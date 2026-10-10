/**
 * The four map layers: palette, class breaks, legend copy, and value formatting.
 *
 * Single source of truth on purpose. The choropleth fill, the legend ramp, the hover
 * tooltip, and the map title all read from here, so switching layers cannot leave a legend
 * describing the previous one. Palettes are copied verbatim from design/README.md §2.
 *
 * The LST and population breaks are NOT the ones in the design handoff. Those were built
 * against sample data with a city mean of 34.3 °C; the real mean is 41.84 °C, so the
 * design's breaks would paint all 264 kelurahan in the top class. The values below come
 * from quantiles of data/processed/kelurahan_metrics.parquet (see m7a plan, Task M7-T2
 * Step 1).
 */

import { formatNumber, formatPercent, formatUnit } from './format';

export type LayerId = 'lst' | 'hvi' | 'veg' | 'pop' | 'dlst';

export const LAYER_ORDER: LayerId[] = ['lst', 'hvi', 'veg', 'pop', 'dlst'];

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
  /**
   * True when a HIGHER value maps to the LIGHTER palette end instead of the darker one.
   * ΔLST is the only such layer: more negative (stronger cooling) is deeper blue, so it is
   * stored with descending breaks and painted with the palette reversed.
   */
  descending?: boolean;
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
    // Quantiles of data/processed/kelurahan_metrics.parquet (Task M7-T2 Step 1):
    // [41.08, 41.69, 42.19, 42.69, 43.22, 43.67], rounded to the nearest 0.5 °C.
    breaks: [41.0, 41.5, 42.0, 42.5, 43.0, 43.5],
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
    // Quantiles of data/processed/kelurahan_metrics.parquet (Task M7-T2 Step 1):
    // [15110.8, 18491.2, 21594.4, 25257.7], rounded to the nearest 1 000 jiwa/km².
    breaks: [15_000, 18_000, 22_000, 25_000],
    format: (value) => formatNumber(value, 0),
  },
  dlst: {
    id: 'dlst',
    label: 'ΔLST Simulasi',
    swatch: '#2B78A8',
    property: 'delta_lst_c',
    title: 'Perubahan suhu permukaan (ΔLST)',
    legendTitle: 'Perubahan suhu permukaan (ΔLST), °C',
    legendSubtitle: 'Hasil simulasi, indikatif · makin pekat makin turun',
    palette: ['#E6F2F8', '#A9D0E6', '#5FA3CB', '#2B78A8', '#1D5F8A'],
    // Stored in display (descending) order: 0 on the left, stronger cooling to the right.
    breaks: [-0.2, -0.4, -0.6, -0.8],
    format: (value) => formatUnit(value, 'degC', 1),
    descending: true,
  },
};

export function colorForValue(layer: LayerDefinition, value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA_COLOR;

  if (layer.descending) {
    const ascending = [...layer.breaks].sort((a, b) => a - b);
    for (let index = 0; index < ascending.length; index += 1) {
      if (value < ascending[index]) return layer.palette[layer.palette.length - 1 - index];
    }
    return layer.palette[0];
  }

  for (let index = 0; index < layer.breaks.length; index += 1) {
    if (value < layer.breaks[index]) return layer.palette[index];
  }
  return layer.palette[layer.palette.length - 1];
}
