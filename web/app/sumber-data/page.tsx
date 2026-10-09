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
import { fetchModelCard } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import type { ModelCard } from '@/lib/types';

const SOURCES = [
  {
    name: 'Batas kelurahan — HDX COD-AB Indonesia level 4',
    detail: 'P-code BPS. Lisensi CC BY-IGO.',
  },
  {
    name: 'Suhu permukaan — USGS Landsat 8/9 Collection 2 Level-2',
    detail: 'Median musim kemarau Juni–September 2023–2025. Domain publik.',
  },
  {
    name: 'Indeks vegetasi — Copernicus Sentinel-2 SR Harmonized',
    detail: 'NDVI, NDBI, NDWI. Lisensi Copernicus.',
  },
  {
    name: 'Tutupan lahan — ESA WorldCover v200 (10 m)',
    detail: 'Fraksi pohon, bangunan, dan air per sel. CC BY 4.0.',
  },
  {
    name: 'Bangunan — Google Open Buildings Temporal v1 (2023)',
    detail: 'Tinggi dan kepadatan bangunan. CC BY 4.0.',
  },
  {
    name: 'Penduduk — WorldPop Global2 2025 (100 m, constrained)',
    detail: 'Total dan struktur usia. CC BY 4.0. Tervalidasi ke Dukcapil Semester I 2025.',
  },
  {
    name: 'Elevasi — Copernicus DEM GLO-30',
    detail: 'Rata-rata per sel. Lisensi Copernicus.',
  },
  {
    name: 'Harga satuan — Keputusan Gubernur DKI Jakarta No. 811 Tahun 2025',
    detail: 'Standar Harga Satuan 2025. Harga cool roof dan green roof belum tersedia di dokumen ini.',
  },
];

export default function SumberData() {
  const [card, setCard] = useState<ModelCard | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  useEffect(() => {
    fetchModelCard()
      .then(setCard)
      .catch((error: Error) => setCardError(error.message));
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: '0 auto', padding: 'var(--space-9) var(--space-8) var(--space-11)' }}>
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

      <h1 style={{ fontSize: 'var(--text-kelurahan)', fontWeight: 700, marginTop: 'var(--space-8)' }}>
        Tentang &amp; Sumber Data
      </h1>

      <p style={{ lineHeight: 'var(--leading-prose)', color: 'var(--color-ink-secondary)' }}>
        TEDUH membantu pemerintah daerah memutuskan di mana dan intervensi apa yang paling
        efektif untuk mendinginkan kawasan paling panas dan paling rentan. Semua angka di
        aplikasi ini berasal dari data terbuka atau dari model yang dijelaskan di bawah —
        tidak ada angka yang dikarang.
      </p>

      <h2 style={{ fontSize: 'var(--text-section)', marginTop: 'var(--space-11)' }}>Sumber data</h2>
      <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
        {SOURCES.map((source) => (
          <li key={source.name} style={{ marginBottom: 'var(--space-5)' }}>
            <strong>{source.name}</strong>
            <br />
            <span style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-secondary)' }}>
              {source.detail}
            </span>
          </li>
        ))}
      </ul>

      <h2 style={{ fontSize: 'var(--text-section)', marginTop: 'var(--space-11)' }}>Model panas</h2>

      {cardError && (
        <p style={{ color: 'var(--color-ink-secondary)' }}>{cardError}</p>
      )}

      {card && (
        <>
          <p style={{ lineHeight: 'var(--leading-prose)' }}>
            <strong>{card.target}.</strong> {card.target_caveat}
          </p>
          <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
            <li>Periode data: {card.data_period}</li>
            <li>Wilayah: {card.area}</li>
            <li>
              Data latih: {formatNumber(card.n_train_cells, 0)} sel pada{' '}
              {formatNumber(card.n_kelurahan, 0)} kelurahan
            </li>
            <li>Validasi: {card.validation.scheme}</li>
            <li>
              R² rata-rata <strong>{formatNumber(card.validation.summary.r2_mean, 2)}</strong>,
              lipatan terburuk {formatNumber(card.validation.summary.r2_min, 2)}, RMSE{' '}
              {formatNumber(card.validation.summary.rmse_mean, 2)} °C
              {' — '}
              {card.validation.meets_target
                ? `memenuhi target ${formatNumber(card.validation.target_r2, 2)}.`
                : `belum mencapai target ${formatNumber(card.validation.target_r2, 2)}.`}
            </li>
          </ul>

          <p style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-secondary)', lineHeight: 'var(--leading-caption)' }}>
            {card.validation.why}
          </p>

          <h3 style={{ fontSize: 'var(--text-body)', marginTop: 'var(--space-9)' }}>
            Pemeriksaan independen
          </h3>
          <ul style={{ paddingLeft: 'var(--space-9)', lineHeight: 'var(--leading-prose)' }}>
            {Object.entries(card.independent_checks).map(([key, value]) => (
              <li key={key}>{value}</li>
            ))}
          </ul>

          <h3 style={{ fontSize: 'var(--text-body)', marginTop: 'var(--space-9)' }}>Keterbatasan</h3>
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
