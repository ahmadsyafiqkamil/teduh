'use client';

/**
 * The main screen. All state lives here and flows down as props.
 *
 * No state library: design/README.md §State Management lists eight flat values, and keeping
 * them in one place is what makes the cross-panel flow -- hover a chat row, highlight the
 * map, click to open the drawer, pan the map clear of it -- readable in a single file. A
 * store would scatter that sequence across four modules for no gain at this size.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AgentPanel, type ChatMessage } from '@/components/AgentPanel';
import { Header } from '@/components/Header';
import { KelurahanDrawer } from '@/components/KelurahanDrawer';
import { MapOverlays } from '@/components/MapOverlays';
import { MapView } from '@/components/MapView';
import { EMPTY_SCENARIO, ScenarioDock, type ScenarioState } from '@/components/ScenarioDock';
import { createSession, streamAgent, type AgentStep } from '@/lib/agent';
import { fetchKelurahan, postSimulate } from '@/lib/api';
import { formatNumber } from '@/lib/format';
// LayerId is defined in lib/layers, not lib/types: it is a presentation concern, not an
// API shape.
import { type LayerId } from '@/lib/layers';
import type { KelurahanCollection } from '@/lib/types';
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

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    fetchKelurahan().then(setCollection).catch((error: Error) => setLoadError(error.message));
  }, []);

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
              setPriorityIds(highlight);
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
      const mean =
        result.results.reduce((total, row) => total + row.delta_lst_c, 0) / result.results.length;
      setScenarioStatus(
        `Perkiraan rata-rata ${formatNumber(mean, 2)} °C pada ${result.results.length} kelurahan · indikatif, suhu permukaan.`,
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

      <div className={styles.body}>
        <div className={styles.left}>
          <div className={styles.mapArea}>
            {loadError ? (
              <div style={{ padding: 'var(--panel-padding)' }}>{loadError}</div>
            ) : (
              <MapView
                collection={collection}
                layer={layer}
                selectedId={selectedId}
                hoverId={hoverId}
                priorityIds={priorityIds}
                showPriority={showPriority}
                drawerOpen={selectedId !== null}
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
            />
          </div>

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
        </div>

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
              setPriorityIds(ids);
              setShowPriority(true);
            }
          }}
          onSelect={setSelectedId}
        />
      </div>
    </div>
  );
}
