import { describe, expect, it } from 'vitest';
import { TABLES, t } from './i18n';

describe('t', () => {
  it('returns Indonesian by default', () => {
    expect(t('id', 'header.searchPlaceholder')).toBe('Cari kelurahan…');
  });

  it('returns English when asked', () => {
    expect(t('en', 'header.searchPlaceholder')).toBe('Search kelurahan…');
  });

  it('fills placeholders from params', () => {
    expect(t('en', 'map.priority', { n: 5 })).toBe('5 priority kelurahan from the agent answer');
    expect(t('id', 'map.priority', { n: 5 })).toBe('5 kelurahan prioritas dari jawaban agen');
  });

  it('falls back to the key rather than rendering nothing', () => {
    expect(t('en', 'header.doesNotExist')).toBe('header.doesNotExist');
  });

  it('keeps both languages consistent in size', () => {
    // A missing key in one language surfaces as the raw key, so parity matters.
    const idKeys = Object.keys(TABLES.id);
    const enKeys = Object.keys(TABLES.en);
    for (const key of idKeys) {
      expect(enKeys).toContain(key);
    }
    for (const key of enKeys) {
      expect(idKeys).toContain(key);
    }
  });
});