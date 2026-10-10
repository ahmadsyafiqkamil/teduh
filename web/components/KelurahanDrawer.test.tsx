import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ProfileResponse } from '@/lib/types';
import { KelurahanDrawer } from './KelurahanDrawer';

const PROFILE: ProfileResponse = {
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

function renderDrawer(overrides: Partial<React.ComponentProps<typeof KelurahanDrawer>> = {}) {
  const props = {
    kelId: 'ID3173040002' as string | null,
    onClose: vi.fn(),
    onAskAgent: vi.fn(),
    width: null,
    onResize: vi.fn(),
    ...overrides,
  };
  render(<KelurahanDrawer {...props} />);
  return props;
}

afterEach(() => vi.unstubAllGlobals());

describe('KelurahanDrawer', () => {
  it('renders nothing when no kelurahan is selected', () => {
    renderDrawer({ kelId: null });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is a labelled dialog', async () => {
    mockProfile();
    renderDrawer();
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());
  });

  it('shows the name and the administrative location', async () => {
    mockProfile();
    renderDrawer();
    await screen.findByText('Kampung Rawa');
    expect(screen.getByText(/Johar Baru/)).toBeInTheDocument();
    expect(screen.getByText(/Jakarta Pusat/)).toBeInTheDocument();
  });

  it('states the HVI rank out of the real total', async () => {
    // Never 267: that was the design's sample figure.
    mockProfile();
    renderDrawer();
    expect(await screen.findByText(/1 dari 264/)).toBeInTheDocument();
  });

  it('shows the anomaly with an explicit sign', async () => {
    mockProfile();
    renderDrawer();
    expect(await screen.findByText(/\+2,77/)).toBeInTheDocument();
  });

  it('renders every number inside a source chip', async () => {
    // design/README.md: "Wajib dipakai untuk setiap angka di UI."
    mockProfile();
    renderDrawer();
    await screen.findByText('Kampung Rawa');
    const chips = screen.getAllByRole('button').filter((node) => node.className.includes('chip'));
    expect(chips.length).toBeGreaterThanOrEqual(8);
  });

  it('shows all four HVI components with the formula', async () => {
    mockProfile();
    renderDrawer();
    await screen.findByText('Bahaya (panas permukaan)');
    expect(screen.getByText('Keterpaparan (kepadatan penduduk)')).toBeInTheDocument();
    expect(screen.getByText('Kepekaan (balita & lansia)')).toBeInTheDocument();
    expect(screen.getByText('Kurangnya kapasitas adaptif')).toBeInTheDocument();
    expect(screen.getByText(/HVI = /)).toBeInTheDocument();
  });

  it('lists the SHAP drivers with their direction', async () => {
    mockProfile();
    renderDrawer();
    expect(await screen.findByText('Fraksi lahan terbangun')).toBeInTheDocument();
    expect(screen.getByText(/memanaskan/)).toBeInTheDocument();
    expect(screen.getByText(/mendinginkan/)).toBeInTheDocument();
  });

  it('warns when the driver contributions do not sum to the anomaly', async () => {
    // design/README.md: "Jumlah kontribusi harus = selisih LST (validasi di backend)."
    // 1.2 + 0.8 - 0.3 = 1.7, not 2.768, so the drawer must say so rather than imply it adds up.
    mockProfile();
    renderDrawer();
    expect(await screen.findByText(/tidak menjumlah/i)).toBeInTheDocument();
  });

  it('says plainly when SHAP is unavailable', async () => {
    mockProfile({ ...PROFILE, drivers: [], drivers_unavailable: 'Artefak SHAP belum dibuat.' });
    renderDrawer();
    expect(await screen.findByText(/belum dibuat/i)).toBeInTheDocument();
  });

  it('carries the surface-temperature footnote', async () => {
    mockProfile();
    renderDrawer();
    expect(await screen.findByText(/bukan suhu udara/i)).toBeInTheDocument();
  });

  it('hands a prepared prompt to the agent', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onAskAgent = vi.fn();
    renderDrawer({ onAskAgent });

    await user.click(await screen.findByRole('button', { name: /tanya agen/i }));

    expect(onAskAgent).toHaveBeenCalledWith(expect.stringContaining('Kampung Rawa'));
  });

  it('closes on the close button', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDrawer({ onClose });

    await user.click(await screen.findByRole('button', { name: /tutup/i }));

    expect(onClose).toHaveBeenCalled();
  });

  it('closes on Escape', async () => {
    mockProfile();
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDrawer({ onClose });
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
    renderDrawer({ kelId: "ID9999999999" });
    expect(await screen.findByText(/tidak ada/i)).toBeInTheDocument();
  });
});
