# M7b — Fitur Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M7a selesai** (token, `lib/format`, `lib/layers`, `lib/api`, `SourceChip`, `Header`), dan API M3c hidup. Panel agen (M7-T10) butuh **M4**; halaman Cek Atap (M7-T13) butuh **M6**.
>
> **Sumber kebenaran desain: `design/README.md`.** Buka `design/TEDUH Layar Utama.dc.html` di browser sebelum menulis komponen apa pun — spesifikasi tertulis tidak menggantikan melihat perilakunya.

**Goal:** Layar utama yang berfungsi: peta choropleth 264 kelurahan, drawer profil, dok simulasi skenario, panel agen dengan streaming, plus halaman `/cek-atap` dan `/sumber-data`.

**Architecture:** `app/page.tsx` memegang seluruh state dan meneruskannya ke bawah sebagai props; tidak ada state management library. Alasannya: statenya kecil dan datar (`design/README.md` §State Management mendaftar delapan nilai), dan satu sumber state membuat alur "klik baris tabel → sorot peta → buka drawer → geser peta" bisa dibaca di satu berkas. Kartu hasil di chat dirender dari output tool terstruktur, **bukan** dari teks LLM, supaya angka di kartu selalu angka terverifikasi.

**Tech Stack:** MapLibre GL JS, React 19, Lucide React, Vitest + Testing Library.

## Global Constraints

- **Setiap angka memakai `SourceChip`.** Tidak ada angka telanjang di UI mana pun.
- Teks UI Bahasa Indonesia. Tanda minus U+2212. `tabular-nums`.
- **Kartu hasil dirender dari output tool**, bukan diparsing dari prosa LLM (`design/README.md` §State Management).
- Animasi hanya `transform`/`opacity`. Drawer slide-in 200 ms; pan peta 300 ms lewat `map.easeTo`.
- Fokus terlihat; tooltip aktif saat hover **dan** focus.
- `/cek-atap` ramah ponsel; layar utama target minimal 1280 px.
- ΔLST selalu berlabel "indikatif" dan "suhu permukaan" di UI.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Angka nyata, bukan data contoh desain

264 kelurahan · rata-rata LST kota **41,84 °C** · WorldPop **2025** · lima prioritas nyata: Kampung Rawa `ID3173040002`, Serdang `ID3173060004`, Johar Baru `ID3173040001`, Galur `ID3173040004`, Krendang `ID3174050005`. Badge "Data contoh" dari desain **dihapus** begitu komponen memakai API nyata; ganti dengan label "Indikatif" hanya pada hasil simulasi.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `web/components/MapView.tsx` | MapLibre: choropleth, hover, klik, sorotan prioritas, pan. |
| `web/components/MapOverlays.tsx` | Kartu judul, kontrol zoom, legenda, atribusi. |
| `web/components/KelurahanDrawer.tsx` | Profil lengkap: kartu angka, komponen HVI, SHAP, tutupan lahan. |
| `web/components/ScenarioDock.tsx` | Tiga slider, input anggaran, tombol Simulasikan. |
| `web/lib/agent.ts` | Klien SSE untuk endpoint ADK. Murni, tanpa React. |
| `web/components/AgentPanel.tsx` | Thread chat, blok langkah kerja, composer. |
| `web/components/ResultTable.tsx` | Kartu tabel hasil tool di dalam chat. |
| `web/app/page.tsx` | Pemegang state tunggal dan perakitan tata letak. |
| `web/app/cek-atap/page.tsx` | Unggah foto atap, ramah ponsel. |
| `web/app/sumber-data/page.tsx` | Atribusi data dan model card. |

---

## Task M7-T6: Peta choropleth

**Files:**
- Create: `web/components/MapView.tsx`
- Create: `web/lib/mapStyle.ts`
- Test: `web/lib/mapStyle.test.ts`

**Interfaces:**
- Consumes: `lib/layers` (`LAYERS`, `colorForValue`, `NO_DATA_COLOR`), `lib/types` (`KelurahanCollection`).
- Produces:
  - `mapStyle.ts`: `JAKARTA_BOUNDS`, `JAKARTA_CENTER`, `BASE_STYLE`, `SOURCE_ID`, `LAYER_IDS`, `fillColorExpression(layer: LayerDefinition): unknown[]`, `centroidOf(feature: KelurahanFeature): [number, number]`
  - `MapView` — props: `collection`, `layer`, `selectedId`, `hoverId`, `priorityIds`, `showPriority`, `onHover`, `onSelect`, `drawerOpen`

**Keputusan:** basemap **tidak** dipakai sebagai tile raster. Peta hanya menggambar poligon kelurahan di atas latar `#EFEBE3` dengan laut `#DFE6E4`, persis seperti prototipe desain. Itu menghilangkan dependensi jaringan ke penyedia tile saat penilaian, membuat peta tampil instan, dan tetap sesuai desain — atribusi OpenFreeMap/OSM di desain berlaku untuk basemap yang tidak kita pakai, jadi atribusi diganti menjadi sumber data yang benar-benar dipakai (dikembalikan oleh `/api/kelurahan` di field `attribution`).

- [ ] **Step 1: Tulis tes yang gagal**

`web/lib/mapStyle.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { LAYERS, NO_DATA_COLOR } from './layers';
import { JAKARTA_BOUNDS, centroidOf, fillColorExpression } from './mapStyle';

describe('fillColorExpression', () => {
  it('builds a step expression over the layer property', () => {
    const expression = fillColorExpression(LAYERS.hvi) as unknown[];
    expect(expression[0]).toBe('case');
    // The flattened step expression must mention the painted property.
    expect(JSON.stringify(expression)).toContain('hvi');
  });

  it('includes every palette colour', () => {
    const encoded = JSON.stringify(fillColorExpression(LAYERS.lst));
    for (const colour of LAYERS.lst.palette) {
      expect(encoded).toContain(colour);
    }
  });

  it('paints a null value with the no-data colour', () => {
    // 28 low-quality cells exist and some kelurahan can lack a metric. Painting them as
    // the coolest class would be a quiet lie on the map.
    expect(JSON.stringify(fillColorExpression(LAYERS.lst))).toContain(NO_DATA_COLOR);
  });

  it('puts one threshold per break', () => {
    const encoded = JSON.stringify(fillColorExpression(LAYERS.veg));
    for (const threshold of LAYERS.veg.breaks) {
      expect(encoded).toContain(String(threshold));
    }
  });
});

describe('centroidOf', () => {
  it('averages the outer ring of the largest polygon', () => {
    const feature = {
      type: 'Feature' as const,
      properties: {} as never,
      geometry: {
        type: 'MultiPolygon' as const,
        coordinates: [[[[106.8, -6.2], [106.9, -6.2], [106.9, -6.1], [106.8, -6.1]]]],
      },
    };
    const [lon, lat] = centroidOf(feature);
    expect(lon).toBeCloseTo(106.85, 2);
    expect(lat).toBeCloseTo(-6.15, 2);
  });

  it('ignores the smaller polygons of a multipart kelurahan', () => {
    // Several Jakarta kelurahan have slivers across a river; a marker in the sliver looks
    // like a bug.
    const feature = {
      type: 'Feature' as const,
      properties: {} as never,
      geometry: {
        type: 'MultiPolygon' as const,
        coordinates: [
          [[[106.0, -6.0], [106.001, -6.0], [106.001, -6.001], [106.0, -6.001]]],
          [[[106.8, -6.2], [106.9, -6.2], [106.9, -6.1], [106.8, -6.1]]],
        ],
      },
    };
    const [lon] = centroidOf(feature);
    expect(lon).toBeGreaterThan(106.5);
  });
});

describe('JAKARTA_BOUNDS', () => {
  it('covers the real grid extent', () => {
    // pipeline/build_grid.py: lon 106.686..106.972, lat -6.370..-6.090.
    const [[west, south], [east, north]] = JAKARTA_BOUNDS;
    expect(west).toBeLessThanOrEqual(106.686);
    expect(east).toBeGreaterThanOrEqual(106.972);
    expect(south).toBeLessThanOrEqual(-6.37);
    expect(north).toBeGreaterThanOrEqual(-6.09);
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./mapStyle"`

- [ ] **Step 3: Tulis `web/lib/mapStyle.ts`**

```ts
/**
 * MapLibre style and geometry helpers.
 *
 * There is no raster basemap. The map draws kelurahan polygons on a flat paper background,
 * exactly as the design prototype does. That removes a network dependency on a tile
 * provider during judging, makes the map appear instantly, and loses nothing: the product
 * shows administrative choropleths, not streets. The attribution shown is therefore the
 * data attribution returned by /api/kelurahan, not an OpenFreeMap credit for tiles we
 * never request.
 */

import type { StyleSpecification } from 'maplibre-gl';
import { NO_DATA_COLOR, type LayerDefinition } from './layers';
import type { KelurahanFeature } from './types';

/** Real grid extent from pipeline/build_grid.py, padded slightly. */
export const JAKARTA_BOUNDS: [[number, number], [number, number]] = [
  [106.65, -6.4],
  [107.0, -6.06],
];

export const JAKARTA_CENTER: [number, number] = [106.83, -6.23];

export const SOURCE_ID = 'kelurahan';

export const LAYER_IDS = {
  fill: 'kelurahan-fill',
  outline: 'kelurahan-outline',
  hover: 'kelurahan-hover',
  selected: 'kelurahan-selected',
  priorityHalo: 'priority-halo',
  priorityOutline: 'priority-outline',
} as const;

export const BASE_STYLE: StyleSpecification = {
  version: 8,
  // No sprite and no glyph server: all labels are HTML overlays, so the map needs no
  // external asset at all.
  sources: {},
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#EFEBE3' },
    },
  ],
};

/**
 * A MapLibre paint expression mapping the layer's property onto its palette.
 *
 * Wrapped in `case` so a null property falls to NO_DATA_COLOR instead of being coerced to
 * 0 and painted as the lowest class.
 */
export function fillColorExpression(layer: LayerDefinition): unknown[] {
  const step: unknown[] = ['step', ['get', layer.property], layer.palette[0]];
  layer.breaks.forEach((threshold, index) => {
    step.push(threshold, layer.palette[index + 1]);
  });

  return [
    'case',
    ['==', ['get', layer.property], null],
    NO_DATA_COLOR,
    step,
  ];
}

function ringCentroid(ring: number[][]): [number, number] {
  let lon = 0;
  let lat = 0;
  for (const [x, y] of ring) {
    lon += x;
    lat += y;
  }
  return [lon / ring.length, lat / ring.length];
}

function ringArea(ring: number[][]): number {
  let total = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    total += x1 * y2 - x2 * y1;
  }
  return Math.abs(total) / 2;
}

/**
 * Marker position for a kelurahan: the centroid of its LARGEST polygon.
 *
 * Several Jakarta kelurahan carry slivers across a river or a rail line. Averaging all
 * parts drops the numbered priority marker into open water, which reads as a bug.
 */
export function centroidOf(feature: KelurahanFeature): [number, number] {
  const polygons = feature.geometry.coordinates;
  let best = polygons[0][0];
  let bestArea = -1;

  for (const polygon of polygons) {
    const outer = polygon[0];
    const area = ringArea(outer);
    if (area > bestArea) {
      bestArea = area;
      best = outer;
    }
  }
  return ringCentroid(best);
}
```

- [ ] **Step 4: Tulis `web/components/MapView.tsx`**

