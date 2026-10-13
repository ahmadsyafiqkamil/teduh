'use client';

/**
 * The choropleth.
 *
 * Hover and selection are driven by feature state rather than by re-setting the GeoJSON
 * source, because re-setting 264 MultiPolygons on every mouse move drops frames badly.
 * The priority markers are HTML elements positioned by map.project() rather than symbol
 * layers, which avoids needing a glyph server for five numbers.
 */

import { Map as MapLibreMap, setWorkerUrl, type GeoJSONSource } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { LAYERS, type LayerId } from '@/lib/layers';
import {
  BASE_STYLE,
  JAKARTA_BOUNDS,
  JAKARTA_CENTER,
  LAYER_IDS,
  SOURCE_ID,
  centroidOf,
  fillColorExpression,
} from '@/lib/mapStyle';
import type { KelurahanCollection, KelurahanProperties } from '@/lib/types';
import styles from './MapView.module.css';

// MapLibre v6 derives its worker URL from `import.meta.url`, which under Turbopack points
// at /_next/static/chunks/ — a directory the worker file is never emitted into, so the
// worker 404s and nothing is ever rendered. The copy in public/ is kept in sync with the
// installed version by the predev/prebuild script in package.json.
setWorkerUrl('/maplibre-gl-worker.mjs');

const PAN_DURATION_MS = 300;

interface MapViewProps {
  collection: KelurahanCollection | null;
  layer: LayerId;
  selectedId: string | null;
  hoverId: string | null;
  priorityIds: string[];
  pickedIds: string[];
  showPriority: boolean;
  drawerOpen: boolean;
  /** Current drawer width in px; the map pans by half of it so the selection stays visible. */
  drawerWidth: number;
  onHover: (kelId: string | null) => void;
  onSelect: (kelId: string) => void;
}

