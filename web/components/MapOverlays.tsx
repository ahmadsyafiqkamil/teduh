'use client';

/**
 * Everything floating above the map: scope card, zoom, legend, attribution.
 *
 * The legend reads its ramp, breaks, and copy from lib/layers so it cannot describe a
 * different layer than the one being painted. The right-hand overlays shift when the
 * drawer opens, per design/README.md §2.
 */

import { Minus, Plus } from 'lucide-react';
import { LAYERS, type LayerId } from '@/lib/layers';
import styles from './MapOverlays.module.css';

const DRAWER_OFFSET = '436px';
const EDGE_OFFSET = '16px';

interface MapOverlaysProps {
  layer: LayerId;
  scopeLabel: string;
  attribution: string;
  priorityCount: number;
  drawerOpen: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function MapOverlays({
  layer,
  scopeLabel,
  attribution,
  priorityCount,
  drawerOpen,
  onZoomIn,
  onZoomOut,
}: MapOverlaysProps) {
  const definition = LAYERS[layer];
  const right = drawerOpen ? DRAWER_OFFSET : EDGE_OFFSET;

  return (
    <>
      <div className={styles.titleCard}>
        <div className="kicker">{scopeLabel}</div>
        <div className={styles.layerTitle}>{definition.title}</div>
      </div>

      <div className={styles.zoom} style={{ right }}>
        <button type="button" className={styles.zoomButton} onClick={onZoomIn} aria-label="Perbesar peta">
          <Plus size={16} />
        </button>
        <button type="button" className={styles.zoomButton} onClick={onZoomOut} aria-label="Perkecil peta">
          <Minus size={16} />
        </button>
      </div>

      <div className={styles.legend} style={{ right }} data-testid="legend">
        <div className={styles.legendTitle}>{definition.legendTitle}</div>
        <div className={styles.legendSubtitle}>{definition.legendSubtitle}</div>

        <div className={styles.ramp}>
          {definition.palette.map((colour) => (
            <span
              key={colour}
              className={styles.swatch}
              style={{ background: colour }}
              data-testid="legend-swatch"
            />
          ))}
        </div>

        <div className={styles.ticks}>
          {definition.breaks.map((threshold) => (
            <span key={threshold}>{definition.format(threshold)}</span>
          ))}
        </div>

        {priorityCount > 0 && (
          <div className={styles.priorityRow}>
            <span className={styles.prioritySwatch} aria-hidden="true" />
            {priorityCount} kelurahan prioritas dari jawaban agen
          </div>
        )}
      </div>

      <div className={styles.attribution}>{attribution}</div>
    </>
  );
}