```tsx
'use client';

/**
 * The choropleth.
 *
 * Hover and selection are driven by feature state rather than by re-setting the GeoJSON
 * source, because re-setting 264 MultiPolygons on every mouse move drops frames badly.
 * The priority markers are HTML elements positioned by map.project() rather than symbol
 * layers, which avoids needing a glyph server for five numbers.
 */

import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { LAYERS, type LayerId } from '@/lib/layers';
import {
  BASE_STYLE,
  JAKARTA_BOUNDS,
  JAKARTA_CENTER,
  LAYER_IDS,
  SOURCE_ID,
  centroidOf,
  fillColorExpression,
} from '@/lib/mapStyle';
import type { KelurahanCollection, KelurahanProperties } from '@/lib/types';
import styles from './MapView.module.css';

const PAN_DURATION_MS = 300;

/** Half the drawer width, so the selected kelurahan ends up centred in the visible map. */
const DRAWER_PAN_OFFSET_PX = 210;

interface MapViewProps {
  collection: KelurahanCollection | null;
  layer: LayerId;
  selectedId: string | null;
  hoverId: string | null;
  priorityIds: string[];
  showPriority: boolean;
  drawerOpen: boolean;
  onHover: (kelId: string | null) => void;
  onSelect: (kelId: string) => void;
}

export function MapView({
  collection,
  layer,
  selectedId,
  hoverId,
  priorityIds,
  showPriority,
  drawerOpen,
  onHover,
  onSelect,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [markers, setMarkers] = useState<{ id: string; x: number; y: number; rank: number }[]>(
    [],
  );

  const definition = LAYERS[layer];

  const centroids = useMemo(() => {
    if (!collection) return new Map<string, [number, number]>();
    return new Map(
      collection.features.map((feature) => [
        feature.properties.kel_id,
        centroidOf(feature),
      ]),
    );
  }, [collection]);

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: JAKARTA_CENTER,
      zoom: 10.2,
      maxBounds: JAKARTA_BOUNDS,
      attributionControl: false,
    });
    mapRef.current = map;
    map.on('load', () => setReady(true));

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add the source and layers once both the map and the data exist.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !collection || map.getSource(SOURCE_ID)) return;

    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: collection,
      promoteId: 'kel_id',
    });

    map.addLayer({
      id: LAYER_IDS.fill,
      type: 'fill',
      source: SOURCE_ID,
      paint: { 'fill-color': fillColorExpression(definition) as never },
    });

    map.addLayer({
      id: LAYER_IDS.outline,
      type: 'line',
      source: SOURCE_ID,
      paint: { 'line-color': '#FFFFFF', 'line-width': 0.9 },
    });

    map.addLayer({
      id: LAYER_IDS.hover,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1C2321',
        'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 1.6, 0],
      },
    });

    map.addLayer({
      id: LAYER_IDS.selected,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1C2321',
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2.4, 0],
        'line-dasharray': [5, 3],
      },
    });

    // White halo beneath the green outline, per design/README.md §2.
    map.addLayer({
      id: LAYER_IDS.priorityHalo,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#FFFFFF',
        'line-width': ['case', ['boolean', ['feature-state', 'priority'], false], 6, 0],
      },
    });
    map.addLayer({
      id: LAYER_IDS.priorityOutline,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1F5C4A',
        'line-width': ['case', ['boolean', ['feature-state', 'priority'], false], 3.4, 0],
      },
    });

    let hovered: string | null = null;
    map.on('mousemove', LAYER_IDS.fill, (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const id = String(feature.id);
      if (hovered === id) return;
      if (hovered) {
        map.setFeatureState({ source: SOURCE_ID, id: hovered }, { hover: false });
      }
      hovered = id;
      map.setFeatureState({ source: SOURCE_ID, id }, { hover: true });
      map.getCanvas().style.cursor = 'pointer';
      onHover(id);
    });

    map.on('mouseleave', LAYER_IDS.fill, () => {
      if (hovered) {
        map.setFeatureState({ source: SOURCE_ID, id: hovered }, { hover: false });
      }
      hovered = null;
      map.getCanvas().style.cursor = '';
      onHover(null);
    });

    map.on('click', LAYER_IDS.fill, (event) => {
      const feature = event.features?.[0];
      if (feature) onSelect(String(feature.id));
    });
  }, [ready, collection, definition, onHover, onSelect]);

  // Repaint when the layer changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getLayer(LAYER_IDS.fill)) return;
    map.setPaintProperty(
      LAYER_IDS.fill,
      'fill-color',
      fillColorExpression(definition) as never,
    );
  }, [definition, ready]);

  // Mirror hover coming from outside the map, e.g. a chat result row.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { hover: id === hoverId });
    }
  }, [hoverId, ready, collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { selected: id === selectedId });
    }
  }, [selectedId, ready, collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    const active = new Set(showPriority ? priorityIds : []);
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { priority: active.has(id) });
    }
  }, [priorityIds, showPriority, ready, collection]);

  // Pan so the selected kelurahan is not hidden behind the drawer.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !selectedId) return;
    const target = centroids.get(selectedId);
    if (!target) return;
    map.easeTo({
      center: target,
      offset: drawerOpen ? [-DRAWER_PAN_OFFSET_PX, 0] : [0, 0],
      duration: PAN_DURATION_MS,
    });
  }, [selectedId, drawerOpen, centroids, ready]);

  // Project priority centroids into screen space for the numbered HTML markers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const reproject = () => {
      if (!showPriority) {
        setMarkers([]);
        return;
      }
      setMarkers(
        priorityIds.flatMap((id, index) => {
          const centre = centroids.get(id);
          if (!centre) return [];
          const point = map.project(centre);
          return [{ id, x: point.x, y: point.y, rank: index + 1 }];
        }),
      );
    };

    reproject();
    map.on('move', reproject);
    return () => {
      map.off('move', reproject);
    };
  }, [priorityIds, showPriority, centroids, ready]);

  return (
    <div className={styles.wrapper}>
      <div ref={containerRef} className={styles.canvas} aria-label="Peta kelurahan DKI Jakarta" />
      {markers.map((marker) => (
        <button
          key={marker.id}
          type="button"
          className={styles.marker}
          style={{ transform: `translate(${marker.x - 11}px, ${marker.y - 11}px)` }}
          onClick={() => onSelect(marker.id)}
          onMouseEnter={() => onHover(marker.id)}
          onMouseLeave={() => onHover(null)}
          aria-label={`Prioritas ${marker.rank}`}
        >
          {marker.rank}
        </button>
      ))}
    </div>
  );
}

export type { KelurahanProperties };
```

`web/components/MapView.module.css`:

```css
.wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
  background: var(--color-map-bg);
}

.canvas {
  position: absolute;
  inset: 0;
}

.marker {
  position: absolute;
  top: 0;
  left: 0;
  width: 22px;
  height: 22px;
  border: 2px solid #fff;
  border-radius: var(--radius-pill);
  background: var(--color-canopy);
  color: #fff;
  font-size: var(--text-kicker);
  font-weight: 700;
  line-height: 1;
  display: grid;
  place-items: center;
  /* Only transform animates, so panning stays on the compositor. */
  will-change: transform;
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 7 tes baru. `MapView` sendiri tidak di-unit-test — MapLibre butuh WebGL yang tidak ada di jsdom; perilakunya diperiksa manual di Step 6 dan lewat Playwright di M8.

- [ ] **Step 6: Verifikasi di browser**

Sambungkan sementara di `web/app/page.tsx`:

```tsx
'use client';

import { useEffect, useState } from 'react';
import { MapView } from '@/components/MapView';
import { fetchKelurahan } from '@/lib/api';
import type { KelurahanCollection } from '@/lib/types';

export default function Home() {
  const [collection, setCollection] = useState<KelurahanCollection | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    fetchKelurahan().then(setCollection).catch(console.error);
  }, []);

  return (
    <main style={{ display: 'flex', height: '100vh' }}>
      <MapView
        collection={collection}
        layer="hvi"
        selectedId={selectedId}
        hoverId={hoverId}
        priorityIds={['ID3173040002', 'ID3173060004', 'ID3173040001', 'ID3173040004', 'ID3174050005']}
        showPriority
        drawerOpen={false}
        onHover={setHoverId}
        onSelect={setSelectedId}
      />
    </main>
  );
}
```

Run: `cd web && npm run dev`
Expected: 264 poligon tergambar dengan palet HVI ungu, lima penanda bernomor di Jakarta Pusat dan Barat, hover memberi outline gelap, klik memusatkan peta.

Ganti `layer="hvi"` menjadi `"lst"` dan pastikan petanya **tidak** satu warna rata — kalau rata, batas kelas LST di `lib/layers.ts` masih memakai angka data contoh desain; kembali ke M7a Task M7-T2 Step 1.

- [ ] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/
git commit -m "feat(web): tambah peta choropleth kelurahan dengan sorotan prioritas

Hover dan seleksi memakai feature-state, bukan set ulang GeoJSON, supaya 264
MultiPolygon tidak dirender ulang setiap gerakan mouse.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T7: Overlay peta

**Files:**
- Create: `web/components/MapOverlays.tsx`, `web/components/MapOverlays.module.css`
- Test: `web/components/MapOverlays.test.tsx`

**Interfaces:**
- Consumes: `lib/layers`, `lib/format`.
- Produces: `MapOverlays` — props: `layer: LayerId`, `scopeLabel: string`, `attribution: string`, `priorityCount: number`, `drawerOpen: boolean`, `onZoomIn`, `onZoomOut`

Spesifikasi `design/README.md` §2 Overlay: kartu kiri-atas (kicker uppercase + judul lapisan 14/600), kontrol zoom 36×36 kanan-atas, legenda 312 px kanan-bawah (judul 13/600, sub 11,5, ramp 14 px, tick tabular 11 px), atribusi 10,5 px. Saat drawer terbuka, overlay kanan bergeser ke `right: 436px`.

- [ ] **Step 1: Tulis tes yang gagal**

`web/components/MapOverlays.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { LAYERS } from '@/lib/layers';
import { MapOverlays } from './MapOverlays';

function setup(overrides = {}) {
  const props = {
    layer: 'hvi' as const,
    scopeLabel: 'DKI JAKARTA',
    attribution: 'Batas: HDX COD-AB · LST: USGS Landsat 8/9',
    priorityCount: 0,
    drawerOpen: false,
    onZoomIn: vi.fn(),
    onZoomOut: vi.fn(),
    ...overrides,
  };
  render(<MapOverlays {...props} />);
  return props;
}

