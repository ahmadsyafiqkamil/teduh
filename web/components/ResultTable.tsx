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
import { briefUrl } from '@/lib/api';
import { MINUS, formatIdr, formatNumber, formatPercent, formatUnit } from '@/lib/format';
import { t, type Lang } from '@/lib/i18n';
import { SourceChip } from './SourceChip';
import styles from './ResultTable.module.css';

const MODEL_SOURCE = 'Model panas TEDUH LightGBM v1, spatial block CV.';

/** Resolve a tool's note into the active language via note_key, falling back to the raw note. */
function noteFor(response: Record<string, unknown>, lang: Lang): string {
  const key = response.note_key;
  if (typeof key === 'string' && key) return t(lang, key);
  const raw = response.note;
  if (typeof raw === 'string' && raw) return raw;
  return t(lang, 'result.rank.footnote');
}

/** i18n key for a feature the extrapolation guard can flag. */
const FEATURE_LABEL_KEYS: Record<string, string> = {
  albedo: 'feature.albedo',
  ndvi: 'feature.ndvi',
  ndbi: 'feature.ndbi',
  ndwi: 'feature.ndwi',
  tree_frac: 'feature.tree_frac',
  built_frac: 'feature.built_frac',
  water_frac: 'feature.water_frac',
  roof_frac: 'feature.roof_frac',
  bldg_h_mean: 'feature.bldg_h_mean',
  elev_m: 'feature.elev_m',
  dist_coast_km: 'feature.dist_coast_km',
  pop: 'feature.pop',
};

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
  lang?: Lang;
  onHighlight: (kelIds: string[]) => void;
  onSelect: (kelId: string) => void;
}

function RankCard({ areas, lang, onHighlight, onSelect }: {
  areas: RankedArea[];
  lang: Lang;
  onHighlight: (ids: string[]) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        {t(lang, 'result.rank.head', { n: areas.length })}
      </div>

      <div className={styles.headRow}>
        <span>{t(lang, 'result.rank.col.rank')}</span>
        <span>{t(lang, 'result.rank.col.kelurahan')}</span>
        <span className={styles.numeric}>{t(lang, 'result.rank.col.hvi')}</span>
        <span className={styles.numeric}>{t(lang, 'result.rank.col.lst')}</span>
        <span className={styles.numeric}>{t(lang, 'result.rank.col.vulnerable')}</span>
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
          <span className={styles.numeric}>{formatNumber(area.hvi, 2, lang)}</span>
          <span className={styles.numeric}>{formatUnit(area.lst_c_mean, 'degC', 1, lang)}</span>
          <span className={styles.numeric}>{formatNumber(area.exposed_vulnerable, 0, lang)}</span>
        </button>
      ))}

      <div className={styles.footer}>
        <span>{t(lang, 'result.rank.footnote')}</span>
        <button
          type="button"
          className={styles.highlightToggle}
          onClick={() => onHighlight(areas.map((area) => area.kel_id))}
        >
          <MapPin size={12} aria-hidden="true" /> {t(lang, 'result.rank.highlight')}
        </button>
      </div>
    </div>
  );
}

function ExtrapolationWarning({ features, lang }: { features: string[]; lang: Lang }) {
  const labels = features.map((feature) =>
    t(lang, FEATURE_LABEL_KEYS[feature] ?? feature),
  );
  const hasAlbedo = features.includes('albedo');
  const hasOther = features.some((feature) => feature !== 'albedo');

  return (
    <>
      {t(lang, 'result.extrapolation.intro', { labels: labels.join(', ') })}{' '}
      {hasAlbedo && t(lang, 'result.extrapolation.albedo')}{' '}
      {hasOther && t(lang, 'result.extrapolation.other')}
    </>
  );
}

