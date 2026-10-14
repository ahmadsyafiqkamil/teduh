'use client';

/**
 * The source chip. design/README.md: "Wajib dipakai untuk setiap angka di UI."
 *
 * The tooltip opens on focus as well as hover. That is not a nicety -- provenance is this
 * product's central claim, and a mouse-only tooltip hides it from exactly the users who
 * cannot verify it any other way.
 *
 * Positioning is plain CSS rather than a floating-ui dependency. The chips sit inside
 * panels with predictable room above them, and `placement`/`align` cover the cases where
 * they do not. Revisit only if a chip is actually clipped somewhere.
 */

import { Info } from 'lucide-react';
import { useId, useState } from 'react';
import { t, type Lang } from '@/lib/i18n';
import styles from './SourceChip.module.css';

export type SourceKind = 'data' | 'model' | 'literatur' | 'asumsi' | 'input';

export const SOURCE_KICKER_KEYS: Record<SourceKind, string> = {
  data: 'source.kicker.data',
  model: 'source.kicker.model',
  literatur: 'source.kicker.literatur',
  asumsi: 'source.kicker.asumsi',
  input: 'source.kicker.input',
};

/** Legacy Indonesian kickers, kept for callers that do not pass a language. */
export const SOURCE_KICKERS: Record<SourceKind, string> = {
  data: 'Sumber · Data satelit',
  model: 'Sumber · Model & perhitungan TEDUH',
  literatur: 'Sumber · Literatur',
  asumsi: 'ASUMSI · dapat diedit',
  input: 'Sumber · Masukan pengguna',
};

/** Map a Fact.source token onto a chip kind. */
export function kindForSource(source: string): SourceKind {
  if (source.startsWith('model:')) return 'model';
  if (source.startsWith('evidence:')) return 'literatur';
  if (source.startsWith('assumption:') || source.trim().toUpperCase() === 'ASUMSI') {
    return 'asumsi';
  }
  // A literal citation string (e.g. a Kepgub reference) is a real source, not an
  // assumption. Labelling it "ASUMSI · dapat diedit" would be the opposite of the truth.
  return 'data';
}

interface SourceChipProps {
  value: string;
  unit?: string;
  kind: SourceKind;
  source: string;
  placement?: 'top' | 'bottom';
  align?: 'center' | 'start' | 'end';
  lang?: Lang;
}

export function SourceChip({
  value,
  unit,
  kind,
  source,
  placement = 'top',
  align = 'center',
  lang = 'id',
}: SourceChipProps) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();

  const isDashed = kind === 'asumsi' || kind === 'input';
  // "%" sits tight against the number; everything else gets a non-breaking space.
  const rendered = unit ? (unit === '%' ? `${value}%` : `${value} ${unit}`) : value;

  return (
    <button
      type="button"
      className={`${styles.chip} ${isDashed ? styles.dashed : ''}`}
      tabIndex={0}
      aria-describedby={open ? tooltipId : undefined}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setOpen(false);
      }}
    >
      {rendered}
      <Info size={11} className={styles.icon} aria-hidden="true" />
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className={`${styles.tooltip} ${styles[placement]} ${styles[align]}`}
        >
          <span
            className={`${styles.kicker} ${kind === 'asumsi' ? styles.kickerAssumption : ''}`}
          >
            {t(lang, SOURCE_KICKER_KEYS[kind])}
          </span>
          {source}
        </span>
      )}
    </button>
  );
}
