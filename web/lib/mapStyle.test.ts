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

  it('defaults the ΔLST layer to its deepest blue for strong cooling', () => {
    // Below the lowest break (-0.8) the step falls back to its default, which must be the
    // deepest palette entry, not the lightest: more negative is deeper, not hotter.
    const expression = fillColorExpression(LAYERS.dlst) as unknown[];
    const step = expression[3] as unknown[];
    expect(step[2]).toBe(LAYERS.dlst.palette[LAYERS.dlst.palette.length - 1]);
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
