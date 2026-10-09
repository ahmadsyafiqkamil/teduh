# M7a — Fondasi Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M3c selesai dan API hidup** di `http://localhost:8080`.
>
> **Sumber kebenaran desain: `design/README.md`.** Itu handoff hi-fi dengan warna, tipografi, spasi, dan interaksi final. Buka `design/TEDUH Layar Utama.dc.html` di browser (butuh `support.js` di folder yang sama) untuk melihat perilakunya sebelum menulis kode.

**Goal:** Kerangka Next.js dengan token desain final, pemformatan angka gaya Indonesia, definisi lapisan peta, komponen chip sumber, dan header — semuanya siap dipakai M7b.

**Architecture:** Token desain hidup sebagai CSS custom properties di satu berkas, bukan tersebar di kelas Tailwind, karena palet choropleth harus bisa dibaca JavaScript MapLibre **dan** CSS. `lib/layers.ts` adalah satu-satunya tempat palet, batas kelas, dan teks legenda didefinisikan; peta, legenda, dan tooltip semuanya membacanya dari sana, sehingga ganti lapisan tidak pernah menyisakan legenda yang tidak sinkron.

**Tech Stack:** Next.js App Router, TypeScript, Tailwind CSS, Plus Jakarta Sans, Lucide React, Vitest + Testing Library.

## Global Constraints

- **Semua teks UI Bahasa Indonesia**, toggle Inggris disiapkan (CLAUDE.md aturan 7).
- **Setiap angka di UI wajib memakai `SourceChip`** (`design/README.md` §Komponen kunci). Tidak ada angka telanjang.
- Format angka `id-ID`: koma desimal, titik ribuan, `font-variant-numeric: tabular-nums`, tanda minus **U+2212** (`−`), bukan hubung.
- Fokus terlihat di semua elemen interaktif: `outline 2px solid #1F5C4A; outline-offset 2px`.
- Tooltip aktif saat **hover dan focus**, bukan hover saja (aksesibilitas).
- Animasi hanya pada properti ramah compositor: `transform`, `opacity`. Jangan animasikan `width`/`height`/`top`/`left`.
- Target lebar minimal 1280 px untuk layar utama; `/cek-atap` ramah ponsel.
- Jangan tambah dependensi untuk hal yang bisa 10 baris. Tidak ada komponen library besar.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Peringatan: data contoh di desain bukan data nyata

`design/README.md` memakai data contoh fiktif. Yang **harus** dipakai adalah angka nyata:

| Di desain | Kenyataan |
|---|---|
| 267 kelurahan | **264** |
| Rata-rata LST kota 34,3 °C | **41,84 °C** |
| Batas kelas LST 31 / 32,5 / 33,5 / 34,5 / 35,5 / 36,5 | **Harus dihitung ulang** (Task M7-T2 Step 1) |
| WorldPop 2020 | WorldPop **2025** |
| R² 0,78 | Angka sebenarnya dari `model_card.json` |
| 5 prioritas di Jakarta Timur | Kampung Rawa, Serdang, Johar Baru, Galur (Jakarta Pusat), Krendang (Jakarta Barat) |

Palet, token, tata letak, dan komponen dipakai **apa adanya**. Hanya angkanya yang diganti.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `web/package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs` | Kerangka build. |
| `web/app/globals.css` | Token desain sebagai CSS custom properties + reset + utilitas fokus. |
| `web/app/layout.tsx` | Shell HTML, font, metadata. |
| `web/lib/format.ts` | Pemformatan angka dan satuan gaya Indonesia. Murni, tanpa React. |
| `web/lib/layers.ts` | Empat lapisan: palet, batas kelas, judul, teks legenda, format nilai. |
| `web/lib/api.ts` | Klien fetch bertipe untuk `/api/*`. |
| `web/components/SourceChip.tsx` | Chip sumber. Wajib untuk setiap angka di UI. |
| `web/components/Header.tsx` | Logo, pemilih lapisan, pencarian, toggle ID/EN, tombol Tentang. |

---

## Task M7-T1: Kerangka proyek dan token desain

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/postcss.config.mjs`, `web/.gitignore`
- Create: `web/app/globals.css`
- Create: `web/app/layout.tsx`
- Create: `web/vitest.config.ts`, `web/vitest.setup.ts`

**Interfaces:**
- Consumes: env `NEXT_PUBLIC_TEDUH_API`.
- Produces: `npm run dev` menyajikan halaman kosong bertema; `npm test` menjalankan Vitest; semua token desain tersedia sebagai `var(--...)`.

- [x] **Step 1: Inisialisasi proyek**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
mkdir -p web
cd web
npm init -y
npm install next@latest react@latest react-dom@latest maplibre-gl lucide-react
npm install -D typescript @types/react @types/node @types/react-dom \
  tailwindcss @tailwindcss/postcss postcss \
  vitest @vitejs/plugin-react jsdom \
  @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [x] **Step 2: Tulis `web/package.json` scripts**

Ganti bagian `scripts` menjadi:

```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

- [x] **Step 3: Tulis berkas konfigurasi**

`web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`web/next.config.ts`:

```ts
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The API is a separate Cloud Run service, so there is nothing to rewrite here; the
  // client reads NEXT_PUBLIC_TEDUH_API directly. Kept explicit so nobody adds a proxy
  // and quietly breaks CORS expectations on the API side.
  env: {
    NEXT_PUBLIC_TEDUH_API: process.env.NEXT_PUBLIC_TEDUH_API ?? 'http://localhost:8080',
  },
};

export default nextConfig;
```

`web/postcss.config.mjs`:

```js
export default {
  plugins: { '@tailwindcss/postcss': {} },
};
```

`web/.gitignore`:

```gitignore
node_modules/
.next/
out/
next-env.d.ts
*.tsbuildinfo
```

`web/vitest.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
  },
  resolve: { alias: { '@': new URL('.', import.meta.url).pathname } },
});
```

`web/vitest.setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

- [x] **Step 4: Tulis `web/app/globals.css` dengan token final**

Setiap nilai di sini dikutip dari `design/README.md` §Design Tokens. Jangan mengubahnya.

