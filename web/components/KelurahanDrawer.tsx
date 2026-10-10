'use client';

/**
 * Kelurahan profile drawer.
 *
 * Two things here are substantive rather than cosmetic.
 *
 * design/README.md requires the SHAP bars to sum to the stated temperature difference. They
 * often will not: the model explains its own prediction, not the observed anomaly against
 * the city mean, and those are different quantities. Rather than hide the gap by rounding or
 * by relabelling the total, the drawer states it. A chart that silently does not add up is
 * worse than one that admits it.
 *
 * Every figure goes through SourceChip. That is the product's central claim, and a single
 * bare number anywhere undermines the badge on the brief.
 */

import { MessageCircle, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchProfile } from '@/lib/api';
import { MINUS, formatNumber, formatPercent, formatRank, formatUnit } from '@/lib/format';
import { DRAWER_MAX_PX, DRAWER_MIN_PX, DRAWER_WIDTH_DEFAULT } from '@/lib/resize';
import type { Driver, ProfileResponse } from '@/lib/types';
import { ResizeHandle } from './ResizeHandle';
import { SourceChip, kindForSource } from './SourceChip';
import styles from './KelurahanDrawer.module.css';

const DATA_SOURCE =
  'Data TEDUH v1: Landsat 8/9 (median musim kemarau 2023–2025), Sentinel-2, '
  + 'ESA WorldCover v200, Google Open Buildings, WorldPop 2025.';

const MODEL_SOURCE =
  'Model panas TEDUH LightGBM v1 dengan monotonic constraints dan spatial block CV.';

/** Contributions and anomaly are different quantities; flag a gap beyond this. */
const SUM_TOLERANCE_C = 0.1;

/** Zero axis position inside the divergent bar track (design/README.md §3). */
const ZERO_AXIS_PCT = 20;

const COMPONENT_LABELS: [keyof ProfileResponse['profile'], string][] = [
  ['H', 'Bahaya (panas permukaan)'],
  ['E', 'Keterpaparan (kepadatan penduduk)'],
  ['S', 'Kepekaan (balita & lansia)'],
  ['A', 'Kurangnya kapasitas adaptif'],
];

const LANDCOVER_COLORS = {
  built: '#6F6A60',
  tree: '#5E9A6E',
  water: '#5FA3CB',
  other: '#D5D0C6',
};

function DriverBar({ driver, scale }: { driver: Driver; scale: number }) {
  const warming = driver.contribution_c > 0;
  const widthPct = (Math.abs(driver.contribution_c) / scale) * (100 - ZERO_AXIS_PCT);

  return (
    <div className={styles.driverRow}>
      <span>{driver.label}</span>
      <span className={styles.driverTrack}>
        <span
          className={styles.driverBar}
          style={{
            left: warming ? `${ZERO_AXIS_PCT}%` : `${ZERO_AXIS_PCT - widthPct}%`,
            width: `${widthPct}%`,
            background: warming ? 'var(--color-hot)' : 'var(--color-cold)',
          }}
        />
      </span>
      <SourceChip
        value={`${driver.contribution_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(driver.contribution_c), 1)}`}
        unit="°C"
        kind="model"
        source={`${MODEL_SOURCE} Kontribusi ${driver.label} (${driver.direction}).`}
        align="end"
      />
    </div>
  );
}

interface KelurahanDrawerProps {
  kelId: string | null;
  onClose: () => void;
  onAskAgent: (prompt: string) => void;
  width: number | null;
  onResize: (next: number | null) => void;
}

