import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ResizeHandle } from './ResizeHandle';

function setup(overrides: Partial<React.ComponentProps<typeof ResizeHandle>> = {}) {
  const props = {
    axis: 'vertical' as const,
    getSize: () => 400,
    min: 280,
    max: 760,
    onResize: vi.fn(),
    label: 'Ubah lebar panel',
    ...overrides,
  };
  render(<ResizeHandle {...props} />);
  return props;
}

describe('ResizeHandle', () => {
  it('exposes a separator with the correct orientation', () => {
    setup({ axis: 'vertical' });
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'vertical');
  });

  it('uses a horizontal orientation when asked', () => {
    setup({ axis: 'horizontal' });
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'horizontal');
  });

  it('clamps a shrink at the minimum', async () => {
    const user = userEvent.setup();
    const props = setup({ getSize: () => 280, min: 280, max: 760 });

    const handle = screen.getByRole('separator');
    handle.focus();
    await user.keyboard('{ArrowRight}');

    // 280 - 16 would be 264, but the minimum clamps it back to 280.
    expect(props.onResize).toHaveBeenCalledWith(280);
  });

  it('grows the size with the opposite arrow', async () => {
    const user = userEvent.setup();
    const props = setup({ getSize: () => 400 });

    screen.getByRole('separator').focus();
    await user.keyboard('{ArrowLeft}');

    expect(props.onResize).toHaveBeenCalledWith(416);
  });

  it('resets to null on Home', async () => {
    const user = userEvent.setup();
    const props = setup();

    screen.getByRole('separator').focus();
    await user.keyboard('{Home}');

    expect(props.onResize).toHaveBeenCalledWith(null);
  });

  it('labels itself for screen readers', () => {
    setup({ label: 'Ubah tinggi panel simulasi' });
    expect(screen.getByRole('separator')).toHaveAccessibleName('Ubah tinggi panel simulasi');
  });
});
