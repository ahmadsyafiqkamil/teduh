import { fireEvent, render, screen } from '@testing-library/react';
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

  it('reports a slider change', () => {
    const props = setup();

    const canopy = screen.getByLabelText(/tambah kanopi pohon/i);
    fireEvent.change(canopy, { target: { value: '3' } });

    expect(props.onChange).toHaveBeenCalledWith(expect.objectContaining({ tree: 3 }));
  });

  it('shows the canopy value with its pp suffix', () => {
    setup({ state: { ...EMPTY_SCENARIO, tree: 7 } });
    expect(screen.getByText('+7 pp')).toBeInTheDocument();
  });

  it('shows roof adoption as a percentage', () => {
    setup({ state: { ...EMPTY_SCENARIO, coolRoof: 50 } });
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('formats the budget with Indonesian thousands separators while typing', () => {
    const props = setup();

    // The displayed value carries dot separators (id-ID); typing them back in must not
    // multiply the budget by a thousand, so only digits survive into the parsed number.
    fireEvent.change(screen.getByLabelText(/anggaran/i), { target: { value: '2.000.000.000' } });

    expect(props.onChange).toHaveBeenCalledWith(expect.objectContaining({ budget: 2_000_000_000 }));
  });

  it('ignores non-digits in the budget field', () => {
    const props = setup();

    fireEvent.change(screen.getByLabelText(/anggaran/i), { target: { value: 'abc' } });

    expect(props.onChange).toHaveBeenCalledWith(expect.objectContaining({ budget: null }));
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