```css
@import 'tailwindcss';

/* Design tokens from design/README.md. Declared as custom properties rather than Tailwind
   classes because the choropleth palette has to be readable by MapLibre's JavaScript as
   well as by CSS -- two copies of a palette is how the map and its legend drift apart. */
:root {
  /* Brand */
  --color-canopy: #1f5c4a;
  --color-canopy-hover: #184a3c;
  --color-canopy-tint: #eaf2ec;
  --color-canopy-tint-hover: #f5f9f6;
  --color-leaf: #8bb59a;

  /* Surfaces */
  --color-paper: #f7f4ee;
  --color-surface: #ffffff;
  --color-surface-soft: #fbfaf7;
  --color-surface-hover: #f2efe8;
  --color-map-bg: #efebe3;
  --color-sea: #dfe6e4;

  /* Ink */
  --color-ink: #1c2321;
  --color-ink-secondary: #5e6662;
  --color-ink-on-dark: #c9cfcc;

  /* Lines */
  --color-border: #e3ded4;
  --color-border-strong: #cfc8bb;
  --color-border-row: #f0ece4;
  --color-canvas-outline: #d6d0c4;
  --color-axis: #8a918d;

  /* Data */
  --color-hot: #e0533d;
  --color-hot-strong: #b5213a;
  --color-cold: #2b78a8;
  --color-hvi: #6b4fa0;
  --color-hvi-tint: #f2eef7;
  --color-hvi-dark: #3f1f6b;
  --color-water: #5fa3cb;

  /* Type scale (design/README.md §Tipografi) */
  --text-kelurahan: 24px;
  --text-metric: 22px;
  --text-logo: 16px;
  --text-section: 15px;
  --text-body: 14px;
  --text-control: 13.5px;
  --text-secondary: 13px;
  --text-help: 12.5px;
  --text-kicker: 11.5px;
  --text-attribution: 10.5px;

  --leading-body: 1.5;
  --leading-prose: 1.55;
  --leading-caption: 1.45;
  --leading-heading: 1.2;

  /* Spacing scale */
  --space-1: 2px;
  --space-2: 4px;
  --space-3: 6px;
  --space-4: 8px;
  --space-5: 10px;
  --space-6: 12px;
  --space-7: 14px;
  --space-8: 16px;
  --space-9: 20px;
  --space-10: 22px;
  --space-11: 24px;
  --panel-padding: 20px;

  /* Radius */
  --radius-swatch: 3px;
  --radius-badge: 6px;
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  /* Elevation */
  --shadow-card: 0 1px 2px rgba(28, 35, 33, 0.06);
  --shadow-drawer: -10px 0 28px rgba(28, 35, 33, 0.08);
  --shadow-tooltip: 0 8px 24px rgba(28, 35, 33, 0.18);

  /* Motion */
  --duration-fast: 150ms;
  --duration-drawer: 200ms;
  --duration-pan: 300ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);

  /* Layout */
  --header-height: 60px;
  --drawer-width: 420px;
  --agent-panel-header: 52px;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body {
  margin: 0;
  height: 100%;
}

body {
  background: var(--color-paper);
  color: var(--color-ink);
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  font-size: var(--text-body);
  line-height: var(--leading-body);
  -webkit-font-smoothing: antialiased;
}

/* Every figure in this product is a number a planner may act on, so they are all tabular
   and never reflow as values change. */
.tabular,
input[type='number'],
table {
  font-variant-numeric: tabular-nums;
}

/* design/README.md §Interactions: one focus treatment everywhere. */
:focus-visible {
  outline: 2px solid var(--color-canopy);
  outline-offset: 2px;
}

button {
  font: inherit;
  cursor: pointer;
}

.kicker {
  font-size: var(--text-kicker);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-ink-secondary);
}

/* "Data contoh" marker: dashed border, used on every module whose data is not final. */
.badge-sample {
  display: inline-flex;
  align-items: center;
  border: 1px dashed var(--color-ink-secondary);
  border-radius: var(--radius-badge);
  padding: 2px 6px;
  font-size: var(--text-kicker);
  font-weight: 600;
  color: var(--color-ink-secondary);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [x] **Step 5: Tulis `web/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TEDUH — Prioritas penanganan panas kota',
  description:
    'Alat bantu perencanaan mitigasi Urban Heat Island tingkat kelurahan untuk DKI Jakarta, '
    + 'dengan setiap angka bisa ditelusuri ke sumbernya.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        {/* Two weights beyond the body weight only; design/README.md calls for 400-700 and
            nothing wider. preconnect because the font is above the fold. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

- [x] **Step 6: Buat halaman sementara dan verifikasi**

`web/app/page.tsx` sementara:

```tsx
export default function Home() {
  return <main style={{ padding: 'var(--panel-padding)' }}>TEDUH</main>;
}
```

Run: `cd web && npm run dev`
Expected: `http://localhost:3000` menampilkan "TEDUH" dengan latar `#F7F4EE` dan font Plus Jakarta Sans.

Run: `npm test`
Expected: Vitest jalan dan melaporkan tidak ada berkas tes (belum ada).

- [x] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/ .gitignore
git commit -m "chore: kerangka Next.js dengan token desain final dari handoff

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T2: Pemformatan angka dan definisi lapisan

**Files:**
- Create: `web/lib/format.ts`
- Create: `web/lib/layers.ts`
- Test: `web/lib/format.test.ts`, `web/lib/layers.test.ts`

**Interfaces:**
- Consumes: tidak ada.
- Produces:
  - `format.ts`: `MINUS = '−'`, `formatNumber(value: number | null, decimals?: number): string`, `formatUnit(value: number | null, unit: string, decimals?: number): string`, `formatIdr(value: number | null): string`, `formatPercent(fraction: number | null, decimals?: number): string`, `formatRank(rank: number | null, total: number): string`
  - `layers.ts`: `LayerId = 'lst' | 'hvi' | 'veg' | 'pop'`, `LAYER_ORDER: LayerId[]`, `LayerDefinition` (field: `id, label, swatch, property, title, legendTitle, legendSubtitle, palette, breaks, decimals, unit, format`), `LAYERS: Record<LayerId, LayerDefinition>`, `colorForValue(layer: LayerDefinition, value: number | null): string`, `NO_DATA_COLOR`

- [x] **Step 1: Hitung ulang batas kelas LST dari data nyata**

Batas di `design/README.md` (31 / 32,5 / 33,5 / 34,5 / 35,5 / 36,5 °C) berasal dari data contoh dengan rata-rata kota 34,3 °C. Rata-rata sebenarnya **41,84 °C**, jadi seluruh 264 kelurahan akan jatuh ke kelas paling merah dan petanya menjadi satu warna rata. Hitung batas nyata:

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
uv run python -c "
import pandas as pd
k = pd.read_parquet('data/processed/kelurahan_metrics.parquet')
for col, n in (('lst_c_mean', 6), ('hvi', 4), ('tree_frac_mean', 4), ('pop_density', 4)):
    qs = [round(k[col].quantile(i/(n+1)), 4) for i in range(1, n+1)]
    print(f'{col:16s} min {k[col].min():.4f}  max {k[col].max():.4f}  batas {qs}')
