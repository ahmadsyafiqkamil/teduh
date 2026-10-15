import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { EMPTY_SCENARIO, ScenarioDock } from './ScenarioDock';

function setup(overrides = {}) {
  const props = {
    state: EMPTY_SCENARIO,
    onChange: vi.fn(),
    mode: 'simulate' as const,
    onModeChange: vi.fn(),
    targetLabel: 'Target: 5 kelurahan prioritas',
    status: 'Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan.',
    busy: false,
    onSimulate: vi.fn(),
    onOptimize: vi.fn(),
    multiSelect: false,
    pickedCount: 0,
    onToggleMultiSelect: vi.fn(),
    onClearPicked: vi.fn(),
    hasResult: false,
    onClearResult: vi.fn(),
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
    const props = setup({ mode: 'optimize' });

    // The displayed value carries dot separators (id-ID); typing them back in must not
    // multiply the budget by a thousand, so only digits survive into the parsed number.
    fireEvent.change(screen.getByLabelText(/anggaran/i), { target: { value: '2.000.000.000' } });

    expect(props.onChange).toHaveBeenCalledWith(expect.objectContaining({ budget: 2_000_000_000 }));
  });

  it('ignores non-digits in the budget field', () => {
    const props = setup({ mode: 'optimize' });

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

  it('shows the budget instead of the sliders in optimize mode', () => {
    setup({ mode: 'optimize' });
    expect(screen.getByLabelText(/anggaran/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/porsi keadilan/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/tambah kanopi pohon/i)).not.toBeInTheDocument();
  });

  it('disables Optimalkan until a budget is entered', () => {
    setup({ mode: 'optimize' });
    expect(screen.getByRole('button', { name: /optimalkan/i })).toBeDisabled();
  });

  it('enables Optimalkan once a budget is set', () => {
    setup({ mode: 'optimize', state: { ...EMPTY_SCENARIO, budget: 1_000_000_000 } });
    expect(screen.getByRole('button', { name: /optimalkan/i })).toBeEnabled();
  });

  it('runs the optimization on click', async () => {
    const user = userEvent.setup();
    const props = setup({ mode: 'optimize', state: { ...EMPTY_SCENARIO, budget: 1_000_000_000 } });

    await user.click(screen.getByRole('button', { name: /optimalkan/i }));

    expect(props.onOptimize).toHaveBeenCalled();
  });

  it('switches mode via the toggle', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.click(screen.getByRole('tab', { name: /optimalkan/i }));

    expect(props.onModeChange).toHaveBeenCalledWith('optimize');
  });

  it('hides the clear-result link when there is no result', () => {
    setup();
    expect(screen.queryByRole('button', { name: /hapus hasil/i })).not.toBeInTheDocument();
  });

  it('shows the clear-result link once a result exists', () => {
    setup({ hasResult: true });
    expect(screen.getByRole('button', { name: /hapus hasil/i })).toBeInTheDocument();
  });

  it('clears the result on click', async () => {
    const user = userEvent.setup();
    const props = setup({ hasResult: true });

    await user.click(screen.getByRole('button', { name: /hapus hasil/i }));

    expect(props.onClearResult).toHaveBeenCalled();
  });
});