describe('MapOverlays', () => {
  it('shows the active layer title', () => {
    setup({ layer: 'lst' });
    expect(screen.getByText(LAYERS.lst.title)).toBeInTheDocument();
  });

  it('shows the legend title and subtitle for the active layer', () => {
    setup({ layer: 'veg' });
    expect(screen.getByText(LAYERS.veg.legendTitle)).toBeInTheDocument();
    expect(screen.getByText(LAYERS.veg.legendSubtitle)).toBeInTheDocument();
  });

  it('warns that LST is not air temperature', () => {
    // The product's most important caveat must be on screen whenever LST is displayed,
    // not only inside a tooltip.
    setup({ layer: 'lst' });
    expect(screen.getByText(/bukan suhu udara/i)).toBeInTheDocument();
  });

  it('renders one legend swatch per palette colour', () => {
    setup({ layer: 'hvi' });
    expect(screen.getAllByTestId('legend-swatch')).toHaveLength(LAYERS.hvi.palette.length);
  });

  it('labels every class break', () => {
    setup({ layer: 'hvi' });
    for (const threshold of LAYERS.hvi.breaks) {
      expect(screen.getByText(new RegExp(String(threshold).replace('.', ',')))).toBeInTheDocument();
    }
  });

  it('adds a priority legend row only when priorities are highlighted', () => {
    const { unmount } = render(
      <MapOverlays
        layer="hvi"
        scopeLabel="DKI JAKARTA"
        attribution="x"
        priorityCount={0}
        drawerOpen={false}
        onZoomIn={vi.fn()}
        onZoomOut={vi.fn()}
      />,
    );
    expect(screen.queryByText(/prioritas dari jawaban agen/i)).not.toBeInTheDocument();
    unmount();

    setup({ priorityCount: 5 });
    expect(screen.getByText(/5 kelurahan prioritas dari jawaban agen/i)).toBeInTheDocument();
  });

  it('shows the data attribution', () => {
    setup();
    expect(screen.getByText(/HDX COD-AB/)).toBeInTheDocument();
  });

  it('zooms in and out', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.click(screen.getByRole('button', { name: /perbesar/i }));
    await user.click(screen.getByRole('button', { name: /perkecil/i }));

    expect(props.onZoomIn).toHaveBeenCalled();
    expect(props.onZoomOut).toHaveBeenCalled();
  });

  it('shifts the right-hand overlays when the drawer is open', () => {
    setup({ drawerOpen: true });
    // design/README.md: right: 436px while the drawer covers the map edge.
    expect(screen.getByTestId('legend')).toHaveStyle({ right: '436px' });
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./MapOverlays"`

- [ ] **Step 3: Tulis `web/components/MapOverlays.module.css`**

```css
.titleCard,
.zoom,
.legend,
.attribution {
  position: absolute;
  z-index: 10;
}

.titleCard {
  top: var(--space-8);
  left: var(--space-8);
  padding: var(--space-5) var(--space-7);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.layerTitle {
  font-size: var(--text-body);
  font-weight: 600;
}

.zoom {
  top: var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  transition: right var(--duration-drawer) var(--ease-out);
}

.zoomButton {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-card);
  color: var(--color-ink);
}

.zoomButton:hover {
  background: var(--color-paper);
}

.legend {
  bottom: var(--space-8);
  width: 312px;
  padding: var(--space-6) var(--space-7);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: right var(--duration-drawer) var(--ease-out);
}

.legendTitle {
  font-size: var(--text-secondary);
  font-weight: 600;
}

.legendSubtitle {
  margin-top: var(--space-1);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}

.ramp {
  display: flex;
  margin-top: var(--space-5);
  height: 14px;
  border-radius: var(--radius-swatch);
  overflow: hidden;
}

.swatch {
  flex: 1;
}

.ticks {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-2);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink-secondary);
}

.priorityRow {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-5);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border-row);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.prioritySwatch {
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-canopy);
  border-radius: var(--radius-swatch);
  background: transparent;
  flex: none;
}

.attribution {
  bottom: var(--space-3);
  left: var(--space-8);
  max-width: 48%;
  font-size: var(--text-attribution);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}
```

- [ ] **Step 4: Tulis `web/components/MapOverlays.tsx`**

```tsx
'use client';

/**
 * Everything floating above the map: scope card, zoom, legend, attribution.
 *
 * The legend reads its ramp, breaks, and copy from lib/layers so it cannot describe a
 * different layer than the one being painted. The right-hand overlays shift when the
 * drawer opens, per design/README.md §2.
 */

import { Minus, Plus } from 'lucide-react';
import { LAYERS, type LayerId } from '@/lib/layers';
import styles from './MapOverlays.module.css';

const DRAWER_OFFSET = '436px';
const EDGE_OFFSET = '16px';

interface MapOverlaysProps {
  layer: LayerId;
  scopeLabel: string;
  attribution: string;
  priorityCount: number;
  drawerOpen: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function MapOverlays({
  layer,
  scopeLabel,
  attribution,
  priorityCount,
  drawerOpen,
  onZoomIn,
  onZoomOut,
}: MapOverlaysProps) {
  const definition = LAYERS[layer];
  const right = drawerOpen ? DRAWER_OFFSET : EDGE_OFFSET;

  return (
    <>
      <div className={styles.titleCard}>
        <div className="kicker">{scopeLabel}</div>
        <div className={styles.layerTitle}>{definition.title}</div>
      </div>

      <div className={styles.zoom} style={{ right }}>
        <button type="button" className={styles.zoomButton} onClick={onZoomIn} aria-label="Perbesar peta">
          <Plus size={16} />
        </button>
        <button type="button" className={styles.zoomButton} onClick={onZoomOut} aria-label="Perkecil peta">
          <Minus size={16} />
        </button>
      </div>

      <div className={styles.legend} style={{ right }} data-testid="legend">
        <div className={styles.legendTitle}>{definition.legendTitle}</div>
        <div className={styles.legendSubtitle}>{definition.legendSubtitle}</div>

        <div className={styles.ramp}>
          {definition.palette.map((colour) => (
            <span
              key={colour}
              className={styles.swatch}
              style={{ background: colour }}
              data-testid="legend-swatch"
            />
          ))}
        </div>

        <div className={styles.ticks}>
          {definition.breaks.map((threshold) => (
            <span key={threshold}>{definition.format(threshold)}</span>
          ))}
        </div>

        {priorityCount > 0 && (
          <div className={styles.priorityRow}>
            <span className={styles.prioritySwatch} aria-hidden="true" />
            {priorityCount} kelurahan prioritas dari jawaban agen
          </div>
        )}
      </div>

      <div className={styles.attribution}>{attribution}</div>
    </>
  );
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 9 tes baru.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah overlay peta dengan legenda yang mengikuti lapisan aktif

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T8: Drawer profil kelurahan

**Files:**
- Create: `web/components/KelurahanDrawer.tsx`, `web/components/KelurahanDrawer.module.css`
- Test: `web/components/KelurahanDrawer.test.tsx`

**Interfaces:**
- Consumes: `lib/api.fetchProfile`, `lib/format`, `components/SourceChip` (`kindForSource`), `lib/types` (`ProfileResponse`, `Driver`).
- Produces: `KelurahanDrawer` — props: `kelId: string | null`, `onClose: () => void`, `onAskAgent: (prompt: string) => void`

Spesifikasi `design/README.md` §3. Lima blok isi: (1) grid 2×2 kartu angka, (2) empat bar komponen HVI dengan rumusnya, (3) grafik bar divergen SHAP dengan baris total, (4) bar bertumpuk tutupan lahan, (5) catatan kaki ⓘ. **Jumlah kontribusi SHAP harus sama dengan selisih yang ditampilkan** — kalau tidak, tampilkan peringatan, jangan diam-diam membulatkan.

- [ ] **Step 1: Tulis tes yang gagal**

`web/components/KelurahanDrawer.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { KelurahanDrawer } from './KelurahanDrawer';

const PROFILE = {
  profile: {
    kel_id: 'ID3173040002',
    kel_name: 'Kampung Rawa',
    kec_name: 'Johar Baru',
    kota_name: 'Kota Jakarta Pusat',
    lst: 44.605,
    lst_anomaly: 2.768,
    hvi: 0.9309,
    hvi_rank: 1,
    ndvi: 0.18,
    tree_frac: 0.0,
    built_frac: 0.93,
    water_frac: 0.0,
    pop: 8355.66,
    vulnerable: 1402.1,
    exposed_vulnerable: 1020.39,
    H: 1.0,
    E: 0.98,
    S: 0.91,
    A: 1.0,
  },
  total_kelurahan: 264,
  note: 'Suhu permukaan (LST) dari Landsat 8/9, bukan suhu udara.',
  drivers: [
    { feature: 'built_frac', label: 'Fraksi lahan terbangun', contribution_c: 1.2, direction: 'memanaskan' },
    { feature: 'tree_frac', label: 'Tutupan pohon', contribution_c: 0.8, direction: 'memanaskan' },
    { feature: 'water_frac', label: 'Fraksi badan air', contribution_c: -0.3, direction: 'mendinginkan' },
  ],
  facts: [
    { id: 'kel_ID3173040002.lst', label: 'Suhu permukaan rata-rata', value: 44.605, unit: 'degC', source: 'data:grid_features@v1' },
  ],
};

function mockProfile(payload = PROFILE) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ success: true, data: payload, error: null }) }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('KelurahanDrawer', () => {
  it('renders nothing when no kelurahan is selected', () => {
    render(<KelurahanDrawer kelId={null} onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is a labelled dialog', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
  });

  it('shows the name and the administrative location', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    await screen.findByText('Kampung Rawa');
    expect(screen.getByText(/Johar Baru/)).toBeInTheDocument();
    expect(screen.getByText(/Jakarta Pusat/)).toBeInTheDocument();
  });

  it('states the HVI rank out of the real total', async () => {
    // Never 267: that was the design's sample figure.
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/1 dari 264/)).toBeInTheDocument();
  });

  it('shows the anomaly with an explicit sign', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/\+2,77/)).toBeInTheDocument();
  });

  it('renders every number inside a source chip', async () => {
    // design/README.md: "Wajib dipakai untuk setiap angka di UI."
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    await screen.findByText('Kampung Rawa');
    const chips = screen.getAllByRole('button').filter((node) => node.className.includes('chip'));
    expect(chips.length).toBeGreaterThanOrEqual(8);
  });

  it('shows all four HVI components with the formula', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    await screen.findByText(/Bahaya/);
    expect(screen.getByText(/Keterpaparan/)).toBeInTheDocument();
    expect(screen.getByText(/Kepekaan/)).toBeInTheDocument();
    expect(screen.getByText(/kapasitas adaptif/i)).toBeInTheDocument();
    expect(screen.getByText(/HVI = /)).toBeInTheDocument();
  });

  it('lists the SHAP drivers with their direction', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText('Fraksi lahan terbangun')).toBeInTheDocument();
    expect(screen.getByText(/memanaskan/)).toBeInTheDocument();
  });

  it('warns when the driver contributions do not sum to the anomaly', async () => {
    // design/README.md: "Jumlah kontribusi harus = selisih LST (validasi di backend)."
    // 1.2 + 0.8 - 0.3 = 1.7, not 2.768, so the drawer must say so rather than imply it adds up.
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/tidak menjumlah/i)).toBeInTheDocument();
  });

  it('says plainly when SHAP is unavailable', async () => {
    mockProfile({ ...PROFILE, drivers: [], drivers_unavailable: 'Artefak SHAP belum dibuat.' });
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/belum dibuat/i)).toBeInTheDocument();
  });

  it('carries the surface-temperature footnote', async () => {
    mockProfile();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/bukan suhu udara/i)).toBeInTheDocument();
  });

  it('hands a prepared prompt to the agent', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onAskAgent = vi.fn();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={vi.fn()} onAskAgent={onAskAgent} />);

    await user.click(await screen.findByRole('button', { name: /tanya agen/i }));

    expect(onAskAgent).toHaveBeenCalledWith(expect.stringContaining('Kampung Rawa'));
  });

  it('closes on the close button', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={onClose} onAskAgent={vi.fn()} />);

    await user.click(await screen.findByRole('button', { name: /tutup/i }));

    expect(onClose).toHaveBeenCalled();
  });

  it('closes on Escape', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<KelurahanDrawer kelId="ID3173040002" onClose={onClose} onAskAgent={vi.fn()} />);
    await screen.findByRole('dialog');

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalled();
  });

  it('surfaces a fetch failure instead of showing an empty drawer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ success: false, data: null, error: 'Kelurahan tidak ada.' }),
      }),
    );
    render(<KelurahanDrawer kelId="ID9999999999" onClose={vi.fn()} onAskAgent={vi.fn()} />);
    expect(await screen.findByText(/tidak ada/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./KelurahanDrawer"`

- [ ] **Step 3: Tulis `web/components/KelurahanDrawer.module.css`**

```css
.drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: var(--drawer-width);
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  box-shadow: var(--shadow-drawer);
  animation: slide-in var(--duration-drawer) var(--ease-out);
}

@keyframes slide-in {
  from {
    transform: translateX(16px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.header {
  flex: none;
  padding: var(--space-7) var(--space-9);
  border-bottom: 1px solid var(--color-border);
}

.headerTop {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.close {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-ink-secondary);
}

.close:hover {
  background: var(--color-surface-hover);
}

.name {
  margin: var(--space-3) 0 0;
  font-size: var(--text-kelurahan);
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: var(--leading-heading);
}

.location {
  margin-top: var(--space-1);
  font-size: var(--text-control);
  color: var(--color-ink-secondary);
}

.pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin-top: var(--space-5);
}

.pillRank {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  height: 30px;
  padding: 0 var(--space-6);
  border-radius: var(--radius-pill);
  background: var(--color-hvi-tint);
  color: var(--color-hvi-dark);
  font-size: var(--text-secondary);
}

.ask {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  width: 100%;
  height: 42px;
  margin-top: var(--space-5);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canopy);
  color: #fff;
  font-size: var(--text-body);
  font-weight: 600;
}

.ask:hover {
  background: var(--color-canopy-hover);
}

.body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  padding: var(--space-8) var(--space-9) var(--space-11);
}

.metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}

.metricCard {
  padding: var(--space-5) var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.metricLabel {
  font-size: 12px;
  color: var(--color-ink-secondary);
}

.metricValue {
  margin-top: var(--space-2);
  font-size: var(--text-metric);
  font-weight: 700;
  line-height: var(--leading-heading);
}

.metricSub {
  margin-top: var(--space-1);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.sectionTitle {
  font-size: var(--text-section);
  font-weight: 600;
}

.sectionSub {
  margin-top: var(--space-1);
  font-size: var(--text-help);
  color: var(--color-ink-secondary);
}

.formula {
  margin-top: var(--space-5);
  padding: var(--space-5) var(--space-6);
  background: var(--color-paper);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-help);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}

.componentRow {
  display: grid;
  grid-template-columns: 1fr 64px;
  align-items: center;
  gap: var(--space-5);
  margin-top: var(--space-5);
}

.componentLabel {
  font-size: var(--text-secondary);
}

.track {
  height: 8px;
  margin-top: var(--space-2);
  border-radius: 4px;
  background: var(--color-hvi-tint);
  overflow: hidden;
}

.fill {
  height: 100%;
  border-radius: 4px;
  background: var(--color-hvi);
}

.driverRow {
  display: grid;
  grid-template-columns: 136px 1fr 64px;
  align-items: center;
  gap: var(--space-5);
  margin-top: var(--space-4);
  font-size: var(--text-secondary);
}

.driverTrack {
  position: relative;
  height: 14px;
  background: var(--color-paper);
  border-radius: var(--radius-swatch);
}

/* Zero axis at 20% of the width, per design/README.md §3. */
.driverBar {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 2px;
}

.mismatch {
  margin-top: var(--space-5);
  padding: var(--space-5) var(--space-6);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  font-size: var(--text-help);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}

.landcover {
  display: flex;
  height: 22px;
  margin-top: var(--space-5);
  border-radius: var(--radius-swatch);
  overflow: hidden;
}

.footnote {
  display: flex;
  gap: var(--space-4);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}

.state {
  padding: var(--space-11) var(--space-9);
  font-size: var(--text-secondary);
  color: var(--color-ink-secondary);
}
```

- [ ] **Step 4: Tulis `web/components/KelurahanDrawer.tsx`**

```tsx
'use client';

/**
 * Kelurahan profile drawer.
 *
 * Two things here are substantive rather than cosmetic.
 *
 * design/README.md requires the SHAP bars to sum to the stated temperature difference. They
 * often will not: the model explains its own prediction, not the observed anomaly against
 * the city mean, and those are different quantities. Rather than hide the gap by rounding or
 * by relabelling the total, the drawer states it. A chart that silently does not add up is
 * worse than one that admits it.
 *
 * Every figure goes through SourceChip. That is the product's central claim, and a single
 * bare number anywhere undermines the badge on the brief.
 */

import { MessageCircle, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchProfile } from '@/lib/api';
import { MINUS, formatNumber, formatPercent, formatRank, formatUnit } from '@/lib/format';
import type { Driver, ProfileResponse } from '@/lib/types';
import { SourceChip, kindForSource } from './SourceChip';
import styles from './KelurahanDrawer.module.css';

const DATA_SOURCE =
  'Data TEDUH v1: Landsat 8/9 (median musim kemarau 2023–2025), Sentinel-2, '
  + 'ESA WorldCover v200, Google Open Buildings, WorldPop 2025.';

const MODEL_SOURCE =
  'Model panas TEDUH LightGBM v1 dengan monotonic constraints dan spatial block CV.';

/** Contributions and anomaly are different quantities; flag a gap beyond this. */
const SUM_TOLERANCE_C = 0.1;

/** Zero axis position inside the divergent bar track (design/README.md §3). */
const ZERO_AXIS_PCT = 20;

const COMPONENT_LABELS: [keyof ProfileResponse['profile'], string][] = [
  ['H', 'Bahaya (panas permukaan)'],
  ['E', 'Keterpaparan (kepadatan penduduk)'],
  ['S', 'Kepekaan (balita & lansia)'],
  ['A', 'Kurangnya kapasitas adaptif'],
];

const LANDCOVER_COLORS = {
  built: '#6F6A60',
  tree: '#5E9A6E',
  water: '#5FA3CB',
  other: '#D5D0C6',
};

function DriverBar({ driver, scale }: { driver: Driver; scale: number }) {
  const warming = driver.contribution_c > 0;
  const widthPct = (Math.abs(driver.contribution_c) / scale) * (100 - ZERO_AXIS_PCT);

  return (
    <div className={styles.driverRow}>
      <span>{driver.label}</span>
      <span className={styles.driverTrack}>
        <span
          className={styles.driverBar}
          style={{
            left: warming ? `${ZERO_AXIS_PCT}%` : `${ZERO_AXIS_PCT - widthPct}%`,
            width: `${widthPct}%`,
            background: warming ? 'var(--color-hot)' : 'var(--color-cold)',
          }}
        />
      </span>
      <SourceChip
        value={`${driver.contribution_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(driver.contribution_c), 1)}`}
        unit="°C"
        kind="model"
        source={`${MODEL_SOURCE} Kontribusi ${driver.label} (${driver.direction}).`}
        align="end"
      />
    </div>
  );
}

interface KelurahanDrawerProps {
  kelId: string | null;
  onClose: () => void;
  onAskAgent: (prompt: string) => void;
}

export function KelurahanDrawer({ kelId, onClose, onAskAgent }: KelurahanDrawerProps) {
  const [data, setData] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kelId) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setData(null);
    setError(null);
    fetchProfile(kelId)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((cause: Error) => {
        if (!cancelled) setError(cause.message);
      });
    return () => {
      cancelled = true;
    };
  }, [kelId]);

  useEffect(() => {
    if (!kelId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [kelId, onClose]);

  if (!kelId) return null;

  if (error) {
    return (
      <aside className={styles.drawer} role="dialog" aria-label="Profil kelurahan">
        <div className={styles.state}>{error}</div>
      </aside>
    );
  }

  if (!data) {
    return (
      <aside className={styles.drawer} role="dialog" aria-label="Profil kelurahan">
        <div className={styles.state}>Memuat profil kelurahan…</div>
      </aside>
    );
  }

  const { profile, total_kelurahan: total, drivers } = data;
  const driverSum = drivers.reduce((total_, driver) => total_ + driver.contribution_c, 0);
  const mismatch = Math.abs(driverSum - profile.lst_anomaly) > SUM_TOLERANCE_C;
  const scale = Math.max(...drivers.map((d) => Math.abs(d.contribution_c)), 0.1);
  const otherFrac = Math.max(
    0,
    1 - profile.built_frac - profile.tree_frac - profile.water_frac,
  );

  return (
    <aside className={styles.drawer} role="dialog" aria-label={`Profil ${profile.kel_name}`}>
      <div className={styles.header}>
        <div className={styles.headerTop}>
          <span className="kicker">PROFIL KELURAHAN</span>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Tutup profil">
            <X size={18} />
          </button>
        </div>

        <h2 className={styles.name}>{profile.kel_name}</h2>
        <div className={styles.location}>
          Kec. {profile.kec_name} · {profile.kota_name}
        </div>

        <div className={styles.pills}>
          <span className={styles.pillRank}>
            Peringkat HVI{' '}
            <SourceChip
              value={formatRank(profile.hvi_rank, total)}
              kind="data"
              source={`${DATA_SOURCE} Peringkat dihitung atas ${total} kelurahan DKI Jakarta daratan.`}
              placement="bottom"
            />
          </span>
        </div>

        <button
          type="button"
          className={styles.ask}
          onClick={() =>
            onAskAgent(
              `Jelaskan kondisi panas dan opsi intervensi untuk Kelurahan ${profile.kel_name}.`,
            )
          }
        >
          <MessageCircle size={16} aria-hidden="true" />
          Tanya agen tentang wilayah ini
        </button>
      </div>

      <div className={styles.body}>
        <div className={styles.metrics}>
          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>LST rata-rata</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.lst, 1)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>suhu permukaan</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Selisih dari rata-rata kota</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hot-strong)' }}>
              <SourceChip
                value={`${profile.lst_anomaly > 0 ? '+' : MINUS}${formatNumber(Math.abs(profile.lst_anomaly), 2)}`}
                unit="°C"
                kind="data"
                source={`${DATA_SOURCE} Rata-rata kota dihitung dari sel berkualitas baik.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              rata-rata kota{' '}
              <SourceChip
                value={formatNumber(profile.lst - profile.lst_anomaly, 2)}
                unit="°C"
                kind="data"
                source={DATA_SOURCE}
                align="start"
              />
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Indeks kerentanan (HVI)</div>
            <div className={styles.metricValue} style={{ color: 'var(--color-hvi-dark)' }}>
              <SourceChip
                value={formatNumber(profile.hvi, 2)}
                kind="data"
                source={`${DATA_SOURCE} HVI adalah persentil dalam-kota, bukan risiko absolut.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>skala 0–1, makin tinggi makin rentan</div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>Warga rentan</div>
            <div className={styles.metricValue}>
              <SourceChip
                value={formatNumber(profile.vulnerable, 0)}
                unit="jiwa"
                kind="data"
                source={`${DATA_SOURCE} Balita (<5 tahun) dan lansia (>=65 tahun), WorldPop 2025.`}
                align="start"
              />
            </div>
            <div className={styles.metricSub}>
              <SourceChip
                value={formatNumber(profile.exposed_vulnerable, 0)}
                unit="jiwa"
                kind="data"
                source={`${DATA_SOURCE} Warga rentan di sel dengan persentil bahaya >= 0,8.`}
                align="start"
              />{' '}
              di sel paling panas
            </div>
          </div>
        </div>

        <section>
          <h3 className={styles.sectionTitle}>Komponen kerentanan panas</h3>
          <div className={styles.formula}>
            HVI = Bahaya × (0,4 Keterpaparan + 0,3 Kepekaan + 0,3 Kurangnya kapasitas adaptif)
          </div>
          {COMPONENT_LABELS.map(([key, label]) => {
            const value = profile[key] as number;
            return (
              <div key={key} className={styles.componentRow}>
                <div>
                  <div className={styles.componentLabel}>{label}</div>
                  <div className={styles.track}>
                    <div className={styles.fill} style={{ width: `${value * 100}%` }} />
                  </div>
                </div>
                <SourceChip
                  value={formatNumber(value, 2)}
                  kind="data"
                  source={`${DATA_SOURCE} Persentil dalam-kota untuk komponen ${key}.`}
                  align="end"
                />
              </div>
            );
          })}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>Apa yang membuat wilayah ini panas?</h3>
          <div className={styles.sectionSub}>
            Kontribusi tiap faktor terhadap prediksi suhu, menurut model (SHAP).
          </div>

          {data.drivers_unavailable && (
            <div className={styles.mismatch}>{data.drivers_unavailable}</div>
          )}

          {drivers.map((driver) => (
            <DriverBar key={driver.feature} driver={driver} scale={scale} />
          ))}

          {drivers.length > 0 && mismatch && (
            <div className={styles.mismatch}>
              Jumlah kontribusi di atas{' '}
              <SourceChip
                value={`${driverSum > 0 ? '+' : MINUS}${formatNumber(Math.abs(driverSum), 2)}`}
                unit="°C"
                kind="model"
                source={MODEL_SOURCE}
                align="start"
              />{' '}
              <strong>tidak menjumlah</strong> ke selisih dari rata-rata kota. Keduanya
              besaran berbeda: model menjelaskan prediksinya sendiri, bukan selisih terhadap
              rata-rata kota. Pakai angka ini sebagai arah, bukan sebagai penguraian tepat.
            </div>
          )}
        </section>

        <section>
          <h3 className={styles.sectionTitle}>Tutupan lahan</h3>
          <div className={styles.landcover}>
            <span style={{ width: `${profile.built_frac * 100}%`, background: LANDCOVER_COLORS.built }} />
            <span style={{ width: `${profile.tree_frac * 100}%`, background: LANDCOVER_COLORS.tree }} />
            <span style={{ width: `${profile.water_frac * 100}%`, background: LANDCOVER_COLORS.water }} />
            <span style={{ width: `${otherFrac * 100}%`, background: LANDCOVER_COLORS.other }} />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>Bangunan</span>
            <SourceChip
              value={formatPercent(profile.built_frac, 1)}
              kind="data"
              source={`${DATA_SOURCE} ESA WorldCover kelas 50.`}
              align="end"
            />
          </div>
          <div className={styles.componentRow}>
            <span className={styles.componentLabel}>Pohon</span>
            <SourceChip
              value={formatPercent(profile.tree_frac, 1)}
              kind="data"
              source={`${DATA_SOURCE} ESA WorldCover kelas 10 dan 95.`}
              align="end"
            />
          </div>
        </section>

        <div className={styles.footnote}>
          <span aria-hidden="true">ⓘ</span>
          <span>{data.note}</span>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 15 tes baru.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah drawer profil kelurahan dengan chip sumber di setiap angka

Menyatakan terang-terangan ketika jumlah kontribusi SHAP tidak sama dengan selisih
rata-rata kota, karena keduanya besaran berbeda dan menyembunyikannya akan
membuat grafiknya berbohong.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T9: Dok skenario

**Files:**
- Create: `web/components/ScenarioDock.tsx`, `web/components/ScenarioDock.module.css`
- Test: `web/components/ScenarioDock.test.tsx`

**Interfaces:**
- Consumes: `lib/format.formatIdr`.
- Produces:
  - `SLIDERS: {key, label, help, min, max, step, suffix}[]` — tiga definisi slider
  - `ScenarioState = { tree: number; coolRoof: number; greenRoof: number; budget: number | null }`
  - `EMPTY_SCENARIO: ScenarioState`
  - `ScenarioDock` — props: `state`, `onChange`, `targetLabel`, `status`, `busy`, `onSimulate`

Spesifikasi `design/README.md` §4: grid `repeat(3, 1fr) 196px 132px`, gap 20, align end. Kanopi 0–20 step 1 ("+N pp", bantuan "Poin persen lahan terbuka"); cool roof 0–100 step 5; green roof 0–50 step 5. Nilai `#1F5C4A` bila > 0, `#5E6662` bila 0. `accent-color: #1F5C4A`. Input anggaran 40 px dengan prefix "Rp" dan format ribuan id-ID saat mengetik. Tombol Simulasikan **disabled** sampai ada slider > 0.

- [ ] **Step 1: Tulis tes yang gagal**

`web/components/ScenarioDock.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { EMPTY_SCENARIO, ScenarioDock } from './ScenarioDock';

function setup(overrides = {}) {
  const props = {
    state: EMPTY_SCENARIO,
    onChange: vi.fn(),
    targetLabel: 'Target: 5 kelurahan prioritas',
    status: 'Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan.',
    busy: false,
    onSimulate: vi.fn(),
    ...overrides,
  };
  render(<ScenarioDock {...props} />);
  return props;
}

describe('ScenarioDock', () => {
  it('offers the three interventions', () => {
    setup();
    expect(screen.getByLabelText(/tambah kanopi pohon/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/cool roof/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/green roof/i)).toBeInTheDocument();
  });

  it('uses the ranges from the design handoff', () => {
    setup();
    const canopy = screen.getByLabelText(/tambah kanopi pohon/i);
    expect(canopy).toHaveAttribute('min', '0');
    expect(canopy).toHaveAttribute('max', '20');
    expect(canopy).toHaveAttribute('step', '1');

    const greenRoof = screen.getByLabelText(/green roof/i);
    expect(greenRoof).toHaveAttribute('max', '50');
    expect(greenRoof).toHaveAttribute('step', '5');
  });

  it('explains what percentage points mean', () => {
    // "pp" is meaningless to a planner without the gloss.
    setup();
    expect(screen.getByText(/poin persen lahan terbuka/i)).toBeInTheDocument();
  });

  it('disables Simulasikan until something is set', () => {
    setup();
    expect(screen.getByRole('button', { name: /simulasikan/i })).toBeDisabled();
  });

  it('enables Simulasikan once a slider moves', () => {
    setup({ state: { ...EMPTY_SCENARIO, coolRoof: 50 } });
    expect(screen.getByRole('button', { name: /simulasikan/i })).toBeEnabled();
  });

  it('reports a slider change', async () => {
    const user = userEvent.setup();
    const props = setup();

    const canopy = screen.getByLabelText(/tambah kanopi pohon/i);
    await user.type(canopy, '{ArrowRight}');

    expect(props.onChange).toHaveBeenCalled();
  });

  it('shows the canopy value with its pp suffix', () => {
    setup({ state: { ...EMPTY_SCENARIO, tree: 7 } });
    expect(screen.getByText('+7 pp')).toBeInTheDocument();
  });

  it('shows roof adoption as a percentage', () => {
    setup({ state: { ...EMPTY_SCENARIO, coolRoof: 50 } });
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('formats the budget with Indonesian thousands separators while typing', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.type(screen.getByLabelText(/anggaran/i), '2000000000');

    const lastCall = props.onChange.mock.calls.at(-1)?.[0];
    expect(lastCall.budget).toBe(2_000_000_000);
  });

  it('ignores non-digits in the budget field', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.type(screen.getByLabelText(/anggaran/i), 'abc');

    const calls = props.onChange.mock.calls;
    if (calls.length) {
      expect(calls.at(-1)?.[0].budget).toBeNull();
    }
  });

  it('shows the target scope and the status line', () => {
    setup();
    expect(screen.getByText(/5 kelurahan prioritas/)).toBeInTheDocument();
    expect(screen.getByText(/belum ada simulasi/i)).toBeInTheDocument();
  });

  it('blocks a second submit while a simulation is running', () => {
    setup({ state: { ...EMPTY_SCENARIO, tree: 5 }, busy: true });
    expect(screen.getByRole('button', { name: /menghitung/i })).toBeDisabled();
  });

  it('runs the simulation on click', async () => {
    const user = userEvent.setup();
    const props = setup({ state: { ...EMPTY_SCENARIO, tree: 5 } });

    await user.click(screen.getByRole('button', { name: /simulasikan/i }));

    expect(props.onSimulate).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./ScenarioDock"`

- [ ] **Step 3: Tulis `web/components/ScenarioDock.module.css`**

```css
.dock {
  flex: none;
  padding: var(--space-7) var(--space-9) var(--space-8);
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
}

.titleRow {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
}

.title {
  font-size: var(--text-section);
  font-weight: 600;
}

.target {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 var(--space-5);
  border-radius: var(--radius-pill);
  background: var(--color-canopy-tint);
  color: var(--color-canopy);
  font-size: var(--text-help);
  font-weight: 600;
}

.status {
  font-size: var(--text-help);
  color: var(--color-ink-secondary);
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr) 196px 132px;
  align-items: end;
  gap: var(--space-9);
}

.field {
  min-width: 0;
}

.fieldHead {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-4);
}

.fieldLabel {
  font-size: var(--text-control);
}

.value {
  font-size: var(--text-control);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink-secondary);
}

.valueActive {
  color: var(--color-canopy);
}

.slider {
  width: 100%;
  margin: var(--space-4) 0 var(--space-2);
  accent-color: var(--color-canopy);
}

.help {
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.budgetWrap {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  height: 40px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.budgetWrap:focus-within {
  border-color: var(--color-canopy);
}

.budgetWrap input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: none;
  font: inherit;
  font-variant-numeric: tabular-nums;
  text-align: right;
  outline: none;
}

.simulate {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  height: 40px;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--color-canopy);
  color: #fff;
  font-size: var(--text-control);
  font-weight: 600;
}

.simulate:hover:not(:disabled) {
  background: var(--color-canopy-hover);
}

.simulate:disabled {
  background: var(--color-border);
  color: var(--color-ink-secondary);
  cursor: not-allowed;
}
```

- [ ] **Step 4: Tulis `web/components/ScenarioDock.tsx`**

```tsx
'use client';

/**
 * Scenario sliders and the budget field.
 *
 * Simulasikan stays disabled until at least one slider moves. That is not just polish: a
 * zero scenario returns a delta of exactly 0 for every kelurahan, and a planner reading
 * "0,00 °C" has no way to tell a real null result from a button they pressed too early.
 *
 * The canopy slider is in percentage POINTS of cell area, not a percentage of anything, so
 * the help text spells that out. "pp" alone means nothing to the intended user.
 */

import { Play } from 'lucide-react';
import { Loader2 } from 'lucide-react';
import styles from './ScenarioDock.module.css';

export interface ScenarioState {
  tree: number;
  coolRoof: number;
  greenRoof: number;
  budget: number | null;
}

export const EMPTY_SCENARIO: ScenarioState = {
  tree: 0,
  coolRoof: 0,
  greenRoof: 0,
  budget: null,
};

type SliderKey = 'tree' | 'coolRoof' | 'greenRoof';

interface SliderDefinition {
  key: SliderKey;
  label: string;
  help: string;
  min: number;
  max: number;
  step: number;
  render: (value: number) => string;
}

export const SLIDERS: SliderDefinition[] = [
  {
    key: 'tree',
    label: 'Tambah kanopi pohon',
    help: 'Poin persen lahan terbuka',
    min: 0,
    max: 20,
    step: 1,
    render: (value) => `+${value} pp`,
  },
  {
    key: 'coolRoof',
    label: 'Cool roof',
    help: 'Porsi atap dicat pemantul panas',
    min: 0,
    max: 100,
    step: 5,
    render: (value) => `${value}%`,
  },
  {
    key: 'greenRoof',
    label: 'Green roof',
    help: 'Porsi atap beton datar',
    min: 0,
    max: 50,
    step: 5,
    render: (value) => `${value}%`,
  },
];

interface ScenarioDockProps {
  state: ScenarioState;
  onChange: (next: ScenarioState) => void;
  targetLabel: string;
  status: string;
  busy: boolean;
  onSimulate: () => void;
}

export function ScenarioDock({
  state,
  onChange,
  targetLabel,
  status,
  busy,
  onSimulate,
}: ScenarioDockProps) {
  const hasIntervention = state.tree > 0 || state.coolRoof > 0 || state.greenRoof > 0;

  return (
    <section className={styles.dock} aria-label="Simulasi skenario">
      <div className={styles.titleRow}>
        <span className={styles.title}>Simulasi skenario</span>
        <span className={styles.target}>{targetLabel}</span>
        <span className={styles.status}>{status}</span>
      </div>

      <div className={styles.grid}>
        {SLIDERS.map((slider) => {
          const value = state[slider.key];
          return (
            <div key={slider.key} className={styles.field}>
              <div className={styles.fieldHead}>
                <label className={styles.fieldLabel} htmlFor={`slider-${slider.key}`}>
                  {slider.label}
                </label>
                <span
                  className={`${styles.value} ${value > 0 ? styles.valueActive : ''}`}
                >
                  {slider.render(value)}
                </span>
              </div>
              <input
                id={`slider-${slider.key}`}
                className={styles.slider}
                type="range"
                min={slider.min}
                max={slider.max}
                step={slider.step}
                value={value}
                onChange={(event) =>
                  onChange({ ...state, [slider.key]: Number(event.target.value) })
                }
              />
              <div className={styles.help}>{slider.help}</div>
            </div>
          );
        })}

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="budget">
            Anggaran (Rp)
          </label>
          <div className={styles.budgetWrap}>
            <span aria-hidden="true">Rp</span>
            <input
              id="budget"
              type="text"
              inputMode="numeric"
              aria-label="Anggaran dalam rupiah"
              value={state.budget === null ? '' : state.budget.toLocaleString('id-ID')}
              onChange={(event) => {
                // Digits only: the displayed value carries dot separators, and parsing them
                // back as a number would multiply the budget by a thousand.
                const digits = event.target.value.replace(/\D/g, '');
                onChange({ ...state, budget: digits ? Number(digits) : null });
              }}
            />
          </div>
        </div>

        <button
          type="button"
          className={styles.simulate}
          disabled={!hasIntervention || busy}
          onClick={onSimulate}
        >
          {busy ? (
            <>
              <Loader2 size={16} aria-hidden="true" /> Menghitung…
            </>
          ) : (
            <>
              <Play size={16} aria-hidden="true" /> Simulasikan
            </>
          )}
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 13 tes baru.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah dok skenario dengan tombol yang terkunci sampai ada intervensi

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T10: Klien SSE dan panel agen

**Files:**
- Create: `web/lib/agent.ts`
- Create: `web/components/AgentPanel.tsx`, `web/components/AgentPanel.module.css`
- Test: `web/lib/agent.test.ts`

**Interfaces:**
- Consumes: `lib/api.API_BASE`.
- Produces:
  - `agent.ts`: `APP_NAME = 'teduh_agent'`, `AgentStep`, `AgentEvent`, `createSession(userId): Promise<string>`, `parseSseChunk(buffer: string): { events: unknown[]; rest: string }`, `eventsToSteps(raw: unknown[]): AgentStep[]`, `streamAgent(options): AsyncGenerator<AgentEvent>`
  - `AgentPanel` — props: `draft`, `onDraftChange`, `messages`, `onSend`, `onNewThread`, `onHighlight`, `busy`

**WAJIB diverifikasi sebelum menulis:** bentuk payload `/run_sse` dan jalur pembuatan sesi berubah antar rilis ADK. Jalankan API lokal dan periksa:

```bash
uv run uvicorn api.main:app --port 8080 &
curl -s localhost:8080/openapi.json | python3 -c "
import json,sys
spec = json.load(sys.stdin)
for path in sorted(spec['paths']):
    if 'run' in path or 'session' in path:
        print(path, list(spec['paths'][path].keys()))
"
```

Sesuaikan `createSession` dan `streamAgent` dengan path serta skema yang tercetak. Bentuk di bawah berlaku untuk ADK yang memakai `POST /apps/{app}/users/{user}/sessions/{session}` dan `POST /run_sse`.

- [ ] **Step 1: Tulis tes yang gagal**

`web/lib/agent.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { eventsToSteps, parseSseChunk } from './agent';

describe('parseSseChunk', () => {
  it('extracts complete events and keeps the partial tail', () => {
    const { events, rest } = parseSseChunk('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c"');
    expect(events).toEqual([{ a: 1 }, { b: 2 }]);
    expect(rest).toBe('data: {"c"');
  });

  it('returns nothing when no event is complete yet', () => {
    const { events, rest } = parseSseChunk('data: {"partial":');
    expect(events).toEqual([]);
    expect(rest).toBe('data: {"partial":');
  });

  it('ignores the [DONE] sentinel', () => {
    expect(parseSseChunk('data: [DONE]\n\n').events).toEqual([]);
  });

  it('skips a malformed event rather than throwing', () => {
    // A single bad frame must not kill a live stream mid-answer.
    const { events } = parseSseChunk('data: {bukan json}\n\ndata: {"ok":true}\n\n');
    expect(events).toEqual([{ ok: true }]);
  });
});

describe('eventsToSteps', () => {
  it('turns a function call into a running step', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'find_area', args: { query: 'Jakarta Timur' } } }] } },
    ]);
    expect(steps).toEqual([
      expect.objectContaining({ tool: 'find_area', status: 'running' }),
    ]);
  });

  it('marks a step done once its response arrives', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'find_area', args: {} } }] } },
      { content: { parts: [{ functionResponse: { name: 'find_area', response: { matches: [] } } }] } },
    ]);
    expect(steps[0].status).toBe('done');
  });

  it('labels each known tool in Indonesian', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'rank_priority_areas', args: {} } }] } },
    ]);
    expect(steps[0].label).toMatch(/kerentanan|prioritas/i);
  });

  it('keeps the tool name for an unknown tool instead of hiding the step', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'tool_baru', args: {} } }] } },
    ]);
    expect(steps[0].label).toContain('tool_baru');
  });

  it('keeps the structured tool response so result cards render from data', () => {
    // design/README.md: "kartu hasil dirender dari output tool terstruktur, bukan dari
    // teks LLM, agar angka terverifikasi."
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'rank_priority_areas', args: {} } }] } },
      {
        content: {
          parts: [
            {
              functionResponse: {
                name: 'rank_priority_areas',
                response: { areas: [{ kel_id: 'ID3173040002', hvi: 0.93 }] },
              },
            },
          ],
        },
      },
    ]);
    expect(steps[0].response).toEqual({ areas: [{ kel_id: 'ID3173040002', hvi: 0.93 }] });
  });

  it('ignores plain text parts, which are prose not steps', () => {
    expect(eventsToSteps([{ content: { parts: [{ text: 'Lima kelurahan…' }] } }])).toEqual([]);
  });

  it('tolerates an event with no content', () => {
    expect(eventsToSteps([{}, { content: {} }])).toEqual([]);
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./agent"`

- [ ] **Step 3: Tulis `web/lib/agent.ts`**

```ts
/**
 * SSE client for the ADK agent endpoint.
 *
 * The step list is built from functionCall/functionResponse parts rather than from the
 * model's prose, and the structured response is kept alongside each step. That is what lets
 * the chat render result cards from verified tool output instead of parsing numbers back
 * out of generated text -- design/README.md is explicit that cards come from tool data
 * "agar angka terverifikasi".
 *
 * A malformed SSE frame is skipped rather than thrown, because one bad frame must not kill
 * a live answer halfway through.
 *
 * The /run_sse payload shape moves between ADK releases. Verify against
 * `curl localhost:8080/openapi.json` before changing anything here.
 */

import { API_BASE } from './api';

export const APP_NAME = 'teduh_agent';

/** Indonesian labels for the step list; keys are the tool names from M3/M5/M6. */
const TOOL_LABELS: Record<string, string> = {
  find_area: 'Mencari wilayah',
  get_area_profile: 'Mengambil profil kelurahan',
  rank_priority_areas: 'Menghitung indeks kerentanan',
  explain_drivers: 'Menganalisis faktor pendorong',
  simulate_intervention: 'Menyimulasikan intervensi',
  optimize_portfolio: 'Menyusun portofolio anggaran',
  get_evidence: 'Mengambil temuan literatur',
  get_session_facts: 'Mengumpulkan fakta percakapan',
  render_policy_brief: 'Menyusun policy brief',
  analyze_roof_photo: 'Menganalisis foto atap',
  recommend_roof_action: 'Menyusun rekomendasi atap',
};

export interface AgentStep {
  tool: string;
  label: string;
  args: Record<string, unknown>;
  status: 'running' | 'done';
  response?: Record<string, unknown>;
}

export type AgentEvent =
  | { kind: 'text'; text: string }
  | { kind: 'steps'; steps: AgentStep[] }
  | { kind: 'done' }
  | { kind: 'error'; message: string };

export async function createSession(userId: string): Promise<string> {
  const sessionId = `s-${Date.now().toString(36)}`;
  const response = await fetch(
    `${API_BASE}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions/${sessionId}`,
    { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' },
  );
  if (!response.ok) {
    throw new Error(`Gagal membuat sesi agen (status ${response.status}).`);
  }
  return sessionId;
}

/** Split a buffer into complete SSE events, returning the unparsed tail. */
export function parseSseChunk(buffer: string): { events: unknown[]; rest: string } {
  const frames = buffer.split('\n\n');
  const rest = frames.pop() ?? '';
  const events: unknown[] = [];

  for (const frame of frames) {
    for (const line of frame.split('\n')) {
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;
      try {
        events.push(JSON.parse(payload));
      } catch {
        // One bad frame must not end a live answer.
      }
    }
  }
  return { events, rest };
}

interface RawPart {
  text?: string;
  functionCall?: { name: string; args?: Record<string, unknown> };
  functionResponse?: { name: string; response?: Record<string, unknown> };
}

function partsOf(event: unknown): RawPart[] {
  const content = (event as { content?: { parts?: RawPart[] } })?.content;
  return content?.parts ?? [];
}

export function eventsToSteps(raw: unknown[]): AgentStep[] {
  const steps: AgentStep[] = [];

  for (const event of raw) {
    for (const part of partsOf(event)) {
      if (part.functionCall) {
        const { name, args } = part.functionCall;
        steps.push({
          tool: name,
          label: TOOL_LABELS[name] ?? `Menjalankan ${name}`,
          args: args ?? {},
          status: 'running',
        });
      }
      if (part.functionResponse) {
        const { name, response } = part.functionResponse;
        const pending = [...steps].reverse().find(
          (step) => step.tool === name && step.status === 'running',
        );
        if (pending) {
          pending.status = 'done';
          pending.response = response ?? {};
        }
      }
    }
  }
  return steps;
}

export function textOf(raw: unknown[]): string {
  return raw
    .flatMap(partsOf)
    .map((part) => part.text ?? '')
    .join('');
}

export async function* streamAgent(options: {
  userId: string;
  sessionId: string;
  message: string;
  signal?: AbortSignal;
}): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${API_BASE}/run_sse`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    signal: options.signal,
    body: JSON.stringify({
      appName: APP_NAME,
      userId: options.userId,
      sessionId: options.sessionId,
      newMessage: { role: 'user', parts: [{ text: options.message }] },
      streaming: true,
    }),
  });

  if (!response.ok || !response.body) {
    yield {
      kind: 'error',
      message: `Agen tidak bisa dihubungi (status ${response.status}).`,
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const collected: unknown[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;

    if (events.length) {
      collected.push(...events);
      const text = textOf(collected);
      if (text) yield { kind: 'text', text };
      const steps = eventsToSteps(collected);
      if (steps.length) yield { kind: 'steps', steps };
    }
  }
  yield { kind: 'done' };
}
```

- [ ] **Step 4: Tulis `web/components/AgentPanel.module.css` dan `AgentPanel.tsx`**

Ikuti `design/README.md` §5 persis: header 52 px ("Agen TEDUH" 15/600 + sub 12 `#5E6662`, tombol `pencil`), thread scroll padding `12px 20px` gap 8 dengan auto-scroll, pesan pengguna rata kanan max 88% `bg #F7F4EE` radius `12 12 4 12`, blok langkah kerja `bg #FBFAF7` radius 10 dengan header "N langkah selesai · X detik" dan nama tool monospace 11 px di kanan, prosa jawaban 14 px `lh 1.55`, pil saran pertanyaan lanjutan 30 px radius penuh dengan ikon `arrow-right`, composer border-top dengan textarea dan tombol Kirim 36×36 `bg #1F5C4A`.

`web/components/AgentPanel.module.css`:

```css
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  height: var(--agent-panel-header);
  padding: 0 var(--space-9);
  border-bottom: 1px solid var(--color-border);
  flex: none;
}

.headerTitle {
  font-size: var(--text-section);
  font-weight: 600;
}

.headerSub {
  font-size: 12px;
  color: var(--color-ink-secondary);
}

.iconButton {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-ink-secondary);
  flex: none;
}

.iconButton:hover {
  background: var(--color-surface-hover);
}

.thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-9);
}

.user {
  align-self: flex-end;
  max-width: 88%;
  padding: var(--space-5) var(--space-6);
  background: var(--color-paper);
  border: 1px solid var(--color-border);
  border-radius: 12px 12px 4px 12px;
  font-size: var(--text-body);
  line-height: var(--leading-body);
}

.steps {
  background: var(--color-surface-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-5) var(--space-6);
}

.stepsHead {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: var(--space-4);
}

.step {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--text-secondary);
  padding: 2px 0;
}

.stepTool {
  margin-left: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  color: var(--color-ink-secondary);
}

.spin {
  animation: spin 1s linear infinite;
  color: var(--color-ink-secondary);
  flex: none;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.prose {
  font-size: var(--text-body);
  line-height: var(--leading-prose);
  white-space: pre-wrap;
}

.error {
  padding: var(--space-5) var(--space-6);
  border: 1px solid var(--color-hot-strong);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--color-hot-strong);
  font-size: var(--text-secondary);
}

.composer {
  flex: none;
  padding: var(--space-6) var(--space-8) var(--space-7);
  border-top: 1px solid var(--color-border);
}

.composerBox {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.composerBox:focus-within {
  border-color: var(--color-canopy);
}

.composerBox textarea {
  flex: 1;
  min-height: 40px;
  max-height: 140px;
  border: 0;
  background: none;
  font: inherit;
  font-size: var(--text-body);
  resize: none;
  outline: none;
}

.send {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--color-canopy);
  color: #fff;
  flex: none;
}

.send:disabled {
  background: var(--color-border);
  color: var(--color-ink-secondary);
  cursor: not-allowed;
}
```

`web/components/AgentPanel.tsx`:

```tsx
'use client';

/**
 * Chat thread, visible tool steps, and the composer.
 *
 * The step block is the point of this panel: it shows the agent reaching for data rather
 * than producing an answer from nowhere, which is what makes the provenance claim legible
 * to a sceptical user. Result cards render from step.response -- verified tool output --
 * never from the prose.
 */

import { Camera, Check, Loader2, Pencil, Send } from 'lucide-react';
import { useEffect, useRef } from 'react';
import type { AgentStep } from '@/lib/agent';
import { ResultTable } from './ResultTable';
import styles from './AgentPanel.module.css';

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  text: string;
  steps: AgentStep[];
  error?: string;
  elapsedMs?: number;
}

interface AgentPanelProps {
  messages: ChatMessage[];
  draft: string;
  busy: boolean;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onNewThread: () => void;
  onHighlight: (kelIds: string[]) => void;
  onSelect: (kelId: string) => void;
}

function StepBlock({ steps, elapsedMs }: { steps: AgentStep[]; elapsedMs?: number }) {
  const done = steps.filter((step) => step.status === 'done').length;
  const seconds = elapsedMs ? (elapsedMs / 1000).toLocaleString('id-ID', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }) : null;

  return (
    <div className={styles.steps}>
      <div className={styles.stepsHead}>
        {done} dari {steps.length} langkah selesai
        {seconds ? ` · ${seconds} detik` : ''}
      </div>
      {steps.map((step, index) => (
        <div key={`${step.tool}-${index}`} className={styles.step}>
          {step.status === 'done' ? (
            <Check size={14} color="var(--color-canopy)" aria-hidden="true" />
          ) : (
            <Loader2 size={14} className={styles.spin} aria-hidden="true" />
          )}
          <span>{step.label}</span>
          <code className={styles.stepTool}>{step.tool}</code>
        </div>
      ))}
    </div>
  );
}

export function AgentPanel({
  messages,
  draft,
  busy,
  onDraftChange,
  onSend,
  onNewThread,
  onHighlight,
  onSelect,
}: AgentPanelProps) {
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = threadRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages]);

  return (
    <aside className={styles.panel} aria-label="Agen TEDUH">
      <div className={styles.header}>
        <div>
          <div className={styles.headerTitle}>Agen TEDUH</div>
          <div className={styles.headerSub}>
            Setiap angka berasal dari data atau model, bukan karangan
          </div>
        </div>
        <button
          type="button"
          className={styles.iconButton}
          onClick={onNewThread}
          aria-label="Percakapan baru"
        >
          <Pencil size={16} />
        </button>
      </div>

      <div className={styles.thread} ref={threadRef}>
        {messages.map((message) =>
          message.role === 'user' ? (
            <div key={message.id} className={styles.user}>
              {message.text}
            </div>
          ) : (
            <div key={message.id}>
              {message.steps.length > 0 && (
                <StepBlock steps={message.steps} elapsedMs={message.elapsedMs} />
              )}
              {message.error && <div className={styles.error}>{message.error}</div>}
              {message.text && <div className={styles.prose}>{message.text}</div>}
              {message.steps
                .filter((step) => step.status === 'done' && step.response)
                .map((step, index) => (
                  <ResultTable
                    key={`${step.tool}-card-${index}`}
                    tool={step.tool}
                    response={step.response!}
                    onHighlight={onHighlight}
                    onSelect={onSelect}
                  />
                ))}
            </div>
          ),
        )}
      </div>

      <div className={styles.composer}>
        <div className={styles.composerBox}>
          <textarea
            value={draft}
            placeholder="Tanyakan tentang panas di wilayah Anda…"
            aria-label="Pertanyaan untuk agen"
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (draft.trim() && !busy) onSend();
              }
            }}
          />
          <a
            href="/cek-atap"
            className={styles.iconButton}
            aria-label="Buka halaman Cek Atap"
          >
            <Camera size={16} />
          </a>
          <button
            type="button"
            className={styles.send}
            disabled={!draft.trim() || busy}
            onClick={onSend}
            aria-label="Kirim pertanyaan"
          >
            {busy ? <Loader2 size={16} className={styles.spin} /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 12 tes baru untuk `agent.ts`.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/
git commit -m "feat(web): tambah klien SSE agen dan panel chat dengan blok langkah kerja

Kartu hasil dirender dari functionResponse terstruktur, bukan diparsing dari prosa
LLM, supaya angka di kartu selalu angka terverifikasi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T11: Kartu hasil tool

**Files:**
- Create: `web/components/ResultTable.tsx`, `web/components/ResultTable.module.css`
- Test: `web/components/ResultTable.test.tsx`

**Interfaces:**
- Consumes: `lib/format`, `components/SourceChip`.
- Produces: `ResultTable` — props: `tool: string`, `response: Record<string, unknown>`, `onHighlight: (ids: string[]) => void`, `onSelect: (kelId: string) => void`

Merender tiga bentuk kartu sesuai nama tool: `rank_priority_areas` → tabel kolom `24px | 1fr | 50px | 76px | 66px`; `simulate_intervention` → kartu ΔLST per kelurahan dengan rentang literatur; `optimize_portfolio` → daftar paket dengan total biaya dan porsi keadilan. Tool lain tidak dirender sebagai kartu.

- [ ] **Step 1: Tulis tes yang gagal**

`web/components/ResultTable.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ResultTable } from './ResultTable';