"
```

Pakai kuantil yang tercetak sebagai `breaks` di Step 3, dibulatkan rapi (misalnya ke 0,5 °C untuk LST). **Catat angka yang kamu pakai di komentar kode** supaya jelas itu berasal dari data, bukan dari desain. Panjang `palette` harus `breaks.length + 1`.

- [x] **Step 2: Tulis tes yang gagal**

`web/lib/format.test.ts`:

```ts
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
```

`web/lib/layers.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { LAYERS, LAYER_ORDER, NO_DATA_COLOR, colorForValue } from './layers';

describe('layer definitions', () => {
  it('declares exactly the four layers the header offers', () => {
    expect(LAYER_ORDER).toEqual(['lst', 'hvi', 'veg', 'pop']);
  });

  it('gives every layer a palette one longer than its breaks', () => {
    // A palette of n colours needs n-1 thresholds; any other pairing silently drops a class.
    for (const id of LAYER_ORDER) {
      const layer = LAYERS[id];
      expect(layer.palette.length).toBe(layer.breaks.length + 1);
    }
  });

  it('keeps every break list ascending', () => {
    for (const id of LAYER_ORDER) {
      const { breaks } = LAYERS[id];
      expect([...breaks].sort((a, b) => a - b)).toEqual(breaks);
    }
  });

  it('uses the exact palettes from the design handoff', () => {
    expect(LAYERS.hvi.palette).toEqual(['#F2EEF7', '#CBBFE0', '#9B86C4', '#6B4FA0', '#3F1F6B']);
    expect(LAYERS.veg.palette).toEqual(['#F1F5EC', '#CFE0C3', '#9DC39A', '#5E9A6E', '#2C6A4C']);
    expect(LAYERS.pop.palette).toEqual(['#F1EFEA', '#D5D0C6', '#A9A396', '#6F6A60', '#3A3833']);
    expect(LAYERS.lst.palette).toEqual([
      '#FFF5D6', '#FEE08B', '#FDB863', '#F4845F', '#E0533D', '#B5213A', '#6E0F2B',
    ]);
  });

  it('names the metrics parquet column each layer paints', () => {
    expect(LAYERS.lst.property).toBe('lst_c_mean');
    expect(LAYERS.hvi.property).toBe('hvi');
    expect(LAYERS.veg.property).toBe('tree_frac_mean');
    expect(LAYERS.pop.property).toBe('pop_density');
  });

  it('spans the real LST range rather than the design sample range', () => {
    // The design sample had a city mean of 34.3; the real one is 41.84, so breaks built
    // from the design would paint all 264 kelurahan the same colour.
    const { breaks } = LAYERS.lst;
    expect(breaks[breaks.length - 1]).toBeGreaterThan(38);
  });

  it('tells the user LST is a surface temperature in the legend subtitle', () => {
    expect(LAYERS.lst.legendSubtitle.toLowerCase()).toContain('bukan suhu udara');
  });

  it('cites the data source in every legend subtitle', () => {
    for (const id of LAYER_ORDER) {
      expect(LAYERS[id].legendSubtitle.length).toBeGreaterThan(20);
    }
  });
});

describe('colorForValue', () => {
  it('returns the lowest class below the first break', () => {
    expect(colorForValue(LAYERS.hvi, 0.05)).toBe(LAYERS.hvi.palette[0]);
  });

  it('returns the highest class above the last break', () => {
    expect(colorForValue(LAYERS.hvi, 0.99)).toBe(
      LAYERS.hvi.palette[LAYERS.hvi.palette.length - 1],
    );
  });

  it('places a value exactly on a break into the upper class', () => {
    const layer = LAYERS.hvi;
    expect(colorForValue(layer, layer.breaks[0])).toBe(layer.palette[1]);
  });

  it('returns the no-data colour for a missing value', () => {
    // 28 low-quality cells and any unmatched kelurahan must be visibly absent, not
    // painted as if they were the coolest.
    expect(colorForValue(LAYERS.lst, null)).toBe(NO_DATA_COLOR);
  });
});
```

- [x] **Step 3: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./format"`

- [x] **Step 4: Tulis `web/lib/format.ts`**

```ts
/**
 * Indonesian number formatting.
 *
 * Centralised because a planner reads these figures as budget and temperature evidence, and
 * a number formatted two different ways in two panels reads as two different numbers. The
 * minus sign is U+2212 rather than a hyphen: in a tabular column a hyphen is visibly
 * shorter and breaks the alignment the design relies on.
 */

export const MINUS = '−';

const MISSING = '—';
const NBSP = ' ';

/** Units rendered with no separating space. */
const TIGHT_UNITS = new Set(['%']);

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (isMissing(value)) return MISSING;

  const body = Math.abs(value).toLocaleString('id-ID', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return value < 0 ? `${MINUS}${body}` : body;
}

export function formatUnit(
  value: number | null | undefined,
  unit: string,
  decimals = 2,
): string {
  if (isMissing(value)) return MISSING;
  const body = formatNumber(value, decimals);
  if (!unit) return body;
  if (TIGHT_UNITS.has(unit)) return `${body}${unit}`;
  const label = unit === 'degC' ? '°C' : unit === 'm2' ? 'm²' : unit;
  return `${body}${NBSP}${label}`;
}

export function formatIdr(value: number | null | undefined): string {
  if (isMissing(value)) return MISSING;
  // Rupiah has no practical sub-unit at municipal budget scale, so decimals are noise.
  const body = Math.round(Math.abs(value)).toLocaleString('id-ID');
  return `${value < 0 ? MINUS : ''}Rp ${body}`;
}

export function formatPercent(
  fraction: number | null | undefined,
  decimals = 0,
): string {
  if (isMissing(fraction)) return MISSING;
  return formatUnit(fraction * 100, '%', decimals);
}

export function formatRank(rank: number | null | undefined, total: number): string {
  if (isMissing(rank)) return MISSING;
  // A rank without its denominator is meaningless: "3" could be of 10 or of 264.
  return `${formatNumber(rank, 0)} dari ${formatNumber(total, 0)}`;
}
```

- [x] **Step 5: Tulis `web/lib/layers.ts`**

