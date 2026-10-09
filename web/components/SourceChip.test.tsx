import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SourceChip, kindForSource } from './SourceChip';

describe('kindForSource', () => {
  it('maps the data token', () => {
    expect(kindForSource('data:grid_features@v1')).toBe('data');
  });

  it('maps the model token', () => {
    expect(kindForSource('model:lgbm@v1')).toBe('model');
  });

  it('maps an evidence token to literature', () => {
    expect(kindForSource('evidence:ev_ndvi_kl_2025')).toBe('literatur');
  });

  it('maps an assumption token', () => {
    expect(kindForSource('assumption:cool_roof.albedo_cool')).toBe('asumsi');
    expect(kindForSource('ASUMSI')).toBe('asumsi');
  });

  it('treats a literal citation as data rather than an assumption', () => {
    // A Kepgub citation is a real source; showing it as "ASUMSI · dapat diedit" would be
    // the opposite of the truth.
    expect(kindForSource('Kepgub DKI 811/2025, item 696.19, hlm 1262')).toBe('data');
  });
});

describe('SourceChip', () => {
  it('renders the value and unit together', () => {
    render(<SourceChip value="44,61" unit="°C" kind="data" source="Data satelit" />);
    expect(screen.getByText(/44,61/)).toBeInTheDocument();
  });

  it('is reachable by keyboard', () => {
    render(<SourceChip value="0,93" kind="data" source="Data satelit" />);
    expect(screen.getByRole('button')).toHaveAttribute('tabindex', '0');
  });

  it('shows the tooltip on focus, not only on hover', async () => {
    // Accessibility: a mouse-only tooltip hides the provenance from keyboard and
    // screen-reader users, which is the whole feature.
    const user = userEvent.setup();
    render(<SourceChip value="0,93" kind="data" source="Data satelit TEDUH" />);

    await user.tab();

    expect(screen.getByRole('tooltip')).toHaveTextContent('Data satelit TEDUH');
  });

  it('shows the tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="0,93" kind="model" source="Model TEDUH" />);

    await user.hover(screen.getByRole('button'));

    expect(screen.getByRole('tooltip')).toHaveTextContent('Model TEDUH');
  });

  it('labels each kind with its own kicker', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="95.000" kind="asumsi" source="Harga satuan TEDUH" />);

    await user.tab();

    expect(screen.getByRole('tooltip')).toHaveTextContent('ASUMSI');
  });

  it('uses a dashed underline for an assumption and dotted otherwise', () => {
    const { rerender } = render(
      <SourceChip value="1" kind="data" source="x" />,
    );
    const dotted = screen.getByRole('button').className;

    rerender(<SourceChip value="1" kind="asumsi" source="x" />);
    expect(screen.getByRole('button').className).not.toBe(dotted);
  });

  it('hides the tooltip again on blur', async () => {
    const user = userEvent.setup();
    render(<SourceChip value="1" kind="data" source="x" />);

    await user.tab();
    await user.tab();

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});
