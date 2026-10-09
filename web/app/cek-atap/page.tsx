'use client';

/**
 * Citizen-facing roof check. Mobile first: this is the one screen a resident opens on a
 * phone, so it is a single narrow column with a large tap target.
 *
 * The privacy notice and the "do not photograph identifying details" instruction appear
 * BEFORE the file picker. Telling someone their photo was fine to send after they have sent
 * it is not a privacy control.
 */

import { Camera, TreeDeciduous } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { postRoof } from '@/lib/api';
import { formatPercent } from '@/lib/format';
import type { RoofResponse } from '@/lib/types';
import styles from './page.module.css';

const MATERIAL_LABELS: Record<string, string> = {
  clay_tile: 'Genteng tanah liat',
  concrete_tile: 'Genteng beton',
  metal_sheet: 'Seng atau metal',
  concrete_slab: 'Pelat beton',
  asbestos_cement: 'Asbes (semen berserat)',
  other: 'Lainnya',
  unknown: 'Belum bisa dipastikan',
};

const FORM_LABELS: Record<string, string> = {
  flat: 'Datar',
  pitched: 'Miring',
  mixed: 'Campuran',
  unknown: 'Belum bisa dipastikan',
};

const ACTION_LABELS: Record<string, string> = {
  cool_roof: 'Cat cool roof (pemantul panas)',
  green_roof: 'Green roof (atap hijau)',
  maintain_shade: 'Pertahankan peneduh pohon',
  consult_professional: 'Konsultasi tenaga profesional',
  retake_photo: 'Perlu foto ulang',
};

export default function CekAtap() {
  const [result, setResult] = useState<RoofResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setPreviewUrl(URL.createObjectURL(file));
    try {
      setResult(await postRoof(file));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Analisis gagal.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.brand}>
        <TreeDeciduous size={18} aria-hidden="true" />
        TEDUH
      </Link>

      <h1 className={styles.title}>Cek Atap</h1>
      <p className={styles.lead}>
        Foto atap rumah Anda, dan TEDUH akan mengenali jenisnya lalu menyarankan cara
        menurunkan panas yang masuk ke dalam rumah.
      </p>

      <div className={styles.privacy}>
        <strong>Sebelum memotret:</strong> jangan ada wajah, nomor rumah, plat nomor, atau
        nama jalan di dalam frame. Foto Anda <strong>tidak disimpan</strong> — foto hanya
        dianalisis, lalu langsung dibuang bersama seluruh metadatanya.
      </div>

      <label className={styles.picker}>
        <Camera size={28} aria-hidden="true" color="var(--color-canopy)" />
        <div style={{ marginTop: 'var(--space-5)', fontWeight: 600 }}>
          {busy ? 'Menganalisis foto…' : 'Pilih foto atap'}
        </div>
        <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-kicker)', color: 'var(--color-ink-secondary)' }}>
          JPG atau PNG, maksimal 8 MB
        </div>
        <input
          type="file"
          accept="image/jpeg,image/png"
          aria-label="Pilih foto atap"
          disabled={busy}
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
      </label>

      {previewUrl && <img src={previewUrl} alt="Pratinjau foto atap" className={styles.preview} />}

      {error && <div className={styles.error}>{error}</div>}

      {result && (
        <>
          {result.recommendation.safety.length > 0 && (
            <div className={styles.alert} role="alert">
              {result.recommendation.safety.map((line) => (
                <p key={line} style={{ margin: '0 0 var(--space-4)' }}>
                  {line}
                </p>
              ))}
            </div>
          )}

          <div className={styles.card}>
            <h2 style={{ margin: 0, fontSize: 'var(--text-section)' }}>
              {ACTION_LABELS[result.recommendation.action] ?? result.recommendation.action}
            </h2>
            <p style={{ fontSize: 'var(--text-body)', lineHeight: 'var(--leading-prose)' }}>
              {result.recommendation.reason}
            </p>
            {result.guidance && (
              <p style={{ fontSize: 'var(--text-secondary)', color: 'var(--color-ink-secondary)' }}>
                {result.guidance}
              </p>
            )}
          </div>

          <div className={styles.card}>
            <span className="kicker">YANG TERLIHAT DI FOTO</span>
            <div className={styles.row}>
              <span>Bentuk atap</span>
              <strong>{FORM_LABELS[result.roof.roof_form] ?? result.roof.roof_form}</strong>
            </div>
            <div className={styles.row}>
              <span>Material</span>
              <strong>{MATERIAL_LABELS[result.roof.material] ?? result.roof.material}</strong>
            </div>
            <div className={styles.row}>
              <span>Keyakinan analisis</span>
              <strong>{formatPercent(result.roof.confidence, 0)}</strong>
            </div>
            {result.roof.notes && (
              <p style={{ fontSize: 'var(--text-kicker)', color: 'var(--color-ink-secondary)' }}>
                {result.roof.notes}
              </p>
            )}
          </div>
        </>
      )}
    </main>
  );
}
