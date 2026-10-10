'use client';

/**
 * A draggable separator with keyboard support.
 *
 * The separator sits in the column/row that divides two panels; the panel is always on the
 * side after the separator, so the math is uniform: `next = startSize - delta`. The current
 * size is read through a getSize() callback rather than a prop so the initial value can stay
 * in CSS (px is only known once the user has dragged once), which is also what makes this
 * testable in jsdom where offsetWidth is 0.
 *
 * onResize receives a number for a concrete size and null for "reset to the CSS default".
 */

import { useRef } from 'react';
import { KEYBOARD_STEP_PX, clampPx } from '@/lib/resize';
import styles from './ResizeHandle.module.css';

export interface ResizeHandleProps {
  /** vertical = drags left/right; horizontal = drags up/down. */
  axis: 'vertical' | 'horizontal';
  /** Current panel size in px. */
  getSize: () => number;
  min: number;
  max: number;
  /** null resets the panel to its CSS default. */
  onResize: (next: number | null) => void;
  /** aria-label, Bahasa Indonesia. */
  label: string;
}

export function ResizeHandle({
  axis,
  getSize,
  min,
  max,
  onResize,
  label,
}: ResizeHandleProps) {
  const start = useRef<{ coord: number; size: number } | null>(null);

  const horizontal = axis === 'horizontal';

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    start.current = { coord: horizontal ? event.clientY : event.clientX, size: getSize() };
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!start.current) return;
    const coord = horizontal ? event.clientY : event.clientX;
    const delta = coord - start.current.coord;
    onResize(clampPx(start.current.size - delta, min, max));
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    start.current = null;
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Home') {
      event.preventDefault();
      onResize(null);
      return;
    }
    // The panel sits after the separator, so the pointer math is `next = size - delta`:
    // moving toward the panel shrinks it, moving away grows it. Arrows mirror that.
    const grow = horizontal ? 'ArrowUp' : 'ArrowLeft';
    const shrink = horizontal ? 'ArrowDown' : 'ArrowRight';
    if (event.key === grow || event.key === shrink) {
      event.preventDefault();
      const step = event.key === grow ? KEYBOARD_STEP_PX : -KEYBOARD_STEP_PX;
      onResize(clampPx(getSize() + step, min, max));
    }
  };

  return (
    <div
      role="separator"
      aria-orientation={horizontal ? 'horizontal' : 'vertical'}
      aria-label={label}
      tabIndex={0}
      className={`${styles.handle} ${horizontal ? styles.horizontal : styles.vertical}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onKeyDown={onKeyDown}
    />
  );
}