function SimulateCard({ response, lang }: { response: Record<string, unknown>; lang: Lang }) {
  const results = response.results as {
    kel_id: string;
    kel_name: string;
    delta_lst_c: number;
    delta_lst_pop_weighted_c: number;
    vulnerable_benefiting: number;
    area_m2: number;
    cost_idr: number;
    extrapolation: boolean;
    extrapolated_features?: string[];
    area_by_type?: Record<string, number>;
  }[];
  const interventions = (response.interventions ?? []) as { type: string }[];
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
  const flaggedFeatures = [
    ...new Set(results.flatMap((result) => result.extrapolated_features ?? [])),
  ];

  // A tree scenario on fully built (or water) cells plants zero square metres. The number
  // is honest, but a planner needs to be told WHY it is zero rather than left to read it
  // as a silent failure.
  const treeRequested = interventions.some((item) => item.type === 'tree_planting');
  const treeArea = results.reduce(
    (total, result) => total + (result.area_by_type?.tree_planting ?? 0),
    0,
  );

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>{t(lang, 'result.simulate.head')}</div>

      {results.map((result) => (
        <div key={result.kel_id} className={styles.block}>
          <div className={styles.blockHead}>{result.kel_name}</div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.deltaLst')}</span>
            <SourceChip
              value={`${result.delta_lst_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_c), 2, lang)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.popWeighted')}</span>
            <SourceChip
              value={`${result.delta_lst_pop_weighted_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_pop_weighted_c), 2, lang)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.vulnerableBenefiting')}</span>
            <SourceChip
              value={formatNumber(result.vulnerable_benefiting, 0, lang)}
              unit={lang === 'en' ? 'people' : 'jiwa'}
              kind="model"
              source={`${MODEL_SOURCE} ${lang === 'en' ? 'Cells with at least 0.5 °C cooling.' : 'Sel dengan pendinginan minimal 0,5 °C.'}`}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.cost')}</span>
            <SourceChip
              value={formatIdr(result.cost_idr, lang).replace('Rp ', '')}
              unit=""
              kind="asumsi"
              source={t(lang, 'source.price')}
              lang={lang}
              align="end"
            />
          </div>
        </div>
      ))}

      {treeRequested && treeArea <= 0 && (
        <div className={styles.warn}>
          {t(lang, 'result.simulate.treeBlocked')}
        </div>
      )}

      {flaggedFeatures.length > 0 && (
        <div className={styles.warn}>
          <ExtrapolationWarning features={flaggedFeatures} lang={lang} />
        </div>
      )}

      {evidence.map((entry) => (
        <div key={entry.id} className={styles.evidence}>
          {t(lang, 'result.simulate.evidence', {
            title: entry.source_title,
            year: entry.year,
            min: formatUnit(entry.value_min, 'degC', 1, lang),
            max: formatUnit(entry.value_max, 'degC', 1, lang),
          })}
          {entry.comparable_to_model
            ? '.'
            : t(lang, 'result.simulate.evidenceNotComparable')}
        </div>
      ))}

      <div className={styles.footer}>
        <span>{noteFor(response, lang)}</span>
      </div>
    </div>
  );
}