const RANK_RESPONSE = {
  areas: [
    { rank: 1, kel_id: 'ID3173040002', kel_name: 'Kampung Rawa', kota_name: 'Kota Jakarta Pusat', hvi: 0.9309, lst_c_mean: 44.605, exposed_vulnerable: 1020.39 },
    { rank: 2, kel_id: 'ID3173060004', kel_name: 'Serdang', kota_name: 'Kota Jakarta Pusat', hvi: 0.8987, lst_c_mean: 43.872, exposed_vulnerable: 1836.52 },
  ],
  map_highlight: ['ID3173040002', 'ID3173060004'],
};

const SIM_RESPONSE = {
  results: [
    { kel_id: 'ID3173040002', delta_lst_c: -0.83, delta_lst_pop_weighted_c: -0.91, vulnerable_benefiting: 540, area_m2: 12000, cost_idr: 1_140_000_000, extrapolation: false },
  ],
  evidence: [
    { id: 'ev_ndvi_kl_2025', source_title: 'Kuala Lumpur UHI', year: 2025, value_min: -1.4, value_max: 0.1, unit: 'degC', comparable_to_model: true, url_or_doi: 'https://doi.org/x' },
  ],
  note: 'Angka ini perkiraan model untuk suhu PERMUKAAN dan bersifat indikatif.',
};

