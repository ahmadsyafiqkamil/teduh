import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Header } from './Header';

function setup(overrides = {}) {
  const props = {
    layer: 'hvi' as const,
    onLayerChange: vi.fn(),
    lang: 'id' as const,
    onLangChange: vi.fn(),
    query: '',
    onQueryChange: vi.fn(),
    onSearchSubmit: vi.fn(),
    ...overrides,
  };
  render(<Header {...props} />);
  return props;
}

describe('Header', () => {
  it('offers all four layers', () => {
    setup();
    const group = screen.getByRole('group', { name: /lapisan/i });
    expect(group.querySelectorAll('button')).toHaveLength(4);
  });

  it('marks the active layer with aria-pressed', () => {
    setup({ layer: 'lst' });
    expect(screen.getByRole('button', { name: /suhu permukaan/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: /vegetasi/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('reports a layer change', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.click(screen.getByRole('button', { name: /vegetasi/i }));

    expect(props.onLayerChange).toHaveBeenCalledWith('veg');
  });

  it('states the coverage next to the brand', () => {
    setup();
    expect(screen.getByText(/DKI Jakarta/)).toBeInTheDocument();
  });

  it('submits the search on Enter', async () => {
    const user = userEvent.setup();
    const props = setup({ query: 'Kampung Rawa' });

    await user.type(screen.getByPlaceholderText(/cari kelurahan/i), '{Enter}');

    expect(props.onSearchSubmit).toHaveBeenCalledWith('Kampung Rawa');
  });

  it('reports typing in the search box', async () => {
    const user = userEvent.setup();
    const props = setup();

    await user.type(screen.getByPlaceholderText(/cari kelurahan/i), 'S');

    expect(props.onQueryChange).toHaveBeenCalledWith('S');
  });

  it('toggles the language', async () => {
    const user = userEvent.setup();
    const props = setup({ lang: 'id' });

    await user.click(screen.getByRole('button', { name: 'EN' }));

    expect(props.onLangChange).toHaveBeenCalledWith('en');
  });

  it('marks the active language', () => {
    setup({ lang: 'id' });
    expect(screen.getByRole('button', { name: 'ID' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('links to the sources page', () => {
    setup();
    expect(screen.getByRole('link', { name: /sumber data/i })).toHaveAttribute(
      'href',
      '/sumber-data',
    );
  });

  it('labels the navigation for screen readers', () => {
    setup();
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
