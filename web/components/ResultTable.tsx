'use client';

/**
 * Result cards rendered from structured tool output.
 *
 * design/README.md: "kartu hasil dirender dari output tool terstruktur, bukan dari teks
 * LLM, agar angka terverifikasi." So this component reads the functionResponse payload and
 * never the prose. If a tool returned an error, no card is rendered at all -- an empty card
 * with dashes would look like a data problem rather than a failed call.
 */

import { MapPin } from 'lucide-react';
import { MINUS, formatIdr, formatNumber, formatPercent, formatUnit } from '@/lib/format';
import { SourceChip } from './SourceChip';
import styles from './ResultTable.module.css';

const DATA_SOURCE = 'Data TEDUH v1 (Landsat 8/9, WorldPop 2025, ESA WorldCover v200).';
const MODEL_SOURCE = 'Model panas TEDUH LightGBM v1, spatial block CV.';
const LST_FOOTNOTE = 'LST = suhu permukaan, bukan suhu udara.';

interface RankedArea {
  rank: number;
  kel_id: string;
  kel_name: string;
  kota_name: string;
  hvi: number;
  lst_c_mean: number;
  exposed_vulnerable: number;
}

interface ResultTableProps {
  tool: string;
  response: Record<string, unknown>;
  onHighlight: (kelIds: string[]) => void;
  onSelect: (kelId: string) => void;
}

function RankCard({ areas, onHighlight, onSelect }: {
  areas: RankedArea[];
  onHighlight: (ids: string[]) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        {areas.length} kelurahan paling rentan panas
      </div>

      <div className={styles.headRow}>
        <span>#</span>
        <span>Kelurahan</span>
        <span className={styles.numeric}>HVI</span>
        <span className={styles.numeric}>LST</span>
        <span className={styles.numeric}>Rentan</span>
      </div>

      {areas.map((area) => (
        <button
          key={area.kel_id}
          type="button"
          className={styles.row}
          onMouseEnter={() => onHighlight([area.kel_id])}
          onMouseLeave={() => onHighlight([])}
          onClick={() => onSelect(area.kel_id)}
        >
          <span className={styles.rank}>{area.rank}</span>
          <span>
            {area.kel_name}
            <br />
            <span style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-kicker)' }}>
              {area.kota_name}
            </span>
          </span>
          <span className={styles.numeric}>{formatNumber(area.hvi, 2)}</span>
          <span className={styles.numeric}>{formatUnit(area.lst_c_mean, 'degC', 1)}</span>
          <span className={styles.numeric}>{formatNumber(area.exposed_vulnerable, 0)}</span>
        </button>
      ))}

      <div className={styles.footer}>
        <span>{LST_FOOTNOTE}</span>
        <button
          type="button"
          className={styles.highlightToggle}
          onClick={() => onHighlight(areas.map((area) => area.kel_id))}
        >
          <MapPin size={12} aria-hidden="true" /> Sorot di peta
        </button>
      </div>
    </div>
  );
}