export function MapView({
  collection,
  layer,
  selectedId,
  hoverId,
  priorityIds,
  pickedIds,
  showPriority,
  drawerOpen,
  drawerWidth,
  onHover,
  onSelect,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [markers, setMarkers] = useState<{ id: string; x: number; y: number; rank: number }[]>(
    [],
  );

  const definition = LAYERS[layer];

  const centroids = useMemo(() => {
    if (!collection) return new Map<string, [number, number]>();
    return new Map(
      collection.features.map((feature) => [
        feature.properties.kel_id,
        centroidOf(feature),
      ]),
    );
  }, [collection]);

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASE_STYLE,
      center: JAKARTA_CENTER,
      zoom: 10.2,
      maxBounds: JAKARTA_BOUNDS,
      attributionControl: false,
    });
    mapRef.current = map;
    map.on('load', () => setReady(true));

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add the source and layers once both the map and the data exist.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !collection || map.getSource(SOURCE_ID)) return;

    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: collection,
      promoteId: 'kel_id',
    });

    map.addLayer({
      id: LAYER_IDS.fill,
      type: 'fill',
      source: SOURCE_ID,
      paint: { 'fill-color': fillColorExpression(definition) as never },
    });

    map.addLayer({
      id: LAYER_IDS.outline,
      type: 'line',
      source: SOURCE_ID,
      paint: { 'line-color': '#FFFFFF', 'line-width': 0.9 },
    });

    map.addLayer({
      id: LAYER_IDS.hover,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1C2321',
        'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 1.6, 0],
      },
    });

    map.addLayer({
      id: LAYER_IDS.selected,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1C2321',
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2.4, 0],
        'line-dasharray': [5, 3],
      },
    });

    // White halo beneath the green outline, per design/README.md §2.
    map.addLayer({
      id: LAYER_IDS.priorityHalo,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#FFFFFF',
        'line-width': ['case', ['boolean', ['feature-state', 'priority'], false], 6, 0],
      },
    });
    map.addLayer({
      id: LAYER_IDS.priorityOutline,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1F5C4A',
        'line-width': ['case', ['boolean', ['feature-state', 'priority'], false], 3.4, 0],
      },
    });

    // Manually picked kelurahan (multi-select). Distinct from the agent's green priority
    // outline and the single dashed selection, so a planner can tell "picked by hand" apart
    // from "suggested by the agent" at a glance.
    map.addLayer({
      id: LAYER_IDS.pickedHalo,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#FFFFFF',
        'line-width': ['case', ['boolean', ['feature-state', 'picked'], false], 6, 0],
      },
    });
    map.addLayer({
      id: LAYER_IDS.pickedOutline,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#1D5F8A',
        'line-width': ['case', ['boolean', ['feature-state', 'picked'], false], 2.6, 0],
      },
    });

    let hovered: string | null = null;
    map.on('mousemove', LAYER_IDS.fill, (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const id = String(feature.id);
      if (hovered === id) return;
      if (hovered) {
        map.setFeatureState({ source: SOURCE_ID, id: hovered }, { hover: false });
      }
      hovered = id;
      map.setFeatureState({ source: SOURCE_ID, id }, { hover: true });
      map.getCanvas().style.cursor = 'pointer';
      onHover(id);
    });

    map.on('mouseleave', LAYER_IDS.fill, () => {
      if (hovered) {
        map.setFeatureState({ source: SOURCE_ID, id: hovered }, { hover: false });
      }
      hovered = null;
      map.getCanvas().style.cursor = '';
      onHover(null);
    });

    map.on('click', LAYER_IDS.fill, (event) => {
      const feature = event.features?.[0];
      if (feature) onSelect(String(feature.id));
    });
  }, [ready, collection, definition, onHover, onSelect]);

  // The scenario dock injects `delta_lst_c` into a fresh collection object after each
  // simulation; the source holds the original reference, so push the new data in.
  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (!map || !ready || !source || !collection) return;
    source.setData(collection as never);
  }, [collection, ready]);

  // Repaint when the layer changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getLayer(LAYER_IDS.fill)) return;
    map.setPaintProperty(
      LAYER_IDS.fill,
      'fill-color',
      fillColorExpression(definition) as never,
    );
  }, [definition, ready]);

  // Mirror hover coming from outside the map, e.g. a chat result row.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { hover: id === hoverId });
    }
  }, [hoverId, ready, collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { selected: id === selectedId });
    }
  }, [selectedId, ready, collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    const active = new Set(showPriority ? priorityIds : []);
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { priority: active.has(id) });
    }
  }, [priorityIds, showPriority, ready, collection]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !map.getSource(SOURCE_ID) || !collection) return;
    const active = new Set(pickedIds);
    for (const feature of collection.features) {
      const id = feature.properties.kel_id;
      map.setFeatureState({ source: SOURCE_ID, id }, { picked: active.has(id) });
    }
  }, [pickedIds, ready, collection]);

  // Pan so the selected kelurahan is not hidden behind the drawer.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !selectedId) return;
    const target = centroids.get(selectedId);
    if (!target) return;
    map.easeTo({
      center: target,
      offset: drawerOpen ? [-drawerWidth / 2, 0] : [0, 0],
      duration: PAN_DURATION_MS,
    });
  }, [selectedId, drawerOpen, drawerWidth, centroids, ready]);

  // Project priority centroids into screen space for the numbered HTML markers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const reproject = () => {
      if (!showPriority) {
        setMarkers([]);
        return;
      }
      const seen = new Set<string>();
      setMarkers(
        priorityIds.flatMap((id, index) => {
          if (seen.has(id)) return [];
          const centre = centroids.get(id);
          if (!centre) return [];
          seen.add(id);
          const point = map.project(centre);
          return [{ id, x: point.x, y: point.y, rank: index + 1 }];
        }),
      );
    };

    reproject();
    map.on('move', reproject);
    return () => {
      map.off('move', reproject);
    };
  }, [priorityIds, showPriority, centroids, ready]);

  return (
    <div className={styles.wrapper}>
      <div ref={containerRef} className={styles.canvas} aria-label="Peta kelurahan DKI Jakarta" />
      {markers.map((marker) => (
        <button
          key={marker.id}
          type="button"
          className={styles.marker}
          style={{ transform: `translate(${marker.x - 11}px, ${marker.y - 11}px)` }}
          onClick={() => onSelect(marker.id)}
          onMouseEnter={() => onHover(marker.id)}
          onMouseLeave={() => onHover(null)}
          aria-label={`Prioritas ${marker.rank}`}
        >
          {marker.rank}
        </button>
      ))}
    </div>
  );
}

export type { KelurahanProperties };
