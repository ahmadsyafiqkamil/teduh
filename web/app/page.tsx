'use client';

/**
 * The main screen. All state lives here and flows down as props.
 *
 * No state library: design/README.md §State Management lists eight flat values, and keeping
 * them in one place is what makes the cross-panel flow -- hover a chat row, highlight the
 * map, click to open the drawer, pan the map clear of it -- readable in a single file. A
 * store would scatter that sequence across four modules for no gain at this size.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AgentPanel, type ChatMessage } from '@/components/AgentPanel';
import { Header } from '@/components/Header';
import { KelurahanDrawer } from '@/components/KelurahanDrawer';
import { MapOverlays } from '@/components/MapOverlays';
import { MapView } from '@/components/MapView';
import { ResizeHandle } from '@/components/ResizeHandle';
import { ResultTable } from '@/components/ResultTable';
import { EMPTY_SCENARIO, ScenarioDock, type ScenarioState } from '@/components/ScenarioDock';
import { createSession, streamAgent, type AgentStep } from '@/lib/agent';
import { fetchKelurahan, postSimulate } from '@/lib/api';
import { formatNumber } from '@/lib/format';
// LayerId is defined in lib/layers, not lib/types: it is a presentation concern, not an
// API shape.
import { type LayerId } from '@/lib/layers';
import {
  AGENT_MAX_PX,
  AGENT_MIN_PX,
  BOTTOM_MAX_PX,
  BOTTOM_MIN_PX,
  DRAWER_WIDTH_DEFAULT,
  SIZE_KEYS,
  clearSize,
  readSize,
  writeSize,
} from '@/lib/resize';
import type { KelurahanCollection, SimulateResponse } from '@/lib/types';
import styles from './page.module.css';

const USER_ID = 'perencana';

export default function Home() {
  const [collection, setCollection] = useState<KelurahanCollection | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [layer, setLayer] = useState<LayerId>('hvi');
  const [lang, setLang] = useState<'id' | 'en'>('id');
  const [query, setQuery] = useState('');

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [priorityIds, setPriorityIds] = useState<string[]>([]);
  const [showPriority, setShowPriority] = useState(true);

  const [scenario, setScenario] = useState<ScenarioState>(EMPTY_SCENARIO);
  const [scenarioStatus, setScenarioStatus] = useState(
    'Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan.',
  );
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [simulation, setSimulation] = useState<SimulateResponse | null>(null);
  const [simulationDeltas, setSimulationDeltas] = useState<Record<string, number>>({});

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const sessionRef = useRef<string | null>(null);

  // Panel sizes are nullable: null means "use the CSS default". They are seeded from
  // localStorage inside an effect so the first render matches the server (no SSR mismatch),
  // and every change is persisted so a reload restores the last layout.
  const [agentWidth, setAgentWidth] = useState<number | null>(null);
  const [bottomHeight, setBottomHeight] = useState<number | null>(null);
  const [drawerWidth, setDrawerWidth] = useState<number | null>(null);
  const agentRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setAgentWidth(readSize(SIZE_KEYS.agent));
    setBottomHeight(readSize(SIZE_KEYS.bottom));
    setDrawerWidth(readSize(SIZE_KEYS.drawer));
  }, []);

  const persist = (key: string, next: number | null) => {
    if (next === null) clearSize(key);
    else writeSize(key, next);
  };

  const getAgentSize = () =>
    agentWidth ?? agentRef.current?.getBoundingClientRect().width ?? AGENT_MIN_PX;
  const getBottomSize = () =>
    bottomHeight ?? bottomRef.current?.getBoundingClientRect().height ?? BOTTOM_MIN_PX;

  useEffect(() => {
    fetchKelurahan().then(setCollection).catch((error: Error) => setLoadError(error.message));
  }, []);

  // The collection the map paints. When a simulation has run, its per-kelurahan ΔLST is
  // injected here so the `dlst` layer has something to read; untouched kelurahan stay null.
  const displayCollection = useMemo<KelurahanCollection | null>(() => {
    if (!collection) return null;
    if (Object.keys(simulationDeltas).length === 0) return collection;
    return {
      ...collection,
      features: collection.features.map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          delta_lst_c: simulationDeltas[feature.properties.kel_id] ?? null,
        },
      })),
    };
  }, [collection, simulationDeltas]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || chatBusy) return;

      setDraft('');
      setChatBusy(true);
      const userId = `u-${Date.now()}`;
      setMessages((previous) => [
        ...previous,
        { id: userId, role: 'user', text: trimmed, steps: [] },
        { id: `a-${Date.now()}`, role: 'agent', text: '', steps: [] },
      ]);

      const started = Date.now();
      try {
        if (!sessionRef.current) sessionRef.current = await createSession(USER_ID);

        for await (const event of streamAgent({
          userId: USER_ID,
          sessionId: sessionRef.current,
          message: trimmed,
        })) {
          setMessages((previous) => {
            const next = [...previous];
            const last = next[next.length - 1];
            if (!last || last.role !== 'agent') return previous;

            if (event.kind === 'text') next[next.length - 1] = { ...last, text: event.text };
            if (event.kind === 'steps') {
              next[next.length - 1] = {
                ...last,
                steps: event.steps,
                elapsedMs: Date.now() - started,
              };
            }
            if (event.kind === 'error') {
              next[next.length - 1] = { ...last, error: event.message };
            }
            return next;
          });

          // Any tool that returned map_highlight drives the map, so the agent's answer and
          // the map never describe different kelurahan.
          if (event.kind === 'steps') {
            const highlight = event.steps
              .flatMap((step: AgentStep) => (step.response?.map_highlight as string[]) ?? [])
              .filter(Boolean);
            if (highlight.length) {
              setPriorityIds([...new Set(highlight)]);
              setShowPriority(true);
            }
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Agen tidak bisa dihubungi.';
        setMessages((previous) => {
          const next = [...previous];
          const last = next[next.length - 1];
          if (last && last.role === 'agent') next[next.length - 1] = { ...last, error: message };
          return next;
        });
      } finally {
        setChatBusy(false);
      }
    },
    [chatBusy],
  );

  const runSimulation = useCallback(async () => {
    const targets = priorityIds.length ? priorityIds : selectedId ? [selectedId] : [];
    if (!targets.length) {
      setScenarioStatus('Pilih kelurahan di peta atau minta agen menyusun prioritas dulu.');
      return;
    }

    const interventions: { type: string; params: Record<string, number> }[] = [];
    if (scenario.tree > 0) {
      interventions.push({
        type: 'tree_planting',
        params: { canopy_increase_pp: scenario.tree },
      });
    }
    if (scenario.coolRoof > 0) {
      interventions.push({
        type: 'cool_roof',
        params: { adoption_rate: scenario.coolRoof / 100 },
      });
    }
    if (scenario.greenRoof > 0) {
      interventions.push({
        type: 'green_roof',
        params: { adoption_rate: scenario.greenRoof / 100 },
      });
    }

    setScenarioBusy(true);
    setScenarioStatus('Menghitung…');
    try {
      const result = await postSimulate({ kel_ids: targets, interventions });

      const deltas: Record<string, number> = {};
      for (const row of result.results) deltas[row.kel_id] = row.delta_lst_c;
      setSimulationDeltas(deltas);
      setSimulation(result);
      setLayer('dlst');

      const mean =
        result.results.reduce((total, row) => total + row.delta_lst_c, 0) / result.results.length;
      const treeRequested = interventions.some((item) => item.type === 'tree_planting');
      const treeArea = result.results.reduce(
        (total, row) => total + (row.area_by_type?.tree_planting ?? 0),
        0,
      );
      setScenarioStatus(
        treeRequested && treeArea <= 0
          ? `Pohon tidak bisa ditanam — lahan terbangun penuh. Coba cool roof atau green roof.`
          : `Perkiraan rata-rata ${formatNumber(mean, 2)} °C pada ${result.results.length} kelurahan · indikatif, suhu permukaan.`,
      );
    } catch (error) {
      setScenarioStatus(error instanceof Error ? error.message : 'Simulasi gagal.');
    } finally {
      setScenarioBusy(false);
    }
  }, [priorityIds, selectedId, scenario]);

  const scopeLabel = selectedId
    ? (collection?.features.find((f) => f.properties.kel_id === selectedId)?.properties
        .kota_name ?? 'DKI JAKARTA').toUpperCase()
    : 'DKI JAKARTA';

  return (
    <div className={styles.shell}>
      <Header
        layer={layer}
        onLayerChange={setLayer}
        lang={lang}
        onLangChange={setLang}
        query={query}
        onQueryChange={setQuery}
        onSearchSubmit={(value) => send(`Tampilkan profil panas untuk ${value}.`)}
      />

      <div
        className={styles.body}
        style={{ '--agent-w': agentWidth ? `${agentWidth}px` : undefined } as React.CSSProperties}
      >
        <div className={styles.left}>
          <div className={styles.mapArea}>
            {loadError ? (
              <div style={{ padding: 'var(--panel-padding)' }}>{loadError}</div>
            ) : (
              <MapView
                collection={displayCollection}
                layer={layer}
                selectedId={selectedId}
                hoverId={hoverId}
                priorityIds={priorityIds}
                showPriority={showPriority}
                drawerOpen={selectedId !== null}
                drawerWidth={drawerWidth ?? DRAWER_WIDTH_DEFAULT}
                onHover={setHoverId}
                onSelect={setSelectedId}
              />
            )}

            <MapOverlays
              layer={layer}
              scopeLabel={scopeLabel}
              attribution={collection?.attribution ?? ''}
              priorityCount={showPriority ? priorityIds.length : 0}
              drawerOpen={selectedId !== null}
              onZoomIn={() => undefined}
              onZoomOut={() => undefined}
            />

            <KelurahanDrawer
              kelId={selectedId}
              onClose={() => setSelectedId(null)}
              onAskAgent={send}
              width={drawerWidth}
              onResize={(next) => {
                setDrawerWidth(next);
                persist(SIZE_KEYS.drawer, next);
              }}
            />
          </div>

          <ResizeHandle
            axis="horizontal"
            getSize={getBottomSize}
            min={BOTTOM_MIN_PX}
            max={BOTTOM_MAX_PX}
            onResize={(next) => {
              setBottomHeight(next);
              persist(SIZE_KEYS.bottom, next);
            }}
            label="Ubah tinggi panel simulasi"
          />

          <div
            ref={bottomRef}
            className={styles.bottom}
            style={{ '--bottom-h': bottomHeight ? `${bottomHeight}px` : undefined } as React.CSSProperties}
          >
            <ScenarioDock
              state={scenario}
              onChange={setScenario}
              targetLabel={
                priorityIds.length
                  ? `Target: ${priorityIds.length} kelurahan prioritas`
                  : selectedId
                    ? 'Target: 1 kelurahan terpilih'
                    : 'Target: belum dipilih'
              }
              status={scenarioStatus}
              busy={scenarioBusy}
              onSimulate={runSimulation}
            />

            {simulation && (
              <div className={styles.simulationCard}>
                <ResultTable
                  tool="simulate_intervention"
                  response={simulation as unknown as Record<string, unknown>}
                  onHighlight={(ids) => {
                    if (ids.length === 1) setHoverId(ids[0]);
                    else if (ids.length === 0) setHoverId(null);
                    else {
                      setPriorityIds([...new Set(ids)]);
                      setShowPriority(true);
                    }
                  }}
                  onSelect={setSelectedId}
                />
              </div>
            )}
          </div>
        </div>

        <ResizeHandle
          axis="vertical"
          getSize={getAgentSize}
          min={AGENT_MIN_PX}
          max={AGENT_MAX_PX}
          onResize={(next) => {
            setAgentWidth(next);
            persist(SIZE_KEYS.agent, next);
          }}
          label="Ubah lebar panel agen"
        />

        <div ref={agentRef} className={styles.agentWrap}>
          <AgentPanel
            messages={messages}
            draft={draft}
            busy={chatBusy}
            onDraftChange={setDraft}
            onSend={() => send(draft)}
            onNewThread={() => {
              setMessages([]);
              sessionRef.current = null;
              setPriorityIds([]);
            }}
            onHighlight={(ids) => {
              if (ids.length === 1) setHoverId(ids[0]);
              else if (ids.length === 0) setHoverId(null);
              else {
                setPriorityIds([...new Set(ids)]);
                setShowPriority(true);
              }
            }}
            onSelect={setSelectedId}
          />
        </div>
      </div>
    </div>
  );
}
