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
    // "indikatif" appears in both the card head and the footer note.
    expect(screen.getAllByText(/indikatif/i).length).toBeGreaterThanOrEqual(1);
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
    // The total also appears inside the package line, so it may match more than once.
    expect(screen.getAllByText(/Rp 950\.000\.000/).length).toBeGreaterThanOrEqual(1);
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
