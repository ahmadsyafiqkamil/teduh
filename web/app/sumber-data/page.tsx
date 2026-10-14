'use client';

/**
 * Attribution and model card.
 *
 * A submission requirement (CONCEPT §16) and the mitigation for the data-licence risk
 * (CONCEPT §14), so the attribution block renders even when the model card fetch fails --
 * the licences do not stop applying because an artifact is missing.
 *
 * The R squared shown is whatever the model actually scored. If it misses the 0.75 target
 * the page says so, because the alternative is a page that quietly contradicts the model
 * card it claims to display.
 */

import { TreeDeciduous } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { LangToggle } from '@/components/LangToggle';
import { fetchModelCard } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import { t, type Lang } from '@/lib/i18n';
import { useStoredLang } from '@/lib/useLang';
import type { ModelCard } from '@/lib/types';

const SOURCES: { name: Record<Lang, string>; detail: Record<Lang, string> }[] = [
  {
    name: {
      id: 'Batas kelurahan — HDX COD-AB Indonesia level 4',
      en: 'Kelurahan boundaries — HDX COD-AB Indonesia level 4',
    },
    detail: { id: 'P-code BPS. Lisensi CC BY-IGO.', en: 'BPS P-codes. CC BY-IGO licence.' },
  },
  {
    name: {
      id: 'Suhu permukaan — USGS Landsat 8/9 Collection 2 Level-2',
      en: 'Surface temperature — USGS Landsat 8/9 Collection 2 Level-2',
    },
    detail: {
      id: 'Median musim kemarau Juni–September 2023–2025. Domain publik.',
      en: 'Dry-season median June–September 2023–2025. Public domain.',
    },
  },
  {
    name: {
      id: 'Indeks vegetasi — Copernicus Sentinel-2 SR Harmonized',
      en: 'Vegetation indices — Copernicus Sentinel-2 SR Harmonized',
    },
    detail: { id: 'NDVI, NDBI, NDWI. Lisensi Copernicus.', en: 'NDVI, NDBI, NDWI. Copernicus licence.' },
  },
  {
    name: {
      id: 'Tutupan lahan — ESA WorldCover v200 (10 m)',
      en: 'Land cover — ESA WorldCover v200 (10 m)',
    },
    detail: {
      id: 'Fraksi pohon, bangunan, dan air per sel. CC BY 4.0.',
      en: 'Tree, building, and water fraction per cell. CC BY 4.0.',
    },
  },
  {
    name: {
      id: 'Bangunan — Google Open Buildings Temporal v1 (2023)',
      en: 'Buildings — Google Open Buildings Temporal v1 (2023)',
    },
    detail: {
      id: 'Tinggi dan kepadatan bangunan. CC BY 4.0.',
      en: 'Building height and density. CC BY 4.0.',
    },
  },
  {
    name: {
      id: 'Penduduk — WorldPop Global2 2025 (100 m, constrained)',
      en: 'Population — WorldPop Global2 2025 (100 m, constrained)',
    },
    detail: {
      id: 'Total dan struktur usia. CC BY 4.0. Tervalidasi ke Dukcapil Semester I 2025.',
      en: 'Total and age structure. CC BY 4.0. Validated to Dukcapil H1 2025.',
    },
  },
  {
    name: {
      id: 'Elevasi — Copernicus DEM GLO-30',
      en: 'Elevation — Copernicus DEM GLO-30',
    },
    detail: { id: 'Rata-rata per sel. Lisensi Copernicus.', en: 'Mean per cell. Copernicus licence.' },
  },
  {
    name: {
      id: 'Harga satuan — Keputusan Gubernur DKI Jakarta No. 811 Tahun 2025',
      en: 'Unit prices — Jakarta Governor Regulation No. 811 of 2025',
    },
    detail: {
      id: 'Standar Harga Satuan 2025. Harga cool roof dan green roof belum tersedia di dokumen ini.',
      en: '2025 Unit Price Standard. Cool roof and green roof prices are not yet in this document.',
    },
  },
];

export default function SumberData() {
  const [lang] = useStoredLang();
  const [card, setCard] = useState<ModelCard | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  useEffect(() => {
    fetchModelCard()
      .then(setCard)
      .catch((error: Error) => setCardError(error.message));
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: '0 auto', padding: 'var(--space-9) var(--space-8) var(--space-11)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link
          href="/"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 'var(--space-4)',
            color: 'var(--color-canopy)', fontSize: 'var(--text-logo)', fontWeight: 700,
            letterSpacing: '0.14em', textDecoration: 'none',
          }}
        >
          <TreeDeciduous size={18} aria-hidden="true" />
          TEDUH
        </Link>
        <LangToggle />
      </div>

      <h1 style={{ fontSize: 'var(--text-kelurahan)', fontWeight: 700, marginTop: 'var(--space-8)' }}>
        {t(lang, 'about.title')}
      </h1>

      <p style={{ lineHeight: 'var(--leading-prose)', color: 'var(--color-ink-secondary)' }}>
        {t(lang, 'about.lead')}
      </p>

      <h2 style={{ fontSize: 'var(--text-section)', marginTop: 'var(--space-11)' }}>{t(lang, 'about.sourcesTitle')}</h2>
      <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
        {SOURCES.map((source) => (
          <li key={source.name.id} style={{ marginBottom: 'var(--space-5)' }}>
            <strong>{source.name[lang]}</strong>
            <br />
            <span style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-secondary)' }}>
              {source.detail[lang]}
            </span>
          </li>
        ))}
      </ul>

      <h2 style={{ fontSize: 'var(--text-section)', marginTop: 'var(--space-11)' }}>{t(lang, 'about.modelTitle')}</h2>

      {cardError && (
        <p style={{ color: 'var(--color-ink-secondary)' }}>{cardError}</p>
      )}

      {card && (
        <>
          <p style={{ lineHeight: 'var(--leading-prose)' }}>
            <strong>{card.target}.</strong> {card.target_caveat}
          </p>
          <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
            <li>{t(lang, 'about.dataPeriod', { period: card.data_period })}</li>
            <li>{t(lang, 'about.area', { area: card.area })}</li>
            <li>
              {t(lang, 'about.trainCells', {
                cells: formatNumber(card.n_train_cells, 0, lang),
                kel: formatNumber(card.n_kelurahan, 0, lang),
              })}
            </li>
            <li>{t(lang, 'about.validation', { scheme: card.validation.scheme })}</li>
            <li>
              {t(lang, 'about.r2', {
                r2: formatNumber(card.validation.summary.r2_mean, 2, lang),
                r2min: formatNumber(card.validation.summary.r2_min, 2, lang),
                rmse: formatNumber(card.validation.summary.rmse_mean, 2, lang),
              })}{' '}
              {' — '}
              {card.validation.meets_target
                ? t(lang, 'about.meetsTarget', { target: formatNumber(card.validation.target_r2, 2, lang) })
                : t(lang, 'about.missesTarget', { target: formatNumber(card.validation.target_r2, 2, lang) })}
            </li>
          </ul>

          <p style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-secondary)', lineHeight: 'var(--leading-caption)' }}>
            {card.validation.why}
          </p>

          <h3 style={{ fontSize: 'var(--text-body)', marginTop: 'var(--space-9)' }}>
            {t(lang, 'about.independentChecks')}
          </h3>
          <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
            {Object.entries(card.independent_checks).map(([key, value]) => (
              <li key={key}>{value}</li>
            ))}
          </ul>

          <h3 style={{ fontSize: 'var(--text-body)', marginTop: 'var(--space-9)' }}>{t(lang, 'about.limitations')}</h3>
          <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
            {card.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