function SimulateCard({ response }: { response: Record<string, unknown> }) {
  const results = response.results as {
    kel_id: string;
    delta_lst_c: number;
    delta_lst_pop_weighted_c: number;
    vulnerable_benefiting: number;
    area_m2: number;
    cost_idr: number;
    extrapolation: boolean;
  }[];
  const evidence = (response.evidence ?? []) as {
    id: string;
    source_title: string;
    year: number;
    value_min: number;
    value_max: number;
    unit: string;
    comparable_to_model: boolean;
    url_or_doi: string;
  }[];
  const extrapolated = results.some((result) => result.extrapolation);

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>Perkiraan dampak intervensi · indikatif</div>

      {results.map((result) => (
        <div key={result.kel_id} className={styles.block}>
          <div className={styles.metricLine}>
            <span>Perubahan suhu permukaan</span>
            <SourceChip
              value={`${result.delta_lst_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_c), 2)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Tertimbang penduduk</span>
            <SourceChip
              value={`${result.delta_lst_pop_weighted_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_pop_weighted_c), 2)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Warga rentan merasakan pendinginan</span>
            <SourceChip
              value={formatNumber(result.vulnerable_benefiting, 0)}
              unit="jiwa"
              kind="model"
              source={`${MODEL_SOURCE} Sel dengan pendinginan minimal 0,5 °C.`}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Perkiraan biaya</span>
            <SourceChip
              value={formatIdr(result.cost_idr).replace('Rp ', '')}
              unit=""
              kind="asumsi"
              source="Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml)."
              align="end"
            />
          </div>
        </div>
      ))}

      {extrapolated && (
        <div className={styles.warn}>
          Skenario ini <strong>di luar rentang data latih</strong> model, jadi angkanya
          kurang bisa dipercaya. Turunkan intensitas intervensi untuk hasil yang lebih
          dapat diandalkan.
        </div>
      )}

      {evidence.map((entry) => (
        <div key={entry.id} className={styles.evidence}>
          Pembanding literatur: {entry.source_title} ({entry.year}) melaporkan{' '}
          {formatUnit(entry.value_min, 'degC', 1)} sampai{' '}
          {formatUnit(entry.value_max, 'degC', 1)}
          {entry.comparable_to_model
            ? '.'
            : ' — perhatikan bahwa studi ini mengukur besaran lain, bukan pendinginan kawasan.'}
        </div>
      ))}

      <div className={styles.footer}>
        <span>{String(response.note ?? LST_FOOTNOTE)}</span>
      </div>
    </div>
  );
}

function OptimizeCard({ response, onSelect }: {
  response: Record<string, unknown>;
  onSelect: (id: string) => void;
}) {
  const packages = response.packages as {
    kel_id: string;
    kel_name: string;
    intervention_type: string;
    level: string;
    cost_idr: number;
    delta_lst_c: number;
    in_top_hvi_quintile: boolean;
  }[];

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        Rekomendasi portofolio · {packages.length} paket
      </div>

      <div className={styles.block}>
        <div className={styles.metricLine}>
          <span>Total biaya</span>
          <SourceChip
            value={formatIdr(response.total_cost_idr as number)}
            kind="asumsi"
            source="Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml)."
            align="end"
          />
        </div>
        <div className={styles.metricLine}>
          <span>Anggaran tersedia</span>
          <SourceChip
            value={formatIdr(response.budget_idr as number)}
            kind="input"
            source="Anggaran yang Anda masukkan."
            align="end"
          />
        </div>
        <div className={styles.metricLine}>
          <span>Porsi untuk kelurahan paling rentan</span>
          <SourceChip
            value={formatPercent(response.equity_share_achieved as number, 0)}
            kind="model"
            source={`${MODEL_SOURCE} Kendala minimum ${formatPercent(response.equity_share_requested as number, 0)}.`}
            align="end"
          />
        </div>
      </div>

      {packages.map((item) => (
        <button
          key={`${item.kel_id}-${item.intervention_type}`}
          type="button"
          className={styles.block}
          style={{ textAlign: 'left', width: '100%', border: 0, background: 'none', cursor: 'pointer' }}
          onClick={() => onSelect(item.kel_id)}
        >
          <strong>{item.kel_name}</strong> · {item.intervention_type} ({item.level}) ·{' '}
          {formatIdr(item.cost_idr)}
          {item.in_top_hvi_quintile && ' · kuintil teratas'}
        </button>
      ))}

      <div className={styles.footer}>
        <span>{String(response.note ?? LST_FOOTNOTE)}</span>
      </div>
    </div>
  );
}

export function ResultTable({ tool, response, onHighlight, onSelect }: ResultTableProps) {
  // A failed tool call renders no card: an empty table of dashes reads as missing data
  // rather than as a call that did not succeed.
  if (!response || 'error' in response) return null;

  if (tool === 'rank_priority_areas' && Array.isArray(response.areas)) {
    return (
      <RankCard
        areas={response.areas as RankedArea[]}
        onHighlight={onHighlight}
        onSelect={onSelect}
      />
    );
  }

  if (tool === 'simulate_intervention' && Array.isArray(response.results)) {
    return <SimulateCard response={response} />;
  }

  if (tool === 'optimize_portfolio' && Array.isArray(response.packages)) {
    return <OptimizeCard response={response} onSelect={onSelect} />;
  }

  return null;
}