const OPT_RESPONSE = {
  packages: [
    { kel_id: 'ID3173040002', kel_name: 'Kampung Rawa', intervention_type: 'cool_roof', level: 'medium', cost_idr: 950_000_000, delta_lst_c: -0.6, vulnerable_benefiting: 400, in_top_hvi_quintile: true },
  ],
  total_cost_idr: 950_000_000,
  budget_idr: 2_000_000_000,
  equity_share_requested: 0.6,
  equity_share_achieved: 1.0,
};

describe('ResultTable', () => {
  it('renders the ranking table with real kelurahan names', () => {
    render(<ResultTable tool="rank_priority_areas" response={RANK_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText('Kampung Rawa')).toBeInTheDocument();
    expect(screen.getByText('Serdang')).toBeInTheDocument();
  });

  it('warns that LST is a surface temperature in the table footer', () => {
    render(<ResultTable tool="rank_priority_areas" response={RANK_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/bukan suhu udara/i)).toBeInTheDocument();
  });

  it('highlights a row on hover', async () => {
    const user = userEvent.setup();
    const onHighlight = vi.fn();
    render(<ResultTable tool="rank_priority_areas" response={RANK_RESPONSE} onHighlight={onHighlight} onSelect={vi.fn()} />);

    await user.hover(screen.getByText('Serdang'));

    expect(onHighlight).toHaveBeenCalledWith(['ID3173060004']);
  });

  it('opens the drawer on a row click', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ResultTable tool="rank_priority_areas" response={RANK_RESPONSE} onHighlight={vi.fn()} onSelect={onSelect} />);

    await user.click(screen.getByText('Kampung Rawa'));

    expect(onSelect).toHaveBeenCalledWith('ID3173040002');
  });

  it('toggles the map highlight for the whole set', async () => {
    const user = userEvent.setup();
    const onHighlight = vi.fn();
    render(<ResultTable tool="rank_priority_areas" response={RANK_RESPONSE} onHighlight={onHighlight} onSelect={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /sorot di peta/i }));

    expect(onHighlight).toHaveBeenCalledWith(['ID3173040002', 'ID3173060004']);
  });

  it('shows the simulated cooling with an indicative label', () => {
    render(<ResultTable tool="simulate_intervention" response={SIM_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/−0,83/)).toBeInTheDocument();
    expect(screen.getByText(/indikatif/i)).toBeInTheDocument();
  });

  it('places the literature range beside the model number', () => {
    render(<ResultTable tool="simulate_intervention" response={SIM_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/Kuala Lumpur UHI/)).toBeInTheDocument();
    expect(screen.getByText(/−1,4/)).toBeInTheDocument();
  });

  it('flags an extrapolated scenario', () => {
    const extrapolated = { ...SIM_RESPONSE, results: [{ ...SIM_RESPONSE.results[0], extrapolation: true }] };
    render(<ResultTable tool="simulate_intervention" response={extrapolated} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/di luar rentang data latih/i)).toBeInTheDocument();
  });

  it('shows the portfolio total against the budget', () => {
    render(<ResultTable tool="optimize_portfolio" response={OPT_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/Rp 950\.000\.000/)).toBeInTheDocument();
    expect(screen.getByText(/Rp 2\.000\.000\.000/)).toBeInTheDocument();
  });

  it('shows the equity share achieved', () => {
    render(<ResultTable tool="optimize_portfolio" response={OPT_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });

  it('marks packages that land in the top HVI quintile', () => {
    render(<ResultTable tool="optimize_portfolio" response={OPT_RESPONSE} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText(/kuintil teratas/i)).toBeInTheDocument();
  });

  it('renders nothing for a tool with no card', () => {
    const { container } = render(<ResultTable tool="get_evidence" response={{}} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the tool returned an error', () => {
    const { container } = render(<ResultTable tool="rank_priority_areas" response={{ error: 'gagal' }} onHighlight={vi.fn()} onSelect={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./ResultTable"`

- [ ] **Step 3: Tulis `web/components/ResultTable.module.css`**

```css
.card {
  margin-top: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  overflow: hidden;
}

.cardHead {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-row);
  font-size: var(--text-secondary);
  font-weight: 600;
}

.row,
.headRow {
  display: grid;
  grid-template-columns: 24px 1fr 50px 76px 66px;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-6);
  font-size: var(--text-secondary);
  text-align: left;
  width: 100%;
  border: 0;
  background: none;
}

.headRow {
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.row {
  border-top: 1px solid var(--color-border-row);
  cursor: pointer;
}

.row:hover {
  background: var(--color-paper);
}

.rank {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-pill);
  background: var(--color-canopy);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-top: 1px solid var(--color-border-row);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
}

.highlightToggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  height: 28px;
  padding: 0 var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: transparent;
  font-size: var(--text-kicker);
  font-weight: 600;
  color: var(--color-ink);
}

.highlightToggle:hover {
  border-color: var(--color-canopy);
  background: var(--color-canopy-tint-hover);
}

.block {
  padding: var(--space-5) var(--space-6);
  border-top: 1px solid var(--color-border-row);
  font-size: var(--text-secondary);
}

.metricLine {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-5);
  padding: 2px 0;
}

.warn {
  margin: var(--space-4) var(--space-6) var(--space-5);
  padding: var(--space-4) var(--space-5);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-paper);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}

.evidence {
  padding: var(--space-5) var(--space-6);
  border-top: 1px solid var(--color-border-row);
  font-size: var(--text-kicker);
  color: var(--color-ink-secondary);
  line-height: var(--leading-caption);
}
```

- [ ] **Step 4: Tulis `web/components/ResultTable.tsx`**

```tsx
'use client';

/**
 * Result cards rendered from structured tool output.
 *
 * design/README.md: "kartu hasil dirender dari output tool terstruktur, bukan dari teks
 * LLM, agar angka terverifikasi." So this component reads the functionResponse payload and
 * never the prose. If a tool returned an error, no card is rendered at all -- an empty card
 * with dashes would look like a data problem rather than a failed call.
 */

import { MapPin } from 'lucide-react';
import { MINUS, formatIdr, formatNumber, formatPercent, formatUnit } from '@/lib/format';
import { SourceChip } from './SourceChip';
import styles from './ResultTable.module.css';

const DATA_SOURCE = 'Data TEDUH v1 (Landsat 8/9, WorldPop 2025, ESA WorldCover v200).';
const MODEL_SOURCE = 'Model panas TEDUH LightGBM v1, spatial block CV.';
const LST_FOOTNOTE = 'LST = suhu permukaan, bukan suhu udara.';

interface RankedArea {
  rank: number;
  kel_id: string;
  kel_name: string;
  kota_name: string;
  hvi: number;
  lst_c_mean: number;
  exposed_vulnerable: number;
}

interface ResultTableProps {
  tool: string;
  response: Record<string, unknown>;
  onHighlight: (kelIds: string[]) => void;
  onSelect: (kelId: string) => void;
}

function RankCard({ areas, onHighlight, onSelect }: {
  areas: RankedArea[];
  onHighlight: (ids: string[]) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        {areas.length} kelurahan paling rentan panas
      </div>

      <div className={styles.headRow}>
        <span>#</span>
        <span>Kelurahan</span>
        <span className={styles.numeric}>HVI</span>
        <span className={styles.numeric}>LST</span>
        <span className={styles.numeric}>Rentan</span>
      </div>

      {areas.map((area) => (
        <button
          key={area.kel_id}
          type="button"
          className={styles.row}
          onMouseEnter={() => onHighlight([area.kel_id])}
          onMouseLeave={() => onHighlight([])}
          onClick={() => onSelect(area.kel_id)}
        >
          <span className={styles.rank}>{area.rank}</span>
          <span>
            {area.kel_name}
            <br />
            <span style={{ color: 'var(--color-ink-secondary)', fontSize: 'var(--text-kicker)' }}>
              {area.kota_name}
            </span>
          </span>
          <span className={styles.numeric}>{formatNumber(area.hvi, 2)}</span>
          <span className={styles.numeric}>{formatUnit(area.lst_c_mean, 'degC', 1)}</span>
          <span className={styles.numeric}>{formatNumber(area.exposed_vulnerable, 0)}</span>
        </button>
      ))}

      <div className={styles.footer}>
        <span>{LST_FOOTNOTE}</span>
        <button
          type="button"
          className={styles.highlightToggle}
          onClick={() => onHighlight(areas.map((area) => area.kel_id))}
        >
          <MapPin size={12} aria-hidden="true" /> Sorot di peta
        </button>
      </div>
    </div>
  );
}

function SimulateCard({ response }: { response: Record<string, unknown> }) {
  const results = response.results as {
    kel_id: string;
    delta_lst_c: number;
    delta_lst_pop_weighted_c: number;
    vulnerable_benefiting: number;
    area_m2: number;
    cost_idr: number;
    extrapolation: boolean;
  }[];
  const evidence = (response.evidence ?? []) as {
    id: string;
    source_title: string;
    year: number;
    value_min: number;
    value_max: number;
    unit: string;
    comparable_to_model: boolean;
    url_or_doi: string;
  }[];
  const extrapolated = results.some((result) => result.extrapolation);

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>Perkiraan dampak intervensi · indikatif</div>

      {results.map((result) => (
        <div key={result.kel_id} className={styles.block}>
          <div className={styles.metricLine}>
            <span>Perubahan suhu permukaan</span>
            <SourceChip
              value={`${result.delta_lst_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_c), 2)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Tertimbang penduduk</span>
            <SourceChip
              value={`${result.delta_lst_pop_weighted_c > 0 ? '+' : MINUS}${formatNumber(Math.abs(result.delta_lst_pop_weighted_c), 2)}`}
              unit="°C"
              kind="model"
              source={MODEL_SOURCE}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Warga rentan merasakan pendinginan</span>
            <SourceChip
              value={formatNumber(result.vulnerable_benefiting, 0)}
              unit="jiwa"
              kind="model"
              source={`${MODEL_SOURCE} Sel dengan pendinginan minimal 0,5 °C.`}
              align="end"
            />
          </div>
          <div className={styles.metricLine}>
            <span>Perkiraan biaya</span>
            <SourceChip
              value={formatIdr(result.cost_idr).replace('Rp ', '')}
              unit=""
              kind="asumsi"
              source="Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml)."
              align="end"
            />
          </div>
        </div>
      ))}

      {extrapolated && (
        <div className={styles.warn}>
          Skenario ini <strong>di luar rentang data latih</strong> model, jadi angkanya
          kurang bisa dipercaya. Turunkan intensitas intervensi untuk hasil yang lebih
          dapat diandalkan.
        </div>
      )}

      {evidence.map((entry) => (
        <div key={entry.id} className={styles.evidence}>
          Pembanding literatur: {entry.source_title} ({entry.year}) melaporkan{' '}
          {formatUnit(entry.value_min, 'degC', 1)} sampai{' '}
          {formatUnit(entry.value_max, 'degC', 1)}
          {entry.comparable_to_model
            ? '.'
            : ' — perhatikan bahwa studi ini mengukur besaran lain, bukan pendinginan kawasan.'}
        </div>
      ))}

      <div className={styles.footer}>
        <span>{String(response.note ?? LST_FOOTNOTE)}</span>
      </div>
    </div>
  );
}

function OptimizeCard({ response, onSelect }: {
  response: Record<string, unknown>;
  onSelect: (id: string) => void;
}) {
  const packages = response.packages as {
    kel_id: string;
    kel_name: string;
    intervention_type: string;
    level: string;
    cost_idr: number;
    delta_lst_c: number;
    in_top_hvi_quintile: boolean;
  }[];

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        Rekomendasi portofolio · {packages.length} paket
      </div>

      <div className={styles.block}>
        <div className={styles.metricLine}>
          <span>Total biaya</span>
          <SourceChip
            value={formatIdr(response.total_cost_idr as number)}
            kind="asumsi"
            source="Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml)."
            align="end"
          />
        </div>
        <div className={styles.metricLine}>
          <span>Anggaran tersedia</span>
          <SourceChip
            value={formatIdr(response.budget_idr as number)}
            kind="input"
            source="Anggaran yang Anda masukkan."
            align="end"
          />
        </div>
        <div className={styles.metricLine}>
          <span>Porsi untuk kelurahan paling rentan</span>
          <SourceChip
            value={formatPercent(response.equity_share_achieved as number, 0)}
            kind="model"
            source={`${MODEL_SOURCE} Kendala minimum ${formatPercent(response.equity_share_requested as number, 0)}.`}
            align="end"
          />
        </div>
      </div>

      {packages.map((item) => (
        <button
          key={`${item.kel_id}-${item.intervention_type}`}
          type="button"
          className={styles.block}
          style={{ textAlign: 'left', width: '100%', border: 0, background: 'none', cursor: 'pointer' }}
          onClick={() => onSelect(item.kel_id)}
        >
          <strong>{item.kel_name}</strong> · {item.intervention_type} ({item.level}) ·{' '}
          {formatIdr(item.cost_idr)}
          {item.in_top_hvi_quintile && ' · kuintil teratas'}
        </button>
      ))}

      <div className={styles.footer}>
        <span>{String(response.note ?? LST_FOOTNOTE)}</span>
      </div>
    </div>
  );
}

