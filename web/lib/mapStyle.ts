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
  pickedHalo: 'picked-halo',
  pickedOutline: 'picked-outline',
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
  if (layer.descending) {
    // Stronger cooling is more negative but deeper in colour, so the default is the deepest
    // palette entry and each ascending stop steps back toward the lightest.
    const ascending = [...layer.breaks].sort((a, b) => a - b);
    const step: unknown[] = [
      'step',
      ['get', layer.property],
      layer.palette[layer.palette.length - 1],
    ];
    ascending.forEach((threshold, index) => {
      step.push(threshold, layer.palette[layer.palette.length - 2 - index]);
    });
    return ['case', ['==', ['get', layer.property], null], NO_DATA_COLOR, step];
  }

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
