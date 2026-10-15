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
import {
  EMPTY_SCENARIO,
  ScenarioDock,
  type ScenarioMode,
  type ScenarioState,
} from '@/components/ScenarioDock';
import { createSession, streamAgent, type AgentStep } from '@/lib/agent';
import { fetchKelurahan, postOptimize, postSimulate } from '@/lib/api';
import { formatIdr, formatNumber } from '@/lib/format';
import { t } from '@/lib/i18n';
import { useStoredLang } from '@/lib/useLang';
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
import type { KelurahanCollection, OptimizeResponse, ScenarioResult, SimulateResponse } from '@/lib/types';
import styles from './page.module.css';

const USER_ID = 'perencana';

// Mirrors api/schemas.py MAX_KELURAHAN_PER_REQUEST. The full DKI Jakarta dataset is 264
// kelurahan, so a whole-kota scenario (Jakarta Pusat has 44) must be allowed through. The
// guard only trips for a list larger than the dataset itself, which is never legitimate.
const MAX_KELURAHAN_PER_REQUEST = 264;

export default function Home() {
  const [collection, setCollection] = useState<KelurahanCollection | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [layer, setLayer] = useState<LayerId>('hvi');
  const [lang, setLang] = useStoredLang();
  const [query, setQuery] = useState('');

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [priorityIds, setPriorityIds] = useState<string[]>([]);
  const [showPriority, setShowPriority] = useState(true);

  // Manual multi-select: the planner toggles "pilih banyak" and clicks kelurahan to build
  // their own simulation target, independent of the agent's priority set.
  const [multiSelect, setMultiSelect] = useState(false);
  const [pickedIds, setPickedIds] = useState<string[]>([]);
  const multiSelectRef = useRef(false);
  useEffect(() => {
    multiSelectRef.current = multiSelect;
  }, [multiSelect]);

  const [scenario, setScenario] = useState<ScenarioState>(EMPTY_SCENARIO);
  const [scenarioStatus, setScenarioStatus] = useState(
    t('id', 'scenario.status.empty'),
  );
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [simulation, setSimulation] = useState<SimulateResponse | null>(null);
  const [simulationDeltas, setSimulationDeltas] = useState<Record<string, number>>({});

  // Two-mode dock: "Simulasikan" (sliders) vs "Optimalkan" (budget). Each keeps its own
  // result so switching modes never shows a stale card from the other question.
  const [scenarioMode, setScenarioMode] = useState<ScenarioMode>('simulate');
  const [optimization, setOptimization] = useState<OptimizeResponse | null>(null);
  const [optimizeBusy, setOptimizeBusy] = useState(false);

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

  // Stable across renders so the map registers its click handler exactly once. The mode is
  // read through a ref, so toggling "pilih banyak" never leaves a stale closure behind.
  const handleMapSelect = useCallback((kelId: string) => {
    if (multiSelectRef.current) {
      setPickedIds((previous) =>
        previous.includes(kelId)
          ? previous.filter((id) => id !== kelId)
          : [...previous, kelId],
      );
    } else {
      setSelectedId(kelId);
    }
  }, []);

  const toggleMultiSelect = useCallback(() => {
    if (!multiSelectRef.current) {
      // Entering multi-select: seed with the current single selection so the map gives
      // immediate feedback, and close the drawer so clicks stop being interpreted as select.
      setPickedIds(selectedId ? [selectedId] : []);
      setSelectedId(null);
      setMultiSelect(true);
    } else {
      setPickedIds([]);
      setMultiSelect(false);
    }
  }, [selectedId]);

  const clearPicked = useCallback(() => setPickedIds([]), []);

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
          lang,
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

            // The agent's simulate_intervention also produces per-kelurahan ΔLST. Paint it
            // onto the `dlst` layer exactly like the slider path does, so a scenario asked
            // in chat colours the map instead of leaving it blank.
            const simulated = event.steps
              .filter(
                (step) => step.status === 'done' && step.tool === 'simulate_intervention',
              )
              .flatMap((step) => (step.response?.results as ScenarioResult[]) ?? []);
            if (simulated.length) {
              const deltas: Record<string, number> = {};
              for (const row of simulated) deltas[row.kel_id] = row.delta_lst_c;
              setSimulationDeltas(deltas);
              setLayer('dlst');
            }
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : t(lang, 'agent.unreachable');
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
    [chatBusy, lang],
  );

  // One source of truth for "what is currently targeted", shared by simulate and optimize
  // so the two modes can never act on different kelurahan. Order matches the target label.
  const currentTargets = useMemo<string[]>(() => {
    if (pickedIds.length) return pickedIds;
    if (priorityIds.length) return priorityIds;
    if (selectedId) return [selectedId];
    return [];
  }, [pickedIds, priorityIds, selectedId]);

  const runSimulation = useCallback(async () => {
    let targets = currentTargets;
    if (!targets.length) {
      setScenarioStatus(t(lang, 'scenario.status.pick'));
      return;
    }

    // Safety net only: the API rejects a list larger than the dataset. It cannot trigger
    // from a legitimate selection (there are 264 kelurahan total), so no user-facing note.
    if (targets.length > MAX_KELURAHAN_PER_REQUEST) {
      targets = targets.slice(0, MAX_KELURAHAN_PER_REQUEST);
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
    setScenarioStatus(t(lang, 'scenario.calculating'));
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
          ? t(lang, 'scenario.status.treeBlocked')
          : t(lang, 'scenario.status.result', {
              mean: formatNumber(mean, 2, lang),
              n: result.results.length,
            }),
      );
    } catch (error) {
      setScenarioStatus(error instanceof Error ? error.message : t(lang, 'scenario.status.failed'));
    } finally {
      setScenarioBusy(false);
    }
  }, [currentTargets, scenario, lang]);

  const changeScenarioMode = useCallback(
    (next: ScenarioMode) => {
      setScenarioMode(next);
      setScenarioStatus(
        next === 'optimize'
          ? t(lang, 'scenario.optimizeStatus.empty')
          : t(lang, 'scenario.status.empty'),
      );
    },
    [lang],
  );

  const runOptimize = useCallback(async () => {
    if (scenario.budget === null || scenario.budget <= 0) {
      setScenarioStatus(t(lang, 'scenario.optimizeStatus.needBudget'));
      return;
    }

    // Same target as simulate (currentTargets); fall back to the whole city only when
    // nothing at all is targeted.
    const targets = currentTargets;
    const kel_ids = targets.length ? targets : null;

    setOptimizeBusy(true);
    setScenarioStatus(t(lang, 'scenario.calculating'));
    try {
      const result = await postOptimize({
        kel_ids,
        budget_idr: scenario.budget,
        equity_share: scenario.equityShare,
      });
      setOptimization(result);

      // Drive the map exactly like the agent's optimize path: highlight every kelurahan the
      // portfolio touches, so the answer and the map never show different areas.
      const highlight = result.map_highlight ?? result.packages.map((p) => p.kel_id);
      if (highlight.length) {
        setPriorityIds([...new Set(highlight)]);
        setShowPriority(true);
      }

      const base = t(lang, 'scenario.optimizeStatus.result', {
        n: result.packages.length,
        cost: formatIdr(result.total_cost_idr, lang),
      });
      // The engine caps candidate generation at the 40 highest-HVI areas; tell the planner
      // when their explicit list was trimmed so it never reads as a silent drop.
      const nAreas = result.n_areas;
      let next = base;
      if (kel_ids !== null && nAreas !== undefined && kel_ids.length > nAreas) {
        next = `${base} ${t(lang, 'scenario.optimizeStatus.trimmed', { n: nAreas })}`;
      }
      setScenarioStatus(next);
    } catch (error) {
      setScenarioStatus(
        error instanceof Error ? error.message : t(lang, 'scenario.status.failed'),
      );
    } finally {
      setOptimizeBusy(false);
    }
  }, [scenario.budget, scenario.equityShare, currentTargets, lang]);

  const clearResult = useCallback(() => {
    if (scenarioMode === 'simulate') {
      setSimulation(null);
      setSimulationDeltas({});
      if (layer === 'dlst') setLayer('hvi');
      setScenarioStatus(t(lang, 'scenario.status.empty'));
    } else {
      setOptimization(null);
      setPriorityIds([]);
      setShowPriority(false);
      setScenarioStatus(t(lang, 'scenario.optimizeStatus.empty'));
    }
  }, [scenarioMode, layer, lang]);

  const hasResult = scenarioMode === 'simulate' ? simulation !== null : optimization !== null;

  const scopeLabel = selectedId
    ? (collection?.features.find((f) => f.properties.kel_id === selectedId)?.properties
        .kota_name ?? 'DKI JAKARTA').toUpperCase()
    : 'DKI JAKARTA';

  const targetLabel = pickedIds.length
    ? t(lang, 'target.picked', { n: pickedIds.length })
    : priorityIds.length
      ? t(lang, 'target.priority', { n: priorityIds.length })
      : selectedId
        ? t(lang, 'target.single')
        : t(lang, 'target.none');

  return (
    <div className={styles.shell}>
      <Header
        layer={layer}
        onLayerChange={setLayer}
        lang={lang}
        onLangChange={setLang}
        query={query}
        onQueryChange={setQuery}
        onSearchSubmit={(value) =>
          send(lang === 'en' ? `Show the heat profile for ${value}.` : `Tampilkan profil panas untuk ${value}.`)
        }
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
                pickedIds={pickedIds}
                showPriority={showPriority}
                drawerOpen={selectedId !== null}
                drawerWidth={drawerWidth ?? DRAWER_WIDTH_DEFAULT}
                onHover={setHoverId}
                onSelect={handleMapSelect}
              />
            )}

            <MapOverlays
              layer={layer}
              lang={lang}
              scopeLabel={scopeLabel}
              attribution={collection?.attribution ?? ''}
              priorityCount={showPriority ? priorityIds.length : 0}
              drawerOpen={selectedId !== null}
              onZoomIn={() => undefined}
              onZoomOut={() => undefined}
            />

            <KelurahanDrawer
              kelId={selectedId}
              lang={lang}
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
            label={t(lang, 'resize.simulation')}
          />

          <div
            ref={bottomRef}
            className={styles.bottom}
            style={{ '--bottom-h': bottomHeight ? `${bottomHeight}px` : undefined } as React.CSSProperties}
          >
            <ScenarioDock
              state={scenario}
              onChange={setScenario}
              mode={scenarioMode}
              onModeChange={changeScenarioMode}
              targetLabel={targetLabel}
              status={scenarioStatus}
              busy={scenarioBusy || optimizeBusy}
              lang={lang}
              onSimulate={runSimulation}
              onOptimize={runOptimize}
              multiSelect={multiSelect}
              pickedCount={pickedIds.length}
              onToggleMultiSelect={toggleMultiSelect}
              onClearPicked={clearPicked}
              hasResult={hasResult}
              onClearResult={clearResult}
            />

            {scenarioMode === 'simulate' && simulation && (
              <div className={styles.simulationCard}>
                <ResultTable
                  tool="simulate_intervention"
                  response={simulation as unknown as Record<string, unknown>}
                  lang={lang}
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

            {scenarioMode === 'optimize' && optimization && (
              <div className={styles.simulationCard}>
                <ResultTable
                  tool="optimize_portfolio"
                  response={optimization as unknown as Record<string, unknown>}
                  lang={lang}
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
          label={t(lang, 'resize.agent')}
        />

        <div ref={agentRef} className={styles.agentWrap}>
          <AgentPanel
            messages={messages}
            draft={draft}
            busy={chatBusy}
            lang={lang}
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