Ganti nilai `breaks` LST dengan hasil Step 1. Nilai di bawah adalah contoh bentuk, bukan angka final — **hitung sendiri dan catat sumbernya di komentar.**

```ts
/**
 * The four map layers: palette, class breaks, legend copy, and value formatting.
 *
 * Single source of truth on purpose. The choropleth fill, the legend ramp, the hover
 * tooltip, and the map title all read from here, so switching layers cannot leave a legend
 * describing the previous one. Palettes are copied verbatim from design/README.md §2.
 *
 * The LST breaks are NOT the ones in the design handoff. Those were built against sample
 * data with a city mean of 34.3 °C; the real mean is 41.84 °C, so the design's breaks would
 * paint all 264 kelurahan in the top class. The values below come from quantiles of
 * data/processed/kelurahan_metrics.parquet (see m7a plan, Task M7-T2 Step 1).
 */

import { formatNumber, formatPercent, formatUnit } from './format';

export type LayerId = 'lst' | 'hvi' | 'veg' | 'pop';

export const LAYER_ORDER: LayerId[] = ['lst', 'hvi', 'veg', 'pop'];

/** Kelurahan with no value for the active metric. Visibly absent, never a real class. */
export const NO_DATA_COLOR = '#D6D0C4';

export interface LayerDefinition {
  id: LayerId;
  /** Header segmented-control label. */
  label: string;
  /** 10x10 swatch beside the label. */
  swatch: string;
  /** GeoJSON property this layer paints. */
  property: string;
  /** Map overlay title, top left. */
  title: string;
  legendTitle: string;
  legendSubtitle: string;
  palette: string[];
  /** Ascending thresholds; palette.length === breaks.length + 1. */
  breaks: number[];
  format: (value: number | null) => string;
}

export const LAYERS: Record<LayerId, LayerDefinition> = {
  lst: {
    id: 'lst',
    label: 'Suhu Permukaan',
    swatch: '#E0533D',
    property: 'lst_c_mean',
    title: 'Suhu permukaan per kelurahan',
    legendTitle: 'Suhu permukaan tanah (LST), °C',
    legendSubtitle:
      'Median musim kemarau 2023–2025 · Landsat 8/9 · bukan suhu udara',
    palette: ['#FFF5D6', '#FEE08B', '#FDB863', '#F4845F', '#E0533D', '#B5213A', '#6E0F2B'],
    // REPLACE with the quantiles printed by Task M7-T2 Step 1, rounded to 0.5 °C.
    breaks: [39.5, 40.5, 41.5, 42.5, 43.5, 44.5],
    format: (value) => formatUnit(value, 'degC', 1),
  },
  hvi: {
    id: 'hvi',
    label: 'Kerentanan (HVI)',
    swatch: '#6B4FA0',
    property: 'hvi',
    title: 'Kerentanan panas per kelurahan',
    legendTitle: 'Indeks Kerentanan Panas (HVI), 0–1',
    legendSubtitle:
      'Bahaya × keterpaparan, kepekaan (balita & lansia), dan kurangnya pohon',
    palette: ['#F2EEF7', '#CBBFE0', '#9B86C4', '#6B4FA0', '#3F1F6B'],
    breaks: [0.2, 0.4, 0.6, 0.8],
    format: (value) => formatNumber(value, 2),
  },
  veg: {
    id: 'veg',
    label: 'Vegetasi',
    swatch: '#5E9A6E',
    property: 'tree_frac_mean',
    title: 'Tutupan vegetasi per kelurahan',
    legendTitle: 'Tutupan vegetasi, % luas kelurahan',
    legendSubtitle: 'ESA WorldCover v200, 10 m · tutupan pohon dan mangrove',
    palette: ['#F1F5EC', '#CFE0C3', '#9DC39A', '#5E9A6E', '#2C6A4C'],
    // Stored as a fraction, so the design's "every 10%" is 0.1 here.
    breaks: [0.1, 0.2, 0.3, 0.4],
    format: (value) => formatPercent(value, 1),
  },
  pop: {
    id: 'pop',
    label: 'Penduduk Rentan',
    swatch: '#6F6A60',
    property: 'pop_density',
    title: 'Kepadatan penduduk per kelurahan',
    legendTitle: 'Penduduk, jiwa per km²',
    legendSubtitle: 'WorldPop 2025, 100 m · model constrained, tervalidasi ke Dukcapil',
    palette: ['#F1EFEA', '#D5D0C6', '#A9A396', '#6F6A60', '#3A3833'],
    // REPLACE with the quantiles printed by Task M7-T2 Step 1.
    breaks: [10_000, 20_000, 30_000, 40_000],
    format: (value) => formatNumber(value, 0),
  },
};

export function colorForValue(layer: LayerDefinition, value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA_COLOR;

  for (let index = 0; index < layer.breaks.length; index += 1) {
    if (value < layer.breaks[index]) return layer.palette[index];
  }
  return layer.palette[layer.palette.length - 1];
}
```

Catatan: `legendSubtitle` untuk Vegetasi dan Penduduk di `design/README.md` ditandai *"perlu konfirmasi klien"*, dan keduanya menyebut WorldPop **2020**. Teks di atas sudah dikoreksi ke WorldPop 2025 dan ke pemetaan WorldCover yang sebenarnya dipakai (kelas 10 + 95, DECISIONS 2026-10-09).

- [x] **Step 6: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 24 tes.

- [x] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/lib/
git commit -m "feat(web): tambah pemformatan angka id-ID dan definisi empat lapisan peta

Batas kelas LST dihitung dari kuantil data nyata, bukan dari data contoh desain
yang rata-rata kotanya 34,3 C padahal sebenarnya 41,84 C.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T3: Klien API bertipe

**Files:**
- Create: `web/lib/types.ts`
- Create: `web/lib/api.ts`
- Test: `web/lib/api.test.ts`

**Interfaces:**
- Consumes: endpoint M3c; env `NEXT_PUBLIC_TEDUH_API`.
- Produces:
  - `types.ts`: `Fact`, `KelurahanProperties`, `KelurahanFeature`, `KelurahanCollection`, `Driver`, `AreaProfile`, `ProfileResponse`, `ScenarioResult`, `SimulateResponse`, `PortfolioPackage`, `OptimizeResponse`, `ModelCard`, `RoofAnalysis`, `RoofRecommendation`, `RoofResponse`
  - `api.ts`: `API_BASE`, `ApiError`, `fetchKelurahan()`, `fetchProfile(kelId)`, `postSimulate(body)`, `postOptimize(body)`, `fetchModelCard()`, `postRoof(file, kelurahan?)`, `briefUrl(briefId, format)`

