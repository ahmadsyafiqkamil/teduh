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
import { t, type Lang } from '@/lib/i18n';
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
  ['H', 'drawer.component.H'],
  ['E', 'drawer.component.E'],
  ['S', 'drawer.component.S'],
  ['A', 'drawer.component.A'],
];

const LANDCOVER_COLORS = {
  built: '#6F6A60',
  tree: '#5E9A6E',
  water: '#5FA3CB',
  other: '#D5D0C6',
};

/** i18n key per model feature name, for the English driver labels. */
const DRIVER_LABEL_KEYS: Record<string, string> = {
  albedo: 'driver.albedo',
  ndvi: 'driver.ndvi',
  ndbi: 'driver.ndbi',
  ndwi: 'driver.ndwi',
  tree_frac: 'driver.tree_frac',
  built_frac: 'driver.built_frac',
  water_frac: 'driver.water_frac',
  roof_frac: 'driver.roof_frac',
  bldg_h_mean: 'driver.bldg_h_mean',
  elev_m: 'driver.elev_m',
  dist_coast_km: 'driver.dist_coast_km',
  pop: 'driver.pop',
};

function driverLabel(driver: Driver, lang: Lang): string {
  const key = DRIVER_LABEL_KEYS[driver.feature];
  return lang === 'en' && key ? t(lang, key) : driver.label;
}

function noteForProfile(data: ProfileResponse, lang: Lang): string {
  const key = (data as unknown as Record<string, unknown>).note_key;
  if (typeof key === 'string' && key) return t(lang, key);
  return data.note;
}

function DriverBar({ driver, scale, lang }: { driver: Driver; scale: number; lang: Lang }) {
  const warming = driver.contribution_c > 0;
  const widthPct = (Math.abs(driver.contribution_c) / scale) * (100 - ZERO_AXIS_PCT);

  return (
    <div className={styles.driverRow}>
      <span>{driverLabel(driver, lang)}</span>
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
        value={`${driver.contribution_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(driver.contribution_c), 1, lang)}`}
        unit="°C"
        kind="model"
        source={`${MODEL_SOURCE} Kontribusi ${driverLabel(driver, lang)} (${driver.direction}).`}
        lang={lang}
        align="end"
      />
    </div>
  );
}

interface KelurahanDrawerProps {
  kelId: string | null;
  lang?: Lang;
  onClose: () => void;
  onAskAgent: (prompt: string) => void;
  width: number | null;
  onResize: (next: number | null) => void;
}