export function ResultTable({ tool, response, onHighlight, onSelect }: ResultTableProps) {
  // A failed tool call renders no card: an empty table of dashes reads as missing data
  // rather than as a call that did not succeed.
  if (!response || 'error' in response) return null;

  if (tool === 'rank_priority_areas' && Array.isArray(response.areas)) {
    return (
      <RankCard
        areas={response.areas as RankedArea[]}
        onHighlight={onHighlight}
        onSelect={onSelect}
      />
    );
  }

  if (tool === 'simulate_intervention' && Array.isArray(response.results)) {
    return <SimulateCard response={response} />;
  }

  if (tool === 'optimize_portfolio' && Array.isArray(response.packages)) {
    return <OptimizeCard response={response} onSelect={onSelect} />;
  }

  return null;
}
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 13 tes baru.

- [ ] **Step 6: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/components/
git commit -m "feat(web): tambah kartu hasil tool yang dirender dari output terstruktur

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T12: Perakitan layar utama

**Files:**
- Modify: `web/app/page.tsx` (ganti halaman sementara dari M7-T6)
- Create: `web/app/page.module.css`

**Interfaces:**
- Consumes: semua komponen M7a dan M7b; `lib/api`, `lib/agent`.
- Produces: layar utama berfungsi dengan state tunggal sesuai `design/README.md` §State Management.