- [x] **Step 1: Tulis tes yang gagal**

`web/lib/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, briefUrl, fetchKelurahan, fetchProfile, postSimulate } from './api';

function mockFetch(body: unknown, ok = true, status = 200) {
  const spy = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('envelope unwrapping', () => {
  it('returns the data field on success', async () => {
    mockFetch({ success: true, data: { type: 'FeatureCollection', features: [] }, error: null });
    const result = await fetchKelurahan();
    expect(result.features).toEqual([]);
  });

  it('throws ApiError carrying the server message on a failed envelope', async () => {
    // The API puts a human Indonesian message in `error`; swallowing it and showing
    // "something went wrong" throws away the only useful thing on screen.
    mockFetch({ success: false, data: null, error: 'Kelurahan tidak ada di data TEDUH.' }, false, 404);
    await expect(fetchProfile('ID9999999999')).rejects.toThrow('Kelurahan tidak ada');
  });

  it('throws ApiError with the status when the body is not an envelope', async () => {
    mockFetch('bukan json', false, 502);
    await expect(fetchKelurahan()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('request shapes', () => {
  it('posts the simulate body as JSON', async () => {
    const spy = mockFetch({ success: true, data: { results: [] }, error: null });
    await postSimulate({
      kel_ids: ['ID3173040002'],
      interventions: [{ type: 'cool_roof', level: 'medium' }],
    });

    const [, init] = spy.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.headers['content-type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({
      kel_ids: ['ID3173040002'],
      interventions: [{ type: 'cool_roof', level: 'medium' }],
    });
  });

  it('builds the profile URL from the kelurahan id', async () => {
    const spy = mockFetch({ success: true, data: {}, error: null });
    await fetchProfile('ID3173040002');
    expect(spy.mock.calls[0][0]).toContain('/api/kelurahan/ID3173040002');
  });
});

describe('briefUrl', () => {
  it('defaults to markdown', () => {
    expect(briefUrl('abc123def456')).toContain('/api/brief/abc123def456');
  });

  it('asks for pdf when requested', () => {
    expect(briefUrl('abc123def456', 'pdf')).toContain('format=pdf');
  });
});
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./api"`

- [x] **Step 3: Tulis `web/lib/types.ts`**

```ts
/** Shapes the API actually returns. Mirrors api/schemas.py and the tool payloads. */

export interface Fact {
  id: string;
  label: string;
  value: number | string;
  unit: string;
  source: string;
}

export interface KelurahanProperties {
  kel_id: string;
  kel_name: string;
  kec_id: string;
  kec_name: string;
  kota_id: string;
  kota_name: string;
  lst_c_mean: number | null;
  lst_anomaly_c: number | null;
  hvi: number | null;
  hvi_rank: number | null;
  H: number | null;
  E: number | null;
  S: number | null;
  A: number | null;
  ndvi_mean: number | null;
  tree_frac_mean: number | null;
  built_frac_mean: number | null;
  pop: number | null;
  pop_density: number | null;
  exposed_vulnerable: number | null;
}

export interface KelurahanFeature {
  type: 'Feature';
  properties: KelurahanProperties;
  geometry: { type: 'MultiPolygon'; coordinates: number[][][][] };
}

export interface KelurahanCollection {
  type: 'FeatureCollection';
  features: KelurahanFeature[];
  attribution: string;
}

export interface Driver {
  feature: string;
  label: string;
  contribution_c: number;
  direction: 'memanaskan' | 'mendinginkan';
}

export interface AreaProfile {
  kel_id: string;
  kel_name: string;
  kec_name: string;
  kota_name: string;
  lst: number;
  lst_anomaly: number;
  hvi: number;
  hvi_rank: number;
  ndvi: number;
  tree_frac: number;
  built_frac: number;
  water_frac: number;
  pop: number;
  vulnerable: number;
  exposed_vulnerable: number;
  H: number;
  E: number;
  S: number;
  A: number;
}

export interface ProfileResponse {
  profile: AreaProfile;
  total_kelurahan: number;
  note: string;
  drivers: Driver[];
  drivers_unavailable?: string;
  facts: Fact[];
}

export type InterventionType = 'tree_planting' | 'cool_roof' | 'green_roof';
export type Level = 'low' | 'medium' | 'high';

export interface InterventionInput {
  type: InterventionType;
  level?: Level;
  params?: Record<string, number>;
}

export interface ScenarioResult {
  kel_id: string;
  delta_lst_c: number;
  delta_lst_pop_weighted_c: number;
  vulnerable_benefiting: number;
  area_m2: number;
  area_by_type: Record<string, number>;
  cost_idr: number;
  extrapolation: boolean;
  extrapolated_features: string[];
  n_cells: number;
}

export interface EvidenceEntry {
  id: string;
  intervention: string;
  metric: string;
  value_min: number;
  value_max: number;
  unit: string;
  context: string;
  source_title: string;
  year: number;
  url_or_doi: string;
  comparable_to_model: boolean;
}

export interface SimulateResponse {
  results: ScenarioResult[];
  interventions: InterventionInput[];
  evidence: EvidenceEntry[];
  note: string;
  map_highlight: string[];
  facts: Fact[];
}

export interface PortfolioPackage {
  kel_id: string;
  kel_name: string;
  intervention_type: InterventionType;
  level: Level;
  cost_idr: number;
  delta_lst_c: number;
  vulnerable_benefiting: number;
  area_m2: number;
  in_top_hvi_quintile: boolean;
}

export interface OptimizeResponse {
  packages: PortfolioPackage[];
  total_cost_idr: number;
  budget_idr: number;
  equity_share_requested: number;
  equity_share_achieved: number;
  solver_status: string;
  note: string;
  map_highlight: string[];
  facts: Fact[];
}

export interface ModelCard {
  version: string;
  target: string;
  target_caveat: string;
  data_period: string;
  area: string;
  n_train_cells: number;
  n_kelurahan: number;
  features: string[];
  validation: {
    scheme: string;
    why: string;
    summary: { r2_mean: number; r2_min: number; rmse_mean: number; mae_mean: number };
    target_r2: number;
    meets_target: boolean;
  };
  independent_checks: Record<string, string>;
  limitations: string[];
}

export interface RoofAnalysis {
  roof_visible: boolean;
  roof_form: 'flat' | 'pitched' | 'mixed' | 'unknown';
  material: string;
  color_tone: 'light' | 'medium' | 'dark';
  condition: string;
  shade_from_trees: 'none' | 'partial' | 'heavy';
  confidence: number;
  notes: string;
}

export interface RoofRecommendation {
  action: string;
  priority: string;
  reason: string;
  safety: string[];
  evidence_ids: string[];
}

export interface RoofResponse {
  roof: RoofAnalysis;
  recommendation: RoofRecommendation;
  evidence: EvidenceEntry[];
  guidance: string;
  kelurahan: string | null;
  facts: Fact[];
}
```

