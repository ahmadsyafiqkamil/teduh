/**
 * Number formatting, locale-aware.
 *
 * Centralised because a planner reads these figures as budget and temperature evidence, and
 * a number formatted two different ways in two panels reads as two different numbers. The
 * minus sign is U+2212 rather than a hyphen: in a tabular column a hyphen is visibly
 * shorter and breaks the alignment the design relies on.
 *
 * Every formatter takes an optional `lang`. Defaults to "id" so existing call sites and the
 * default product language are unchanged. "en" switches to US-style grouping (comma
 * thousands, dot decimals) and English ordinal words ("of" instead of "dari").
 */

import type { Lang } from './i18n';

export const MINUS = '−';

const MISSING = '—';
const NBSP = ' ';

/** Units rendered with no separating space. */
const TIGHT_UNITS = new Set(['%']);

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

function localeOf(lang: Lang): string {
  return lang === 'en' ? 'en-US' : 'id-ID';
}

export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
  lang: Lang = 'id',
): string {
  if (isMissing(value)) return MISSING;

  const body = Math.abs(value).toLocaleString(localeOf(lang), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return value < 0 ? `${MINUS}${body}` : body;
}

export function formatUnit(
  value: number | null | undefined,
  unit: string,
  decimals = 2,
  lang: Lang = 'id',
): string {
  if (isMissing(value)) return MISSING;
  const body = formatNumber(value, decimals, lang);
  if (!unit) return body;
  if (TIGHT_UNITS.has(unit)) return `${body}${unit}`;
  const label = unit === 'degC' ? '°C' : unit === 'm2' ? 'm²' : unit;
  return `${body}${NBSP}${label}`;
}

export function formatIdr(value: number | null | undefined, lang: Lang = 'id'): string {
  if (isMissing(value)) return MISSING;
  // Rupiah has no practical sub-unit at municipal budget scale, so decimals are noise.
  const body = Math.round(Math.abs(value)).toLocaleString(localeOf(lang));
  return `${value < 0 ? MINUS : ''}Rp ${body}`;
}

export function formatPercent(
  fraction: number | null | undefined,
  decimals = 0,
  lang: Lang = 'id',
): string {
  if (isMissing(fraction)) return MISSING;
  return formatUnit(fraction * 100, '%', decimals, lang);
}

export function formatRank(
  rank: number | null | undefined,
  total: number,
  lang: Lang = 'id',
): string {
  if (isMissing(rank)) return MISSING;
  // A rank without its denominator is meaningless: "3" could be of 10 or of 264.
  const sep = lang === 'en' ? ' of ' : ' dari ';
  return `${formatNumber(rank, 0, lang)}${sep}${formatNumber(total, 0, lang)}`;
}