State yang dipegang: `layer`, `lang`, `selectedKelurahanId`, `hoverKelurahanId`, `priorityIds`, `showPriority`, `scenario`, `chat` (`messages`, `draft`, `busy`), `collection`, `sessionId`.

- [ ] **Step 1: Tulis `web/app/page.module.css`**

```css
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 65fr 35fr;
}

.left {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.mapArea {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}
```

- [ ] **Step 2: Tulis `web/app/page.tsx`**

```tsx
'use client';

/**
 * The main screen. All state lives here and flows down as props.
 *
 * No state library: design/README.md §State Management lists eight flat values, and keeping
 * them in one place is what makes the cross-panel flow -- hover a chat row, highlight the
 * map, click to open the drawer, pan the map clear of it -- readable in a single file. A
 * store would scatter that sequence across four modules for no gain at this size.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AgentPanel, type ChatMessage } from '@/components/AgentPanel';
import { Header } from '@/components/Header';
import { KelurahanDrawer } from '@/components/KelurahanDrawer';
import { MapOverlays } from '@/components/MapOverlays';
import { MapView } from '@/components/MapView';
import { EMPTY_SCENARIO, ScenarioDock, type ScenarioState } from '@/components/ScenarioDock';
import { createSession, streamAgent, type AgentStep } from '@/lib/agent';
import { fetchKelurahan, postSimulate } from '@/lib/api';
import { formatNumber } from '@/lib/format';
// LayerId is defined in lib/layers, not lib/types: it is a presentation concern, not an
// API shape.
import { type LayerId } from '@/lib/layers';
import type { KelurahanCollection } from '@/lib/types';
import styles from './page.module.css';

const USER_ID = 'perencana';

export default function Home() {
  const [collection, setCollection] = useState<KelurahanCollection | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [layer, setLayer] = useState<LayerId>('hvi');
  const [lang, setLang] = useState<'id' | 'en'>('id');
  const [query, setQuery] = useState('');

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [priorityIds, setPriorityIds] = useState<string[]>([]);
  const [showPriority, setShowPriority] = useState(true);

  const [scenario, setScenario] = useState<ScenarioState>(EMPTY_SCENARIO);
  const [scenarioStatus, setScenarioStatus] = useState(
    'Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan.',
  );
  const [scenarioBusy, setScenarioBusy] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    fetchKelurahan().then(setCollection).catch((error: Error) => setLoadError(error.message));
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || chatBusy) return;

      setDraft('');
      setChatBusy(true);
      const userId = `u-${Date.now()}`;
      setMessages((previous) => [
        ...previous,
        { id: userId, role: 'user', text: trimmed, steps: [] },
        { id: `a-${Date.now()}`, role: 'agent', text: '', steps: [] },
      ]);

      const started = Date.now();
      try {
        if (!sessionRef.current) sessionRef.current = await createSession(USER_ID);

        for await (const event of streamAgent({
          userId: USER_ID,
          sessionId: sessionRef.current,
          message: trimmed,
        })) {
          setMessages((previous) => {
            const next = [...previous];
            const last = next[next.length - 1];
            if (!last || last.role !== 'agent') return previous;

            if (event.kind === 'text') next[next.length - 1] = { ...last, text: event.text };
            if (event.kind === 'steps') {
              next[next.length - 1] = {
                ...last,
                steps: event.steps,
                elapsedMs: Date.now() - started,
              };
            }
            if (event.kind === 'error') {
              next[next.length - 1] = { ...last, error: event.message };
            }
            return next;
          });

          // Any tool that returned map_highlight drives the map, so the agent's answer and
          // the map never describe different kelurahan.
          if (event.kind === 'steps') {
            const highlight = event.steps
              .flatMap((step: AgentStep) => (step.response?.map_highlight as string[]) ?? [])
              .filter(Boolean);
            if (highlight.length) {
              setPriorityIds(highlight);
              setShowPriority(true);
            }
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Agen tidak bisa dihubungi.';
        setMessages((previous) => {
          const next = [...previous];
          const last = next[next.length - 1];
          if (last && last.role === 'agent') next[next.length - 1] = { ...last, error: message };
          return next;
        });
      } finally {
        setChatBusy(false);
      }
    },
    [chatBusy],
  );

  const runSimulation = useCallback(async () => {
    const targets = priorityIds.length ? priorityIds : selectedId ? [selectedId] : [];
    if (!targets.length) {
      setScenarioStatus('Pilih kelurahan di peta atau minta agen menyusun prioritas dulu.');
      return;
    }

    const interventions = [
      scenario.tree > 0 && {
        type: 'tree_planting',
        params: { canopy_increase_pp: scenario.tree },
      },
      scenario.coolRoof > 0 && {
        type: 'cool_roof',
        params: { adoption_rate: scenario.coolRoof / 100 },
      },
      scenario.greenRoof > 0 && {
        type: 'green_roof',
        params: { adoption_rate: scenario.greenRoof / 100 },
      },
    ].filter(Boolean) as { type: string; params: Record<string, number> }[];

    setScenarioBusy(true);
    setScenarioStatus('Menghitung…');
    try {
      const result = await postSimulate({ kel_ids: targets, interventions });
      const mean =
        result.results.reduce((total, row) => total + row.delta_lst_c, 0) / result.results.length;
      setScenarioStatus(
        `Perkiraan rata-rata ${formatNumber(mean, 2)} °C pada ${result.results.length} kelurahan · indikatif, suhu permukaan.`,
      );
    } catch (error) {
      setScenarioStatus(error instanceof Error ? error.message : 'Simulasi gagal.');
    } finally {
      setScenarioBusy(false);
    }
  }, [priorityIds, selectedId, scenario]);

  const scopeLabel = selectedId
    ? (collection?.features.find((f) => f.properties.kel_id === selectedId)?.properties
        .kota_name ?? 'DKI JAKARTA').toUpperCase()
    : 'DKI JAKARTA';

  return (
    <div className={styles.shell}>
      <Header
        layer={layer}
        onLayerChange={setLayer}
        lang={lang}
        onLangChange={setLang}
        query={query}
        onQueryChange={setQuery}
        onSearchSubmit={(value) => send(`Tampilkan profil panas untuk ${value}.`)}
      />

      <div className={styles.body}>
        <div className={styles.left}>
          <div className={styles.mapArea}>
            {loadError ? (
              <div style={{ padding: 'var(--panel-padding)' }}>{loadError}</div>
            ) : (
              <MapView
                collection={collection}
                layer={layer}
                selectedId={selectedId}
                hoverId={hoverId}
                priorityIds={priorityIds}
                showPriority={showPriority}
                drawerOpen={selectedId !== null}
                onHover={setHoverId}
                onSelect={setSelectedId}
              />
            )}

            <MapOverlays
              layer={layer}
              scopeLabel={scopeLabel}
              attribution={collection?.attribution ?? ''}
              priorityCount={showPriority ? priorityIds.length : 0}
              drawerOpen={selectedId !== null}
              onZoomIn={() => undefined}
              onZoomOut={() => undefined}
            />

            <KelurahanDrawer
              kelId={selectedId}
              onClose={() => setSelectedId(null)}
              onAskAgent={send}
            />
          </div>

          <ScenarioDock
            state={scenario}
            onChange={setScenario}
            targetLabel={
              priorityIds.length
                ? `Target: ${priorityIds.length} kelurahan prioritas`
                : selectedId
                  ? 'Target: 1 kelurahan terpilih'
                  : 'Target: belum dipilih'
            }
            status={scenarioStatus}
            busy={scenarioBusy}
            onSimulate={runSimulation}
          />
        </div>

        <AgentPanel
          messages={messages}
          draft={draft}
          busy={chatBusy}
          onDraftChange={setDraft}
          onSend={() => send(draft)}
          onNewThread={() => {
            setMessages([]);
            sessionRef.current = null;
            setPriorityIds([]);
          }}
          onHighlight={(ids) => {
            if (ids.length === 1) setHoverId(ids[0]);
            else if (ids.length === 0) setHoverId(null);
            else {
              setPriorityIds(ids);
              setShowPriority(true);
            }
          }}
          onSelect={setSelectedId}
        />
      </div>
    </div>
  );
}
```