- [x] **Step 4: Tulis `web/lib/api.ts`**

```ts
/**
 * Typed client for the TEDUH API.
 *
 * Unwraps the {success, data, error} envelope in one place and preserves the server's
 * Indonesian message when something fails. That matters: the API already writes an
 * explanation a planner can act on ("Coba naikkan anggaran atau turunkan porsi keadilan"),
 * and replacing it with a generic failure string throws away the only useful thing that
 * would have been on screen.
 */

import type {
  KelurahanCollection,
  ModelCard,
  OptimizeResponse,
  ProfileResponse,
  RoofResponse,
  SimulateResponse,
} from './types';

export const API_BASE =
  process.env.NEXT_PUBLIC_TEDUH_API ?? 'http://localhost:8080';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(
      `Server tidak mengembalikan JSON (status ${response.status}).`,
      response.status,
    );
  }

  const envelope = body as Envelope<T>;
  if (envelope && typeof envelope === 'object' && 'success' in envelope) {
    if (envelope.success && envelope.data !== null) return envelope.data;
    throw new ApiError(
      envelope.error ?? `Permintaan gagal (status ${response.status}).`,
      response.status,
    );
  }

  // FastAPI validation errors (422) are not enveloped.
  throw new ApiError(
    `Permintaan tidak valid (status ${response.status}).`,
    response.status,
  );
}

function jsonPost(payload: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  };
}

export function fetchKelurahan(): Promise<KelurahanCollection> {
  return request<KelurahanCollection>('/api/kelurahan');
}

export function fetchProfile(kelId: string): Promise<ProfileResponse> {
  return request<ProfileResponse>(`/api/kelurahan/${encodeURIComponent(kelId)}`);
}

export function postSimulate(payload: {
  kel_ids: string[];
  interventions: { type: string; level?: string; params?: Record<string, number> }[];
}): Promise<SimulateResponse> {
  return request<SimulateResponse>('/api/simulate', jsonPost(payload));
}

export function postOptimize(payload: {
  scope?: string;
  budget_idr: number;
  equity_share?: number | null;
  allowed?: string[] | null;
}): Promise<OptimizeResponse> {
  return request<OptimizeResponse>('/api/optimize', jsonPost(payload));
}

export function fetchModelCard(): Promise<ModelCard> {
  return request<ModelCard>('/api/model-card');
}

export function postRoof(photo: File, kelurahan?: string): Promise<RoofResponse> {
  const form = new FormData();
  form.append('photo', photo);
  if (kelurahan) form.append('kelurahan', kelurahan);
  // No content-type header: the browser must set the multipart boundary itself.
  return request<RoofResponse>('/api/roof', { method: 'POST', body: form });
}

export function briefUrl(briefId: string, format: 'md' | 'pdf' = 'md'): string {
  return `${API_BASE}/api/brief/${encodeURIComponent(briefId)}?format=${format}`;
}
```

- [x] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 7 tes baru.

- [x] **Step 6: Verifikasi terhadap API yang hidup**

Pastikan `uv run uvicorn api.main:app --port 8080` berjalan, lalu:

```bash
cd web && node --input-type=module -e "
process.env.NEXT_PUBLIC_TEDUH_API='http://localhost:8080';
const { fetchKelurahan, fetchProfile } = await import('./lib/api.ts').catch(() => ({}));
" 2>/dev/null || curl -s localhost:8080/api/kelurahan | head -c 200
```

Cara paling sederhana: buka `http://localhost:8080/docs` dan panggil `/api/kelurahan` serta `/api/kelurahan/ID3173040002` dari Swagger UI, lalu bandingkan nama fieldnya dengan `web/lib/types.ts`. Setiap selisih nama di sini akan muncul sebagai `undefined` di peta, bukan sebagai error.

- [x] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/lib/
git commit -m "feat(web): tambah klien API bertipe yang mempertahankan pesan error server

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T4: Komponen SourceChip

**Files:**
- Create: `web/components/SourceChip.tsx`
- Create: `web/components/SourceChip.module.css`
- Test: `web/components/SourceChip.test.tsx`

**Interfaces:**
- Consumes: `lib/format` (M7-T2).
- Produces:
  - `SourceKind = 'data' | 'model' | 'literatur' | 'asumsi' | 'input'`
  - `SOURCE_KICKERS: Record<SourceKind, string>`
  - `kindForSource(source: string): SourceKind` — memetakan token `Fact.source` ke jenis chip
  - `SourceChip` — props: `value: string`, `unit?: string`, `kind: SourceKind`, `source: string`, `placement?: 'top' | 'bottom'`, `align?: 'center' | 'start' | 'end'`

Spesifikasi lengkap ada di `design/README.md` §Komponen kunci dan `design/SourceChip.dc.html`. Yang mengikat: garis bawah **dotted** 1 px `#5E6662` (**dashed** untuk `asumsi` dan `input`), ikon `info` 11 px, `cursor: help`, `tabIndex=0`, tooltip lebar 252 px dengan `role="tooltip"` yang muncul saat **hover maupun focus**.

- [x] **Step 1: Tulis tes yang gagal**

