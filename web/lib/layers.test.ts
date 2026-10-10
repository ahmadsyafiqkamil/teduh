import { describe, expect, it } from 'vitest';
import { LAYERS, LAYER_ORDER, NO_DATA_COLOR, colorForValue } from './layers';

describe('layer definitions', () => {
  it('declares exactly the layers the header offers', () => {
    expect(LAYER_ORDER).toEqual(['lst', 'hvi', 'veg', 'pop', 'dlst']);
  });

  it('gives every layer a palette one longer than its breaks', () => {
    // A palette of n colours needs n-1 thresholds; any other pairing silently drops a class.
    for (const id of LAYER_ORDER) {
      const layer = LAYERS[id];
      expect(layer.palette.length).toBe(layer.breaks.length + 1);
    }
  });

  it('keeps every break list ascending, except the descending ΔLST layer', () => {
    for (const id of LAYER_ORDER) {
      const { breaks, descending } = LAYERS[id];
      const sorted = [...breaks].sort((a, b) => a - b);
      if (descending) {
        expect(sorted).toEqual([...breaks].reverse());
      } else {
        expect(sorted).toEqual(breaks);
      }
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

  it('paints the ΔLST layer from the simulation delta, not an API column', () => {
    expect(LAYERS.dlst.property).toBe('delta_lst_c');
    expect(LAYERS.dlst.descending).toBe(true);
    expect(LAYERS.dlst.palette).toEqual([
      '#E6F2F8', '#A9D0E6', '#5FA3CB', '#2B78A8', '#1D5F8A',
    ]);
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

  it('paints stronger cooling (more negative) with a deeper blue', () => {
    expect(colorForValue(LAYERS.dlst, 0)).toBe(LAYERS.dlst.palette[0]);
    expect(colorForValue(LAYERS.dlst, -0.5)).toBe(LAYERS.dlst.palette[2]);
    expect(colorForValue(LAYERS.dlst, -1.0)).toBe(LAYERS.dlst.palette[4]);
  });

  it('paints a not-simulated ΔLST kelurahan as no-data', () => {
    expect(colorForValue(LAYERS.dlst, null)).toBe(NO_DATA_COLOR);
  });
});
