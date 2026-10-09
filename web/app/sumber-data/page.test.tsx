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
      // "Copernicus" names two datasets, so a dataset may legitimately match more than once.
      expect((await screen.findAllByText(name)).length).toBeGreaterThanOrEqual(1);
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