`web/components/SourceChip.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SourceChip, kindForSource } from './SourceChip';

describe('kindForSource', () => {
  it('maps the data token', () => {
    expect(kindForSource('data:grid_features@v1')).toBe('data');
  });

  it('maps the model token', () => {
    expect(kindForSource('model:lgbm@v1')).toBe('model');
  });

  it('maps an evidence token to literature', () => {
    expect(kindForSource('evidence:ev_ndvi_kl_2025')).toBe('literatur');
  });

  it('maps an assumption token', () => {
    expect(kindForSource('assumption:cool_roof.albedo_cool')).toBe('asumsi');
    expect(kindForSource('ASUMSI')).toBe('asumsi');
  });

  it('treats a literal citation as data rather than an assumption', () => {
    // A Kepgub citation is a real source; showing it as "ASUMSI · dapat diedit" would be
    // the opposite of the truth.
    expect(kindForSource('Kepgub DKI 811/2025, item 696.19, hlm 1262')).toBe('data');
  });
});

describe('SourceChip', () => {
  it('renders the value and unit together', () => {
    render(<SourceChip value="44,61" unit="°C" kind="data" source="Data satelit" />);
    expect(screen.getByText(/44,61/)).toBeInTheDocument();
  });

  it('is reachable by keyboard', () => {
    render(<SourceChip value="0,93" kind="data" source="Data satelit" />);
    expect(screen.getByRole('button')).toHaveAttribute('tabindex', '0');
  });

  it('shows the tooltip on focus, not only on hover', async () => {
    // Accessibility: a mouse-only tooltip hides the provenance from keyboard and
    // screen-reader users, which is the whole feature.
    const user = userEvent.setup();
    render(<SourceChip value="0,93" kind="data" source="Data satelit TEDUH" />);

    await user.tab();

    expect(screen.getByRole('tooltip')).toHaveTextContent('Data satelit TEDUH');
  });

  it('shows the tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="0,93" kind="model" source="Model TEDUH" />);

    await user.hover(screen.getByRole('button'));

    expect(screen.getByRole('tooltip')).toHaveTextContent('Model TEDUH');
  });

  it('labels each kind with its own kicker', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="95.000" kind="asumsi" source="Harga satuan TEDUH" />);

    await user.tab();

    expect(screen.getByRole('tooltip')).toHaveTextContent('ASUMSI');
  });

  it('uses a dashed underline for an assumption and dotted otherwise', () => {
    const { rerender } = render(
      <SourceChip value="1" kind="data" source="x" />,
    );
    const dotted = screen.getByRole('button').className;

    rerender(<SourceChip value="1" kind="asumsi" source="x" />);
    expect(screen.getByRole('button').className).not.toBe(dotted);
  });

  it('hides the tooltip again on blur', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="1" kind="data" source="x" />);

    await user.tab();
    await user.tab();

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./SourceChip"`

- [x] **Step 3: Tulis `web/components/SourceChip.module.css`**

```css
.chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  position: relative;
  border: 0;
  padding: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  cursor: help;
  border-bottom: 1px dotted var(--color-ink-secondary);
}

/* design/README.md: assumptions and user input are dashed, so an editable figure is
   distinguishable from a measured one at a glance, without reading the tooltip. */
.dashed {
  border-bottom-style: dashed;
}

.icon {
  color: var(--color-ink-secondary);
  flex: none;
}

.tooltip {
  position: absolute;
  z-index: 40;
  width: 252px;
  padding: 8px 10px;
  background: var(--color-ink);
  color: #fff;
  font-size: var(--text-help);
  font-weight: 400;
  line-height: var(--leading-caption);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-tooltip);
  text-align: left;
  pointer-events: none;
}

.top {
  bottom: calc(100% + 8px);
}

.bottom {
  top: calc(100% + 8px);
}

.center {
  left: 50%;
  transform: translateX(-50%);
}

.start {
  left: 0;
}

.end {
  right: 0;
}

.kicker {
  display: block;
  margin-bottom: 3px;
  font-size: var(--text-attribution);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-leaf);
}

.kickerAssumption {
  color: var(--color-border);
}
```

- [x] **Step 4: Tulis `web/components/SourceChip.tsx`**

```tsx
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
import styles from './SourceChip.module.css';

export type SourceKind = 'data' | 'model' | 'literatur' | 'asumsi' | 'input';

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
}

export function SourceChip({
  value,
  unit,
  kind,
  source,
  placement = 'top',
  align = 'center',
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
            {SOURCE_KICKERS[kind]}
          </span>
          {source}
        </span>
      )}
    </button>
  );
}
```

- [x] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 13 tes baru.

- [x] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah SourceChip dengan tooltip yang aktif saat focus

Provenance adalah klaim utama produk ini, jadi tooltip yang hanya muncul saat hover
akan menyembunyikannya dari pengguna yang paling butuh.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T5: Header dengan pemilih lapisan

**Files:**
- Create: `web/components/Header.tsx`
- Create: `web/components/Header.module.css`
- Test: `web/components/Header.test.tsx`

**Interfaces:**
- Consumes: `lib/layers` (`LAYERS`, `LAYER_ORDER`, `LayerId`) (M7-T2).
- Produces:
  - `Header` — props: `layer: LayerId`, `onLayerChange: (id: LayerId) => void`, `lang: 'id' | 'en'`, `onLangChange: (lang: 'id' | 'en') => void`, `query: string`, `onQueryChange: (q: string) => void`, `onSearchSubmit: (q: string) => void`

Spesifikasi presisi di `design/README.md` §1: tinggi 60 px, `bg #FFFFFF`, `border-bottom 1px #E3DED4`, padding `0 20px`, gap 24 px. Logo kotak 32×32 radius 8 `#1F5C4A` dengan ikon Lucide `tree-deciduous` 18 px putih. Segmented control `role="group"` dengan `aria-pressed`. Pencarian 236×38. Toggle ID/EN. Tombol "Tentang & Sumber Data" dengan ikon `book-open`.

- [x] **Step 1: Tulis tes yang gagal**

`web/components/Header.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Header } from './Header';

function setup(overrides = {}) {
  const props = {
    layer: 'hvi' as const,
    onLayerChange: vi.fn(),
    lang: 'id' as const,
    onLangChange: vi.fn(),
    query: '',
    onQueryChange: vi.fn(),
    onSearchSubmit: vi.fn(),
    ...overrides,
  };
  render(<Header {...props} />);
  return props;
}

describe('Header', () => {
  it('offers all four layers', () => {
    setup();
    const group = screen.getByRole('group', { name: /lapisan/i });
    expect(group.querySelectorAll('button')).toHaveLength(4);
  });

  it('marks the active layer with aria-pressed', () => {
    setup({ layer: 'lst' });
    expect(screen.getByRole('button', { name: /suhu permukaan/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: /vegetasi/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('reports a layer change', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.click(screen.getByRole('button', { name: /vegetasi/i }));

    expect(props.onLayerChange).toHaveBeenCalledWith('veg');
  });

  it('states the coverage next to the brand', () => {
    setup();
    expect(screen.getByText(/DKI Jakarta/)).toBeInTheDocument();
  });

  it('submits the search on Enter', async () => {
    const user = userEvent.setup();
    const props = setup({ query: 'Kampung Rawa' });

    await user.type(screen.getByPlaceholderText(/cari kelurahan/i), '{Enter}');

    expect(props.onSearchSubmit).toHaveBeenCalledWith('Kampung Rawa');
  });

  it('reports typing in the search box', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.type(screen.getByPlaceholderText(/cari kelurahan/i), 'S');

    expect(props.onQueryChange).toHaveBeenCalledWith('S');
  });

  it('toggles the language', async () => {
    const user = userEvent.setup();
    const props = setup({ lang: 'id' });

    await user.click(screen.getByRole('button', { name: 'EN' }));

    expect(props.onLangChange).toHaveBeenCalledWith('en');
  });

  it('marks the active language', () => {
    setup({ lang: 'id' });
    expect(screen.getByRole('button', { name: 'ID' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('links to the sources page', () => {
    setup();
    expect(screen.getByRole('link', { name: /sumber data/i })).toHaveAttribute(
      'href',
      '/sumber-data',
    );
  });

  it('labels the navigation for screen readers', () => {
    setup();
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./Header"`