function OptimizeCard({ response, lang, onSelect }: {
  response: Record<string, unknown>;
  lang: Lang;
  onSelect: (id: string) => void;
}) {
  const packages = response.packages as {
    kel_id: string;
    kel_name: string;
    intervention_type: string;
    level: string;
    cost_idr: number;
    delta_lst_c: number;
    vulnerable_benefiting: number;
    in_top_hvi_quintile: boolean;
  }[];

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        {t(lang, 'result.optimize.head', { n: packages.length })}
      </div>

      <div className={styles.block}>
        <div className={styles.metricLine}>
          <span>{t(lang, 'result.optimize.totalCost')}</span>
          <SourceChip
            value={formatIdr(response.total_cost_idr as number, lang)}
            kind="asumsi"
            source={t(lang, 'source.price')}
            lang={lang}
            align="end"
          />
        </div>
        <div className={styles.metricLine}>
          <span>{t(lang, 'result.optimize.budget')}</span>
          <SourceChip
            value={formatIdr(response.budget_idr as number, lang)}
            kind="input"
            source={t(lang, 'result.optimize.budgetSource')}
            lang={lang}
            align="end"
          />
        </div>
        {((response.unspent_idr as number) ?? 0) > 0 && (
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.optimize.unspent')}</span>
            <SourceChip
              value={formatIdr(response.unspent_idr as number, lang)}
              kind="input"
              source={t(lang, 'result.optimize.unspentSource')}
              lang={lang}
              align="end"
            />
          </div>
        )}
        <div className={styles.metricLine}>
          <span>{t(lang, 'result.optimize.equity')}</span>
          <SourceChip
            value={formatPercent(response.equity_share_achieved as number, 0, lang)}
            kind="model"
            source={`${MODEL_SOURCE} ${lang === 'en' ? 'Minimum constraint' : 'Kendala minimum'} ${formatPercent(response.equity_share_requested as number, 0, lang)}.`}
            lang={lang}
            align="end"
          />
        </div>
      </div>

      {/* Each package reports the same impact metrics as a simulation row. A SourceChip is
          itself a button, so the block cannot be a button: the header is the clickable
          region and the metrics sit beside it. */}
      {packages.map((item) => (
        <div key={`${item.kel_id}-${item.intervention_type}`} className={styles.block}>
          <button
            type="button"
            className={styles.blockHead}
            style={{ textAlign: 'left', width: '100%', border: 0, background: 'none', cursor: 'pointer', padding: 0 }}
            onClick={() => onSelect(item.kel_id)}
          >
            {item.kel_name} · {t(lang, `intervention.${item.intervention_type}`)} (
            {t(lang, `level.${item.level}`)})
            {item.in_top_hvi_quintile && ` · ${t(lang, 'result.optimize.quintile')}`}
          </button>

          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.deltaLst')}</span>
            <SourceChip
              value={`${item.delta_lst_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(item.delta_lst_c), 2, lang)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.vulnerableBenefiting')}</span>
            <SourceChip
              value={formatNumber(item.vulnerable_benefiting, 0, lang)}
              unit={lang === 'en' ? 'people' : 'jiwa'}
              kind="model"
              source={`${MODEL_SOURCE} ${lang === 'en' ? 'Cells with at least 0.5 °C cooling.' : 'Sel dengan pendinginan minimal 0,5 °C.'}`}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>{t(lang, 'result.simulate.cost')}</span>
            <SourceChip
              value={formatIdr(item.cost_idr, lang).replace('Rp ', '')}
              unit=""
              kind="asumsi"
              source={t(lang, 'source.price')}
              lang={lang}
              align="end"
            />
          </div>
        </div>
      ))}

      <div className={styles.footer}>
        <span>{noteFor(response, lang)}</span>
      </div>
    </div>
  );
}

function BriefCard({ response, lang }: { response: Record<string, unknown>; lang: Lang }) {
  const briefId = response.brief_id as string;
  const pdfAvailable = response.pdf_available === true;
  const pdfError = response.pdf_error as string | undefined;
  const warnings = (response.warnings ?? []) as string[];

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>{String(response.badge ?? t(lang, 'result.brief.badge'))}</div>

      <div className={styles.block}>
        {pdfAvailable ? (
          <div className={styles.downloadRow}>
            <a className={styles.downloadLink} href={briefUrl(briefId, 'pdf')} download>
              {t(lang, 'result.brief.downloadPdf')}
            </a>
            <a className={styles.downloadLink} href={briefUrl(briefId, 'md')} download>
              {t(lang, 'result.brief.downloadMd')}
            </a>
          </div>
        ) : (
          <>
            <div className={styles.warn}>
              {t(lang, 'result.brief.pdfFailed', { error: pdfError ? `: ${pdfError}` : '' })}
            </div>
            <a className={styles.downloadLink} href={briefUrl(briefId, 'md')} download>
              {t(lang, 'result.brief.downloadMd')}
            </a>
          </>
        )}
      </div>

      {warnings.length > 0 && (
        <div className={styles.warn}>
          {warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}

      <div className={styles.footer}>
        <span>{t(lang, 'result.brief.verified')}</span>
      </div>
    </div>
  );
}

export function ResultTable({
  tool,
  response,
  lang = 'id',
  onHighlight,
  onSelect,
}: ResultTableProps) {
  // A failed tool call renders no card: an empty table of dashes reads as missing data
  // rather than as a call that did not succeed.
  if (!response || 'error' in response) return null;

  if (tool === 'rank_priority_areas' && Array.isArray(response.areas)) {
    return (
      <RankCard
        areas={response.areas as RankedArea[]}
        lang={lang}
        onHighlight={onHighlight}
        onSelect={onSelect}
      />
    );
  }

  if (tool === 'simulate_intervention' && Array.isArray(response.results)) {
    return <SimulateCard response={response} lang={lang} />;
  }

  if (tool === 'optimize_portfolio' && Array.isArray(response.packages)) {
    return <OptimizeCard response={response} lang={lang} onSelect={onSelect} />;
  }

  if (tool === 'render_policy_brief' && typeof response.brief_id === 'string') {
    return <BriefCard response={response} lang={lang} />;
  }

  return null;
}