export function KelurahanDrawer({
  kelId,
  onClose,
  onAskAgent,
  width,
  onResize,
}: KelurahanDrawerProps) {
  const [data, setData] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kelId) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setData(null);
    setError(null);
    fetchProfile(kelId)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message);
      });
    return () => {
      cancelled = true;
    };
  }, [kelId]);

  useEffect(() => {
    if (!kelId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [kelId, onClose]);

  if (!kelId) return null;

  const drawerStyle = {
    '--drawer-w': width ? `${width}px` : undefined,
  } as React.CSSProperties;
  const resizeHandle = (
    <div className={styles.drawerHandle}>
      <ResizeHandle
        axis="vertical"
        getSize={() => width ?? DRAWER_WIDTH_DEFAULT}
        min={DRAWER_MIN_PX}
        max={DRAWER_MAX_PX}
        onResize={onResize}
        label="Ubah lebar panel profil"
      />
    </div>
  );

  if (error) {
    return (
      <aside className={styles.drawer} style={drawerStyle} role="dialog" aria-label="Profil kelurahan">
        {resizeHandle}
        <div className={styles.state}>{error}</div>
      </aside>
    );
  }

  if (!data) {
    return (
      <aside className={styles.drawer} style={drawerStyle} role="dialog" aria-label="Profil kelurahan">
        {resizeHandle}
        <div className={styles.state}>Memuat profil kelurahan…</div>
      </aside>
    );
  }

  const { profile, total_kelurahan: total, drivers } = data;
  const driverSum = drivers.reduce((total_, driver) => total_ + driver.contribution_c, 0);
  const mismatch = Math.abs(driverSum - profile.lst_anomaly) > SUM_TOLERANCE_C;
  const scale = Math.max(...drivers.map((d) => Math.abs(d.contribution_c)), 0.1);
  const otherFrac = Math.max(
    0,
    1 - profile.built_frac - profile.tree_frac - profile.water_frac,
  );

  return (
    <aside
      className={styles.drawer}
      style={drawerStyle}
      role="dialog"
      aria-label={`Profil ${profile.kel_name}`}
    >
      {resizeHandle}
      <div className={styles.header}>
        <div className={styles.headerTop}>
          <span className="kicker">PROFIL KELURAHAN</span>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Tutup profil">
            <X size={18} />
          </button>
        </div>

        <h2 className={styles.name}>{profile.kel_name}</h2>
        <div className={styles.location}>
          Kec. {profile.kec_name} · {profile.kota_name}
        </div>

        <div className={styles.pills}>
          <span className={styles.pillRank}>
            Peringkat HVI{' '}
            <SourceChip
              value={formatRank(profile.hvi_rank, total)}
              kind="data"
              source={`${DATA_SOURCE} Peringkat dihitung atas ${total} kelurahan DKI Jakarta daratan.`}
              placement="bottom"
            />
          </span>
        </div>

        <button
          type="button"
          className={styles.ask}
          onClick={() =>
            onAskAgent(
              `Jelaskan kondisi panas dan opsi intervensi untuk Kelurahan ${profile.kel_name}.`,
            )
          }
        >
          <MessageCircle size={16} aria-hidden="true" />
          Tanya agen tentang wilayah ini
        </button>
      </div>

      <div className={styles.body}>
        <div className={styles.metrics}>
          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>LST rata-rata</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.lst, 1)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>suhu permukaan</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Selisih dari rata-rata kota</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hot-strong)' }}>
              <SourceChip
                value={`${profile.lst_anomaly > 0 ? '+' : MINUS}${formatNumber(Math.abs(profile.lst_anomaly), 2)}`}
                unit="°C"
                kind="data"
                source={`${DATA_SOURCE} Rata-rata kota dihitung dari sel berkualitas baik.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              rata-rata kota{' '}
              <SourceChip
                value={formatNumber(profile.lst - profile.lst_anomaly, 2)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                align="start"
              />
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Indeks kerentanan (HVI)</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hvi-dark)' }}>
              <SourceChip
                value={formatNumber(profile.hvi, 2)}
                kind="data"
                source={`${DATA_SOURCE} HVI adalah persentil dalam-kota, bukan risiko absolut.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>skala 0–1, makin tinggi makin rentan</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Warga rentan</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.vulnerable, 0)}
                unit="jiwa"
                kind="data"
                source={`${DATA_SOURCE} Balita (<5 tahun) dan lansia (>=65 tahun), WorldPop 2025.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              <SourceChip
                value={formatNumber(profile.exposed_vulnerable, 0)}
                unit="jiwa"
                kind="data"
                source={`${DATA_SOURCE} Warga rentan di sel dengan persentil bahaya >= 0,8.`}
                align="start"
              />{' '}
              di sel paling panas
            </div>
          </div>
        </div>

        <section>
          <h3 className={styles.sectionTitle}>Komponen kerentanan panas</h3>
          <div className={styles.formula}>
            HVI = Bahaya × (0,4 Keterpaparan + 0,3 Kepekaan + 0,3 Kurangnya kapasitas adaptif)
          </div>
          {COMPONENT_LABELS.map(([key, label]) => {
            const value = profile[key] as number;
            return (
              <div key={key} className={styles.componentRow}>
                <div>
                  <div className={styles.componentLabel}>{label}</div>
                  <div className={styles.track}>
                    <div className={styles.fill} style={{ width: `${value * 100}%` }} />
                  </div>
                </div>
                <SourceChip
                  value={formatNumber(value, 2)}
                  kind="data"
                  source={`${DATA_SOURCE} Persentil dalam-kota untuk komponen ${key}.`}
                  align="end"
                />
              </div>
            );
          })}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>Apa yang membuat wilayah ini panas?</h3>
          <div className={styles.sectionSub}>
            Kontribusi tiap faktor terhadap prediksi suhu, menurut model (SHAP).
          </div>

          {data.drivers_unavailable && (
            <div className={styles.mismatch}>{data.drivers_unavailable}</div>
          )}

          {drivers.length > 0 && (
            <div className={styles.driverLegend} aria-label="Arah kontribusi">
              <span className={styles.legendWarm}>memanaskan</span>
              <span className={styles.legendCool}>mendinginkan</span>
            </div>
          )}

          {drivers.map((driver) => (
            <DriverBar key={driver.feature} driver={driver} scale={scale} />
          ))}

          {drivers.length > 0 && mismatch && (
            <div className={styles.mismatch}>
              Jumlah kontribusi di atas{' '}
              <SourceChip
                value={`${driverSum > 0 ? '+' : MINUS}${formatNumber(Math.abs(driverSum), 2)}`}
                unit="°C"
                kind="model"
                source={MODEL_SOURCE}
                align="start"
              />{' '}
              <strong>tidak menjumlah</strong> ke selisih dari rata-rata kota. Keduanya
              besaran berbeda: model menjelaskan prediksinya sendiri, bukan selisih terhadap
              rata-rata kota. Pakai angka ini sebagai arah, bukan sebagai penguraian tepat.
            </div>
          )}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>Tutupan lahan</h3>
          <div className={styles.landcover}>
            <span style={{ width: `${profile.built_frac * 100}%`, background: LANDCOVER_COLORS.built }} />
            <span style={{ width: `${profile.tree_frac * 100}%`, background: LANDCOVER_COLORS.tree }} />
            <span style={{ width: `${profile.water_frac * 100}%`, background: LANDCOVER_COLORS.water }} />
            <span style={{ width: `${otherFrac * 100}%`, background: LANDCOVER_COLORS.other }} />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>Bangunan</span>
            <SourceChip
              value={formatPercent(profile.built_frac, 1)}
              kind="data"
              source={`${DATA_SOURCE} ESA WorldCover kelas 50.`}
              align="end"
            />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>Pohon</span>
            <SourceChip
              value={formatPercent(profile.tree_frac, 1)}
              kind="data"
              source={`${DATA_SOURCE} ESA WorldCover kelas 10 dan 95.`}
              align="end"
            />
          </div>
        </section>

        <div className={styles.footnote}>
          <span aria-hidden="true">ⓘ</span>
          <span>{data.note}</span>
        </div>
      </div>
    </aside>
  );
}