- [x] **Step 3: Tulis `web/components/Header.module.css`**

```css
.header {
  display: flex;
  align-items: center;
  gap: var(--space-11);
  height: var(--header-height);
  padding: 0 var(--space-9);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  flex: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--color-canopy);
  color: #fff;
  flex: none;
}

.wordmark {
  font-size: var(--text-logo);
  font-weight: 700;
  letter-spacing: 0.14em;
  line-height: 1.1;
}

.coverage {
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.group {
  display: flex;
  gap: var(--space-1);
  padding: 3px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.layerButton {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 34px;
  padding: 0 var(--space-6);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-ink);
  font-size: var(--text-control);
  font-weight: 500;
  white-space: nowrap;
}

.layerButton:hover {
  background: var(--color-surface-hover);
}

.layerButton[aria-pressed='true'] {
  background: var(--color-surface);
  border-color: var(--color-canopy);
  color: var(--color-canopy);
  font-weight: 600;
}

.swatch {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-swatch);
  flex: none;
}

.spacer {
  flex: 1;
}

.search {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 236px;
  height: 38px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-ink-secondary);
}

.search:focus-within {
  border-color: var(--color-canopy);
}

.search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: none;
  font: inherit;
  color: var(--color-ink);
  outline: none;
}

.langButton {
  min-width: 38px;
  height: 30px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-ink-secondary);
  font-size: var(--text-help);
  font-weight: 700;
}

.langButton[aria-pressed='true'] {
  background: var(--color-canopy);
  color: #fff;
}

.about {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  height: 38px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-ink);
  font-size: var(--text-control);
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.about:hover {
  background: var(--color-paper);
  border-color: var(--color-border-strong);
}
```

- [x] **Step 4: Tulis `web/components/Header.tsx`**

```tsx
'use client';

/**
 * Top bar: brand, layer picker, search, language toggle, sources link.
 *
 * The layer picker is a real segmented control with aria-pressed rather than a select,
 * because switching layers is the single most frequent action on this screen and the
 * colour swatches are what make the choropleth legible without reading the labels.
 */

import { BookOpen, Search, TreeDeciduous } from 'lucide-react';
import Link from 'next/link';
import { LAYERS, LAYER_ORDER, type LayerId } from '@/lib/layers';
import styles from './Header.module.css';

interface HeaderProps {
  layer: LayerId;
  onLayerChange: (id: LayerId) => void;
  lang: 'id' | 'en';
  onLangChange: (lang: 'id' | 'en') => void;
  query: string;
  onQueryChange: (query: string) => void;
  onSearchSubmit: (query: string) => void;
}

export function Header({
  layer,
  onLayerChange,
  lang,
  onLangChange,
  query,
  onQueryChange,
  onSearchSubmit,
}: HeaderProps) {
  return (
    <header className={styles.header} role="banner">
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true">
          <TreeDeciduous size={18} />
        </span>
        <span>
          <span className={styles.wordmark}>TEDUH</span>
          <br />
          <span className={styles.coverage}>DKI Jakarta · kelurahan</span>
        </span>
      </div>

      <div className={styles.group} role="group" aria-label="Lapisan peta">
        {LAYER_ORDER.map((id) => (
          <button
            key={id}
            type="button"
            className={styles.layerButton}
            aria-pressed={layer === id}
            onClick={() => onLayerChange(id)}
          >
            <span
              className={styles.swatch}
              style={{ background: LAYERS[id].swatch }}
              aria-hidden="true"
            />
            {LAYERS[id].label}
          </button>
        ))}
      </div>

      <div className={styles.spacer} />

      <div className={styles.search}>
        <Search size={16} aria-hidden="true" />
        <input
          type="search"
          placeholder="Cari kelurahan…"
          aria-label="Cari kelurahan"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onSearchSubmit(query);
          }}
        />
      </div>

      <div className={styles.group} role="group" aria-label="Bahasa">
        {(['id', 'en'] as const).map((code) => (
          <button
            key={code}
            type="button"
            className={styles.langButton}
            aria-pressed={lang === code}
            onClick={() => onLangChange(code)}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>

      <Link href="/sumber-data" className={styles.about}>
        <BookOpen size={16} stroke="var(--color-canopy)" aria-hidden="true" />
        Tentang &amp; Sumber Data
      </Link>
    </header>
  );
}
```

- [x] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 10 tes baru.

- [x] **Step 6: Bandingkan dengan prototipe desain secara visual**

Buka `design/TEDUH Layar Utama.dc.html` di browser bersebelahan dengan `http://localhost:3000`. Periksa: tinggi header 60 px, swatch 10×10, tombol lapisan aktif berbingkai hijau, lebar pencarian 236 px, dan jarak antar kelompok 24 px.

- [x] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah header dengan pemilih lapisan tersegmentasi

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M7a selesai

- [x] `npm run dev` menyajikan halaman bertema dengan font dan latar dari token desain.
- [x] `npm test` hijau (≥ 54 tes).
- [x] Setiap token di `design/README.md` §Design Tokens ada sebagai CSS custom property.
- [x] Angka diformat gaya `id-ID` dengan tanda minus U+2212 dan `tabular-nums`.
- [x] Batas kelas LST dan kepadatan penduduk **dihitung dari data nyata**, bukan dari data contoh desain, dan sumbernya dicatat di komentar.
- [x] `SourceChip` menampilkan tooltip saat hover **dan** focus, dengan garis bawah dashed untuk asumsi.
- [x] Header menandai lapisan dan bahasa aktif dengan `aria-pressed`.

**Selanjutnya:** [`m7b-web-features.md`](m7b-web-features.md) — peta, drawer, dok skenario, panel agen, dan halaman.