export function KelurahanDrawer({
  kelId,
  lang = 'id',
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
        label={t(lang, 'resize.drawer')}
      />
    </div>
  );

  if (error) {
    return (
      <aside className={styles.drawer} style={drawerStyle} role="dialog" aria-label={t(lang, 'drawer.aria')}>
        {resizeHandle}
        <div className={styles.state}>{error}</div>
      </aside>
    );
  }

  if (!data) {
    return (
      <aside className={styles.drawer} style={drawerStyle} role="dialog" aria-label={t(lang, 'drawer.aria')}>
        {resizeHandle}
        <div className={styles.state}>{t(lang, 'drawer.loading')}</div>
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
      aria-label={t(lang, 'drawer.ariaNamed', { name: profile.kel_name })}
    >
      {resizeHandle}
      <div className={styles.header}>
        <div className={styles.headerTop}>
          <span className="kicker">{t(lang, 'drawer.kicker')}</span>
          <button type="button" className={styles.close} onClick={onClose} aria-label={t(lang, 'drawer.close')}>
            <X size={18} />
          </button>
        </div>

        <h2 className={styles.name}>{profile.kel_name}</h2>
        <div className={styles.location}>
          {t(lang, 'drawer.location', { kec: profile.kec_name, kota: profile.kota_name })}
        </div>

        <div className={styles.pills}>
          <span className={styles.pillRank}>
            {t(lang, 'drawer.rank')}{' '}
            <SourceChip
              value={formatRank(profile.hvi_rank, total, lang)}
              kind="data"
              source={t(lang, 'drawer.rankSource', { source: DATA_SOURCE, total })}
              lang={lang}
              placement="bottom"
            />
          </span>
        </div>

        <button
          type="button"
          className={styles.ask}
          onClick={() =>
            onAskAgent(
              t(lang, 'drawer.askPrompt', { name: profile.kel_name }),
            )
          }
        >
          <MessageCircle size={16} aria-hidden="true" />
          {t(lang, 'drawer.askAgent')}
        </button>
      </div>

      <div className={styles.body}>
        <div className={styles.metrics}>
          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>{t(lang, 'drawer.lst')}</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.lst, 1, lang)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                lang={lang}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>{t(lang, 'drawer.lstSub')}</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>{t(lang, 'drawer.anomaly')}</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hot-strong)' }}>
              <SourceChip
                value={`${profile.lst_anomaly > 0 ? '+' : MINUS}${formatNumber(Math.abs(profile.lst_anomaly), 2, lang)}`}
                unit="°C"
                kind="data"
                source={t(lang, 'drawer.anomalySource', { source: DATA_SOURCE })}
                lang={lang}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              {t(lang, 'drawer.anomalySub')}{' '}
              <SourceChip
                value={formatNumber(profile.lst - profile.lst_anomaly, 2, lang)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                lang={lang}
                align="start"
              />
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>{t(lang, 'drawer.hvi')}</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hvi-dark)' }}>
              <SourceChip
                value={formatNumber(profile.hvi, 2, lang)}
                kind="data"
                source={t(lang, 'drawer.hviSource', { source: DATA_SOURCE })}
                lang={lang}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>{t(lang, 'drawer.hviSub')}</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>{t(lang, 'drawer.vulnerable')}</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.vulnerable, 0, lang)}
                unit={lang === 'en' ? 'people' : 'jiwa'}
                kind="data"
                source={t(lang, 'drawer.vulnerableSource', { source: DATA_SOURCE })}
                lang={lang}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              <SourceChip
                value={formatNumber(profile.exposed_vulnerable, 0, lang)}
                unit={lang === 'en' ? 'people' : 'jiwa'}
                kind="data"
                source={t(lang, 'drawer.exposedSource', { source: DATA_SOURCE })}
                lang={lang}
                align="start"
              />{' '}
              {t(lang, 'drawer.exposedSuffix')}
            </div>
          </div>
        </div>

        <section>
          <h3 className={styles.sectionTitle}>{t(lang, 'drawer.componentsTitle')}</h3>
          <div className={styles.formula}>{t(lang, 'drawer.formula')}</div>
          {COMPONENT_LABELS.map(([key, labelKey]) => {
            const value = profile[key] as number;
            return (
              <div key={key} className={styles.componentRow}>
                <div>
                  <div className={styles.componentLabel}>{t(lang, labelKey)}</div>
                  <div className={styles.track}>
                    <div className={styles.fill} style={{ width: `${value * 100}%` }} />
                  </div>
                </div>
                <SourceChip
                  value={formatNumber(value, 2, lang)}
                  kind="data"
                  source={t(lang, 'drawer.componentSource', { source: DATA_SOURCE, key })}
                  lang={lang}
                  align="end"
                />
              </div>
            );
          })}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>{t(lang, 'drawer.driversTitle')}</h3>
          <div className={styles.sectionSub}>{t(lang, 'drawer.driversSub')}</div>

          {data.drivers_unavailable && (
            <div className={styles.mismatch}>{data.drivers_unavailable}</div>
          )}

          {drivers.length > 0 && (
            <div className={styles.driverLegend} aria-label={t(lang, 'drawer.driversTitle')}>
              <span className={styles.legendWarm}>{t(lang, 'drawer.legendWarm')}</span>
              <span className={styles.legendCool}>{t(lang, 'drawer.legendCool')}</span>
            </div>
          )}

          {drivers.map((driver) => (
            <DriverBar key={driver.feature} driver={driver} scale={scale} lang={lang} />
          ))}

          {drivers.length > 0 && mismatch && (
            <div className={styles.mismatch}>
              {t(lang, 'drawer.mismatch', {
                sum: `${driverSum > 0 ? '+' : MINUS}${formatNumber(Math.abs(driverSum), 2, lang)}`,
              })}
            </div>
          )}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>{t(lang, 'drawer.landcoverTitle')}</h3>
          <div className={styles.landcover}>
            <span style={{ width: `${profile.built_frac * 100}%`, background: LANDCOVER_COLORS.built }} />
            <span style={{ width: `${profile.tree_frac * 100}%`, background: LANDCOVER_COLORS.tree }} />
            <span style={{ width: `${profile.water_frac * 100}%`, background: LANDCOVER_COLORS.water }} />
            <span style={{ width: `${otherFrac * 100}%`, background: LANDCOVER_COLORS.other }} />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>{t(lang, 'drawer.landcover.built')}</span>
            <SourceChip
              value={formatPercent(profile.built_frac, 1, lang)}
              kind="data"
              source={t(lang, 'drawer.landcoverSource.built', { source: DATA_SOURCE })}
              lang={lang}
              align="end"
            />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>{t(lang, 'drawer.landcover.tree')}</span>
            <SourceChip
              value={formatPercent(profile.tree_frac, 1, lang)}
              kind="data"
              source={t(lang, 'drawer.landcoverSource.tree', { source: DATA_SOURCE })}
              lang={lang}
              align="end"
            />
          </div>
        </section>

        <div className={styles.footnote}>
          <span aria-hidden="true">ⓘ</span>
          <span>{noteForProfile(data, lang)}</span>
        </div>
      </div>
    </aside>
  );
}
