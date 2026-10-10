/**
 * Panel-resize primitives: a clamp and a guarded localStorage reader/writer.
 *
 * Kept as pure functions (like format.ts / layers.ts) so ResizeHandle can be tested in
 * jsdom, where offsetWidth is always 0. The sizes start from CSS defaults and only become
 * concrete pixels after the user drags a separator, so nothing here needs the viewport.
 */

export const AGENT_MIN_PX = 280;
export const AGENT_MAX_PX = 760;
export const BOTTOM_MIN_PX = 120;
export const BOTTOM_MAX_PX = 560;
export const DRAWER_MIN_PX = 320;
export const DRAWER_MAX_PX = 640;
/** Matches --drawer-width in app/globals.css; used where JS needs the CSS default in px. */
export const DRAWER_WIDTH_DEFAULT = 420;
export const KEYBOARD_STEP_PX = 16;

/** localStorage keys. The values are pixels, persisted so sizes survive a reload. */
export const SIZE_KEYS = {
  agent: 'teduh.agentWidth',
  bottom: 'teduh.bottomHeight',
  drawer: 'teduh.drawerWidth',
} as const;

export function clampPx(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Read a persisted size, or null when absent / unreadable / non-finite. The try/catch is
 * mandatory: private-window and blocked site-data modes can make localStorage throw on read.
 */
export function readSize(key: string): number | null {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

export function writeSize(key: string, value: number): void {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // Ignore: a blocked localStorage should not break the resize itself.
  }
}

export function clearSize(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore.
  }
}