Catatan: kontrol zoom diteruskan sebagai no-op di sini. Untuk mengaktifkannya, ekspos `zoomIn`/`zoomOut` dari `MapView` lewat `useImperativeHandle`, atau pindahkan `MapOverlays` ke dalam `MapView`. Kerjakan hanya kalau juri benar-benar perlu zoom — peta sudah terkunci ke `maxBounds` Jakarta.

- [ ] **Step 3: Jalankan dan uji rangkaian lengkap**

Pastikan API hidup (`uv run uvicorn api.main:app --port 8080`), lalu:

Run: `cd web && npm run dev`

Uji berurutan di `http://localhost:3000`:
1. Peta menampilkan 264 kelurahan dengan palet HVI.
2. Ganti lapisan ke Suhu Permukaan → fill, legenda, dan judul berubah; peta **tidak** satu warna rata.
3. Klik sebuah kelurahan → drawer terbuka, peta bergeser, overlay kanan bergeser ke 436 px.
4. Tanya agen: "Kelurahan mana di Jakarta Pusat yang paling perlu diprioritaskan?" → blok langkah kerja muncul dengan nama tool, kartu tabel muncul, peta menyorot kelurahan yang sama.
5. Hover baris tabel → kelurahan ter-outline di peta. Klik baris → drawer terbuka.
6. Geser slider Cool roof ke 50 → tombol Simulasikan aktif. Tekan → status menampilkan ΔLST dengan label indikatif.
7. Tab melalui halaman → setiap kontrol punya outline fokus hijau; chip sumber memunculkan tooltip saat difokuskan.

- [ ] **Step 4: Jalankan seluruh suite**

Run: `cd web && npm test`
Expected: hijau semua.

- [ ] **Step 5: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/app/
git commit -m "feat(web): rakit layar utama dengan state tunggal

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T13: Halaman Cek Atap

**Files:**
- Create: `web/app/cek-atap/page.tsx`, `web/app/cek-atap/page.module.css`
- Test: `web/app/cek-atap/page.test.tsx`

**Interfaces:**
- Consumes: `lib/api.postRoof`, `lib/types` (`RoofResponse`).
- Produces: halaman `/cek-atap` ramah ponsel dengan unggah foto, hasil klasifikasi, rekomendasi, dan peringatan keselamatan.

Prasyarat: **M6 selesai** (`POST /api/roof` ada).

- [ ] **Step 1: Tulis tes yang gagal**

`web/app/cek-atap/page.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CekAtap from './page';

const ASBESTOS = {
  roof: {
    roof_visible: true, roof_form: 'pitched', material: 'asbestos_cement',
    color_tone: 'medium', condition: 'worn', shade_from_trees: 'none',
    confidence: 0.82, notes: 'Atap bergelombang kelabu kusam.',
  },
  recommendation: {
    action: 'consult_professional', priority: 'tinggi',
    reason: 'Atap terindikasi asbes.',
    safety: ['JANGAN mengamplas, memotong, atau mengebor atap ini.'],
    evidence_ids: ['ev_green_curtain_tokyo'],
  },
  evidence: [],
  guidance: '',
  kelurahan: null,
  facts: [],
};

function mockRoof(payload: unknown = ASBESTOS) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ success: true, data: payload, error: null }),
    }),
  );
}

function photo() {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], 'atap.jpg', { type: 'image/jpeg' });
}

afterEach(() => vi.unstubAllGlobals());

describe('Cek Atap', () => {
  it('explains what to photograph before asking for a file', () => {
    render(<CekAtap />);
    expect(screen.getByText(/atap rumah/i)).toBeInTheDocument();
  });

  it('warns not to include identifying details in the frame', () => {
    // CLAUDE.md rule 8. The instruction has to be visible before the upload, not after.
    render(<CekAtap />);
    expect(screen.getByText(/nomor rumah|plat nomor|wajah/i)).toBeInTheDocument();
  });

  it('accepts only image files', () => {
    render(<CekAtap />);
    expect(screen.getByLabelText(/pilih foto/i)).toHaveAttribute('accept', 'image/jpeg,image/png');
  });

  it('shows the classification after upload', async () => {
    mockRoof();
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    expect(await screen.findByText(/asbes/i)).toBeInTheDocument();
  });

  it('shows the asbestos safety warning prominently', async () => {
    mockRoof();
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    const warning = await screen.findByRole('alert');
    expect(warning).toHaveTextContent(/JANGAN mengamplas/);
  });

  it('asks for a retake when confidence is low', async () => {
    mockRoof({
      ...ASBESTOS,
      roof: { ...ASBESTOS.roof, confidence: 0.3 },
      recommendation: { action: 'retake_photo', priority: '-', reason: 'Belum jelas.', safety: [], evidence_ids: [] },
      guidance: 'Coba foto ulang dari sudut yang memperlihatkan bidang atap.',
    });
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    expect(await screen.findByText(/foto ulang/i)).toBeInTheDocument();
  });

  it('surfaces a server error instead of silently doing nothing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 415,
      json: async () => ({ success: false, data: null, error: 'Format foto harus image/jpeg.' }),
    }));
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    expect(await screen.findByText(/Format foto harus/)).toBeInTheDocument();
  });

  it('states that the photo is not stored', async () => {
    // docs/DECISIONS.md: the photo never touches disk. Saying so is the point.
    render(<CekAtap />);
    expect(screen.getByText(/tidak disimpan/i)).toBeInTheDocument();
  });

  it('links back to the main screen', () => {
    render(<CekAtap />);
    expect(screen.getByRole('link', { name: /TEDUH/i })).toHaveAttribute('href', '/');
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./page"`

- [ ] **Step 3: Tulis `web/app/cek-atap/page.module.css`**

```css
.page {
  max-width: 560px;
  margin: 0 auto;
  padding: var(--space-9) var(--space-8) var(--space-11);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  color: var(--color-canopy);
  font-size: var(--text-logo);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-decoration: none;
}

.title {
  margin: var(--space-8) 0 var(--space-4);
  font-size: var(--text-kelurahan);
  font-weight: 700;
  line-height: var(--leading-heading);
}

.lead {
  font-size: var(--text-body);
  line-height: var(--leading-prose);
  color: var(--color-ink-secondary);
}

.privacy {
  margin-top: var(--space-6);
  padding: var(--space-5) var(--space-6);
  background: var(--color-canopy-tint);
  border-radius: var(--radius-md);
  font-size: var(--text-secondary);
  line-height: var(--leading-caption);
}

.picker {
  display: block;
  margin-top: var(--space-9);
  padding: var(--space-11) var(--space-8);
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  text-align: center;
  cursor: pointer;
}

.picker:hover,
.picker:focus-within {
  border-color: var(--color-canopy);
  background: var(--color-canopy-tint-hover);
}

.picker input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.preview {
  width: 100%;
  margin-top: var(--space-8);
  border-radius: var(--radius-lg);
}

.alert {
  margin-top: var(--space-8);
  padding: var(--space-6) var(--space-7);
  border: 2px solid var(--color-hot-strong);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--color-hot-strong);
  font-size: var(--text-body);
  font-weight: 600;
  line-height: var(--leading-body);
}

.card {
  margin-top: var(--space-8);
  padding: var(--space-7);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-3) 0;
  font-size: var(--text-secondary);
  border-bottom: 1px solid var(--color-border-row);
}

.error {
  margin-top: var(--space-8);
  padding: var(--space-6);
  border: 1px solid var(--color-hot-strong);
  border-radius: var(--radius-md);
  color: var(--color-hot-strong);
  font-size: var(--text-secondary);
}
```

- [ ] **Step 4: Tulis `web/app/cek-atap/page.tsx`**

```tsx
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
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 9 tes baru.

- [ ] **Step 6: Uji di lebar ponsel**

Buka `http://localhost:3000/cek-atap` dengan devtools pada 375 px. Pastikan tidak ada scroll horizontal, tombol pilih foto besar dan mudah ditekan, dan peringatan asbes terbaca tanpa zoom.

- [ ] **Step 7: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/app/cek-atap/
git commit -m "feat(web): tambah halaman Cek Atap ramah ponsel

Peringatan privasi dan larangan memotret detail identitas muncul SEBELUM pemilih
berkas, karena memberitahu setelah foto terkirim bukan kendali privasi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M7-T14: Halaman Tentang & Sumber Data

**Files:**
- Create: `web/app/sumber-data/page.tsx`
- Test: `web/app/sumber-data/page.test.tsx`

**Interfaces:**
- Consumes: `lib/api.fetchModelCard`, `lib/types.ModelCard`.
- Produces: halaman `/sumber-data` dengan atribusi lisensi dan model card.

Ini syarat submission (CONCEPT §16: "Halaman 'Tentang & Sumber Data' di aplikasi") dan mitigasi risiko lisensi (CONCEPT §14).

- [ ] **Step 1: Tulis tes yang gagal**

`web/app/sumber-data/page.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SumberData from './page';

const CARD = {
  version: 'lgbm@v1',
  target: 'Suhu permukaan tanah (LST), derajat Celsius',
  target_caveat: 'Model memprediksi suhu PERMUKAAN, bukan suhu udara.',
  data_period: '2023-2025 Jun-Sep (median musim kemarau)',
  area: 'DKI Jakarta daratan, tanpa Kepulauan Seribu',
  n_train_cells: 75603,
  n_kelurahan: 264,
  features: ['albedo', 'ndvi'],
  validation: {
    scheme: 'spatial block CV, blok 1000 m, GroupKFold 5 lipatan',
    why: 'LST sangat terautokorelasi pada 100 m.',
    summary: { r2_mean: 0.71, r2_min: 0.62, rmse_mean: 1.84, mae_mean: 1.42 },
    target_r2: 0.75,
    meets_target: false,
  },
  independent_checks: { worldpop_vs_dukcapil: 'Selisih 0,54 persen.' },
  limitations: ['Korelasional, bukan kausal.'],
};

function mockCard(payload: unknown = CARD) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200,
    json: async () => ({ success: true, data: payload, error: null }),
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('Sumber Data', () => {
  it('attributes every dataset the licences require', async () => {
    // CONCEPT §14 risk "Lisensi data". Missing attribution is a real compliance problem,
    // not a nicety.
    mockCard();
    render(<SumberData />);
    for (const name of [/WorldPop/, /ESA WorldCover/, /Open Buildings/, /Copernicus/, /Landsat/, /HDX/]) {
      expect(await screen.findByText(name)).toBeInTheDocument();
    }
  });

  it('shows the real cross-validated R squared, not a claim', async () => {
    mockCard();
    render(<SumberData />);
    expect(await screen.findByText(/0,71/)).toBeInTheDocument();
  });

  it('says plainly when the model misses its own target', async () => {
    // Honesty requirement: the proposal must not claim 0.75 if the model scored 0.71.
    mockCard();
    render(<SumberData />);
    expect(await screen.findByText(/belum mencapai target/i)).toBeInTheDocument();
  });

  it('confirms the target when it is met', async () => {
    mockCard({ ...CARD, validation: { ...CARD.validation, summary: { ...CARD.validation.summary, r2_mean: 0.79 }, meets_target: true } });
    render(<SumberData />);
    expect(await screen.findByText(/memenuhi target/i)).toBeInTheDocument();
  });

  it('states the validation scheme is spatial, not random', async () => {
    mockCard();
    render(<SumberData />);
    expect(await screen.findByText(/spatial block CV/)).toBeInTheDocument();
  });

  it('lists the model limitations', async () => {
    mockCard();
    render(<SumberData />);
    expect(await screen.findByText(/Korelasional, bukan kausal/)).toBeInTheDocument();
  });

  it('shows the independent population validation', async () => {
    mockCard();
    render(<SumberData />);
    expect(await screen.findByText(/0,54 persen/)).toBeInTheDocument();
  });

  it('still shows attribution when the model card is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: async () => ({ success: false, data: null, error: 'Model card belum tersedia.' }),
    }));
    render(<SumberData />);
    expect(await screen.findByText(/WorldPop/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `cd web && npm test`
Expected: FAIL — `Failed to resolve import "./page"`

- [ ] **Step 3: Tulis `web/app/sumber-data/page.tsx`**

```tsx
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
```

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `cd web && npm test`
Expected: PASS, 8 tes baru.

- [ ] **Step 5: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add web/app/sumber-data/
git commit -m "feat(web): tambah halaman Tentang & Sumber Data dengan model card

Halaman menyatakan terang-terangan kalau R2 belum mencapai target, bukan diam-diam
menampilkan target sebagai hasil.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M7b selesai

- [ ] Peta menampilkan 264 kelurahan dengan empat lapisan; ganti lapisan mengubah fill, legenda, judul, dan format nilai bersama-sama.
- [ ] Lapisan LST **tidak** satu warna rata — batas kelas berasal dari data nyata.
- [ ] Hover dan klik bekerja dari peta **maupun** dari baris kartu hasil chat; peta di-pan agar tidak tertutup drawer.
- [ ] Drawer menampilkan empat kartu angka, empat komponen HVI, bar SHAP divergen, dan tutupan lahan — **setiap angka memakai `SourceChip`**.
- [ ] Drawer menyatakan ketika jumlah kontribusi SHAP tidak sama dengan selisih rata-rata kota.
- [ ] Tombol Simulasikan terkunci sampai ada slider > 0; hasil berlabel indikatif dan suhu permukaan.
- [ ] Panel agen menampilkan blok langkah kerja dengan nama tool, dan kartu hasil dirender dari `functionResponse`, bukan dari prosa.
- [ ] Skenario ekstrapolasi diberi peringatan eksplisit di kartu.
- [ ] `/cek-atap` ramah ponsel 375 px, peringatan privasi muncul sebelum pemilih berkas, peringatan asbes memakai `role="alert"`.
- [ ] `/sumber-data` mengatribusi keenam sumber data dan menampilkan R² sebenarnya.
- [ ] `npm test` hijau; `npm run build` sukses.

**Selanjutnya:** [`m8-eval-deploy.md`](m8-eval-deploy.md) — evaluasi golden questions, evaluasi Cek Atap, dan deploy.
