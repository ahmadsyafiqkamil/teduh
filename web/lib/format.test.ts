import { describe, expect, it } from 'vitest';
import { MINUS, formatIdr, formatNumber, formatPercent, formatRank, formatUnit } from './format';

describe('formatNumber', () => {
  it('uses a comma for decimals and a dot for thousands', () => {
    expect(formatNumber(1020.39)).toBe('1.020,39');
  });

  it('uses a real minus sign, not a hyphen', () => {
    // design/README.md: minus is U+2212. A hyphen is visually shorter and breaks alignment
    // in a tabular column.
    expect(formatNumber(-0.83)).toBe(`${MINUS}0,83`);
    expect(formatNumber(-0.83)).not.toContain('-');
  });

  it('respects an explicit decimal count', () => {
    expect(formatNumber(41.8376, 1)).toBe('41,8');
    expect(formatNumber(41.8376, 3)).toBe('41,838');
  });

  it('renders a missing value as an em dash rather than NaN', () => {
    expect(formatNumber(null)).toBe('—');
    expect(formatNumber(Number.NaN)).toBe('—');
  });
});

describe('formatUnit', () => {
  it('puts a non-breaking space before a normal unit', () => {
    expect(formatUnit(44.61, 'degC', 2)).toBe('44,61 °C');
  });

  it('attaches a percent sign with no space', () => {
    expect(formatUnit(30, '%', 0)).toBe('30%');
  });

  it('renders a unitless value plainly', () => {
    expect(formatUnit(0.93, '', 2)).toBe('0,93');
  });
});

describe('formatIdr', () => {
  it('prefixes Rp and groups thousands', () => {
    expect(formatIdr(1_950_000_000)).toBe('Rp 1.950.000.000');
  });

  it('never shows centavos', () => {
    expect(formatIdr(95_000.7)).toBe('Rp 95.001');
  });
});

describe('formatPercent', () => {
  it('converts a fraction to a percentage', () => {
    expect(formatPercent(0.6)).toBe('60%');
  });

  it('keeps a decimal when asked', () => {
    expect(formatPercent(0.0832, 1)).toBe('8,3%');
  });
});

describe('formatRank', () => {
  it('always states the total so a rank is interpretable', () => {
    expect(formatRank(1, 264)).toBe('1 dari 264');
  });

  it('handles a missing rank', () => {
    expect(formatRank(null, 264)).toBe('—');
  });
});
