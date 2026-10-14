'use client';

/**
 * Everything floating above the map: scope card, zoom, legend, attribution.
 *
 * The legend reads its ramp, breaks, and copy from lib/layers so it cannot describe a
 * different layer than the one being painted. The right-hand overlays shift when the
 * drawer opens, per design/README.md §2.
 */

import { Minus, Plus } from 'lucide-react';
import { LAYERS, layerCopy, type LayerId } from '@/lib/layers';
import { t, type Lang } from '@/lib/i18n';
import styles from './MapOverlays.module.css';

const DRAWER_OFFSET = '436px';
const EDGE_OFFSET = '16px';

interface MapOverlaysProps {
  layer: LayerId;
  lang?: Lang;
  scopeLabel: string;
  attribution: string;
  priorityCount: number;
  drawerOpen: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function MapOverlays({
  layer,
  lang = 'id',
  scopeLabel,
  attribution,
  priorityCount,
  drawerOpen,
  onZoomIn,
  onZoomOut,
}: MapOverlaysProps) {
  const definition = LAYERS[layer];
  const copy = layerCopy(definition, lang);
  const right = drawerOpen ? DRAWER_OFFSET : EDGE_OFFSET;

  return (
    <>
      <div className={styles.titleCard}>
        <div className="kicker">{scopeLabel}</div>
        <div className={styles.layerTitle}>{copy.title}</div>
      </div>

      <div className={styles.zoom} style={{ right }}>
        <button type="button" className={styles.zoomButton} onClick={onZoomIn} aria-label={t(lang, 'map.zoomIn')}>
          <Plus size={16} />
        </button>
        <button type="button" className={styles.zoomButton} onClick={onZoomOut} aria-label={t(lang, 'map.zoomOut')}>
          <Minus size={16} />
        </button>
      </div>

      <div className={styles.legend} style={{ right }} data-testid="legend">
        <div className={styles.legendTitle}>{copy.legendTitle}</div>
        <div className={styles.legendSubtitle}>{copy.legendSubtitle}</div>

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
          {(definition.descending ? [0, ...definition.breaks] : definition.breaks).map(
            (threshold) => (
              <span key={threshold}>{definition.format(threshold)}</span>
            ),
          )}
        </div>

        {priorityCount > 0 && (
          <div className={styles.priorityRow}>
            <span className={styles.prioritySwatch} aria-hidden="true" />
            {t(lang, 'map.priority', { n: priorityCount })}
          </div>
        )}
      </div>

      <div className={styles.attribution}>{attribution}</div>
    </>
  );
}
