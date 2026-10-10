import { afterEach, describe, expect, it } from 'vitest';
import { KEYBOARD_STEP_PX, clampPx, readSize, writeSize } from './resize';

afterEach(() => {
  localStorage.clear();
});

describe('clampPx', () => {
  it('raises a value below the minimum', () => {
    expect(clampPx(100, 280, 760)).toBe(280);
  });

  it('lowers a value above the maximum', () => {
    expect(clampPx(900, 280, 760)).toBe(760);
  });

  it('leaves an in-range value untouched', () => {
    expect(clampPx(400, 280, 760)).toBe(400);
  });
});

describe('readSize', () => {
  it('returns null when nothing is stored', () => {
    expect(readSize('teduh.agentWidth')).toBeNull();
  });

  it('returns null when the stored value is not a number', () => {
    localStorage.setItem('teduh.agentWidth', 'lebar');
    expect(readSize('teduh.agentWidth')).toBeNull();
  });

  it('returns null when localStorage throws on access', () => {
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error('blocked');
    };
    try {
      expect(readSize('teduh.agentWidth')).toBeNull();
    } finally {
      Storage.prototype.getItem = original;
    }
  });

  it('round-trips a persisted size', () => {
    writeSize('teduh.bottomHeight', 320);
    expect(readSize('teduh.bottomHeight')).toBe(320);
  });

  it('keeps the keyboard step at a non-zero constant', () => {
    expect(KEYBOARD_STEP_PX).toBeGreaterThan(0);
  });
});
