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
