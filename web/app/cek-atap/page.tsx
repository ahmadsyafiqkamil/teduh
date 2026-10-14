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
import { LangToggle } from '@/components/LangToggle';
import { postRoof } from '@/lib/api';
import { formatPercent } from '@/lib/format';
import { t, type Lang } from '@/lib/i18n';
import { useStoredLang } from '@/lib/useLang';
import type { RoofResponse } from '@/lib/types';
import styles from './page.module.css';

const MATERIAL_LABEL_KEYS: Record<string, string> = {
  clay_tile: 'roof.material.clay_tile',
  concrete_tile: 'roof.material.concrete_tile',
  metal_sheet: 'roof.material.metal_sheet',
  concrete_slab: 'roof.material.concrete_slab',
  asbestos_cement: 'roof.material.asbestos_cement',
  other: 'roof.material.other',
  unknown: 'roof.material.unknown',
};

const FORM_LABEL_KEYS: Record<string, string> = {
  flat: 'roof.form.flat',
  pitched: 'roof.form.pitched',
  mixed: 'roof.form.mixed',
  unknown: 'roof.form.unknown',
};

const ACTION_LABEL_KEYS: Record<string, string> = {
  cool_roof: 'roof.action.cool_roof',
  green_roof: 'roof.action.green_roof',
  maintain_shade: 'roof.action.maintain_shade',
  consult_professional: 'roof.action.consult_professional',
  retake_photo: 'roof.action.retake_photo',
};

export default function CekAtap() {
  const [lang] = useStoredLang();
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
      setError(cause instanceof Error ? cause.message : t(lang, 'roof.analysisFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.topRow}>
        <Link href="/" className={styles.brand}>
          <TreeDeciduous size={18} aria-hidden="true" />
          TEDUH
        </Link>
        <LangToggle />
      </div>

      <h1 className={styles.title}>{t(lang, 'roof.title')}</h1>
      <p className={styles.lead}>{t(lang, 'roof.lead')}</p>

      <div className={styles.privacy}>
        <strong>{t(lang, 'roof.privacyPrefix')}</strong> {t(lang, 'roof.privacy')}
      </div>

      <label className={styles.picker}>
        <Camera size={28} aria-hidden="true" color="var(--color-canopy)" />
        <div style={{ marginTop: 'var(--space-5)', fontWeight: 600 }}>
          {busy ? t(lang, 'roof.analyzing') : t(lang, 'roof.pick')}
        </div>
        <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-kicker)', color: 'var(--color-ink-secondary)' }}>
          {t(lang, 'roof.fileHint')}
        </div>
        <input
          type="file"
          accept="image/jpeg,image/png"
          aria-label={t(lang, 'roof.pickLabel')}
          disabled={busy}
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
      </label>

      {previewUrl && <img src={previewUrl} alt={t(lang, 'roof.previewAlt')} className={styles.preview} />}

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
              {t(lang, ACTION_LABEL_KEYS[result.recommendation.action] ?? result.recommendation.action)}
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
            <span className="kicker">{t(lang, 'roof.kicker')}</span>
            <div className={styles.row}>
              <span>{t(lang, 'roof.form')}</span>
              <strong>{t(lang, FORM_LABEL_KEYS[result.roof.roof_form] ?? result.roof.roof_form)}</strong>
            </div>
            <div className={styles.row}>
              <span>{t(lang, 'roof.material')}</span>
              <strong>{t(lang, MATERIAL_LABEL_KEYS[result.roof.material] ?? result.roof.material)}</strong>
            </div>
            <div className={styles.row}>
              <span>{t(lang, 'roof.confidence')}</span>
              <strong>{formatPercent(result.roof.confidence, 0, lang)}</strong>
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
