'use client';

/**
 * Scenario sliders and the budget/optimize form.
 *
 * Two modes answer two different questions, so they share one dock but never show the same
 * fields at once:
 *   - "Simulasikan" (sliders)  -> "I know WHAT to do, what is the impact?"
 *   - "Optimalkan"  (budget)   -> "I have a budget, what should I BUY?"
 *
 * The budget field therefore lives only in optimize mode. Before this split it sat unused in
 * the simulate path -- `runSimulation` never read `scenario.budget` -- which made a planner
 * type a budget and watch it quietly do nothing.
 *
 * The canopy slider is in percentage POINTS of cell area, not a percentage of anything, so
 * the help text spells that out. "pp" alone means nothing to the intended user.
 */

import { Check, Loader2, Play } from 'lucide-react';
import { t, type Lang } from '@/lib/i18n';
import styles from './ScenarioDock.module.css';

export interface ScenarioState {
  tree: number;
  coolRoof: number;
  greenRoof: number;
  budget: number | null;
  /** Optional equity-share override; null means "use the configured default (0.6)". */
  equityShare: number | null;
}

export const EMPTY_SCENARIO: ScenarioState = {
  tree: 0,
  coolRoof: 0,
  greenRoof: 0,
  budget: null,
  equityShare: null,
};

export type ScenarioMode = 'simulate' | 'optimize';

type SliderKey = 'tree' | 'coolRoof' | 'greenRoof';

interface SliderDefinition {
  key: SliderKey;
  labelKey: string;
  helpKey: string;
  min: number;
  max: number;
  step: number;
  render: (value: number) => string;
}

export const SLIDERS: SliderDefinition[] = [
  {
    key: 'tree',
    labelKey: 'scenario.slider.tree.label',
    helpKey: 'scenario.slider.tree.help',
    min: 0,
    max: 20,
    step: 1,
    render: (value) => `+${value} pp`,
  },
  {
    key: 'coolRoof',
    labelKey: 'scenario.slider.coolRoof.label',
    helpKey: 'scenario.slider.coolRoof.help',
    min: 0,
    max: 100,
    step: 5,
    render: (value) => `${value}%`,
  },
  {
    key: 'greenRoof',
    labelKey: 'scenario.slider.greenRoof.label',
    helpKey: 'scenario.slider.greenRoof.help',
    min: 0,
    max: 50,
    step: 5,
    render: (value) => `${value}%`,
  },
];

interface ScenarioDockProps {
  state: ScenarioState;
  onChange: (next: ScenarioState) => void;
  mode: ScenarioMode;
  onModeChange: (mode: ScenarioMode) => void;
  targetLabel: string;
  status: string;
  busy: boolean;
  lang?: Lang;
  onSimulate: () => void;
  onOptimize: () => void;
  multiSelect: boolean;
  pickedCount: number;
  onToggleMultiSelect: () => void;
  onClearPicked: () => void;
  hasResult: boolean;
  onClearResult: () => void;
}

export function ScenarioDock({
  state,
  onChange,
  mode,
  onModeChange,
  targetLabel,
  status,
  busy,
  lang = 'id',
  onSimulate,
  onOptimize,
  multiSelect,
  pickedCount,
  onToggleMultiSelect,
  onClearPicked,
  hasResult,
  onClearResult,
}: ScenarioDockProps) {
  const hasIntervention = state.tree > 0 || state.coolRoof > 0 || state.greenRoof > 0;
  const hasBudget = state.budget !== null && state.budget > 0;
  const actionDisabled = mode === 'optimize' ? !hasBudget : !hasIntervention;

  const actionLabel = mode === 'optimize' ? t(lang, 'scenario.modeOptimize') : t(lang, 'scenario.simulate');

  return (
    <section className={styles.dock} aria-label={t(lang, 'scenario.title')}>
      <div className={styles.titleRow}>
        <div className={styles.modeToggle} role="tablist" aria-label={t(lang, 'scenario.title')}>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'simulate'}
            className={`${styles.modeOption} ${mode === 'simulate' ? styles.modeActive : ''}`}
            onClick={() => onModeChange('simulate')}
          >
            {t(lang, 'scenario.modeSimulate')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'optimize'}
            className={`${styles.modeOption} ${mode === 'optimize' ? styles.modeActive : ''}`}
            onClick={() => onModeChange('optimize')}
          >
            {t(lang, 'scenario.modeOptimize')}
          </button>
        </div>
        <span className={styles.target}>{targetLabel}</span>
        <span className={styles.status}>{status}</span>
      </div>

      <div className={styles.toolbar}>
        <button
          type="button"
          className={`${styles.multiToggle} ${multiSelect ? styles.multiToggleOn : ''}`}
          aria-pressed={multiSelect}
          onClick={onToggleMultiSelect}
        >
          {multiSelect ? <Check size={14} aria-hidden="true" /> : null}
          {t(lang, 'scenario.multiSelect')}
        </button>
        {pickedCount > 0 && (
          <button type="button" className={styles.clearPicked} onClick={onClearPicked}>
            {t(lang, 'scenario.clearPicked', { n: pickedCount })}
          </button>
        )}
        {hasResult && (
          <button type="button" className={styles.clearPicked} onClick={onClearResult}>
            {t(lang, 'scenario.clearResult')}
          </button>
        )}
        <span className={styles.multiHint}>
          {multiSelect
            ? t(lang, 'scenario.multiHint.on')
            : t(lang, 'scenario.multiHint.off')}
        </span>
      </div>

      <div className={`${styles.grid} ${mode === 'optimize' ? styles.gridOptimize : ''}`}>
        {mode === 'simulate' ? (
          SLIDERS.map((slider) => {
            const value = state[slider.key];
            return (
              <div key={slider.key} className={styles.field}>
                <div className={styles.fieldHead}>
                  <label className={styles.fieldLabel} htmlFor={`slider-${slider.key}`}>
                    {t(lang, slider.labelKey)}
                  </label>
                  <span className={`${styles.value} ${value > 0 ? styles.valueActive : ''}`}>
                    {slider.render(value)}
                  </span>
                </div>
                <input
                  id={`slider-${slider.key}`}
                  className={styles.slider}
                  type="range"
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  value={value}
                  onChange={(event) =>
                    onChange({ ...state, [slider.key]: Number(event.target.value) })
                  }
                />
                <div className={styles.help}>{t(lang, slider.helpKey)}</div>
              </div>
            );
          })
        ) : (
          <>
            <div className={styles.field}>
              <div className={styles.fieldHead}>
                <label className={styles.fieldLabel} htmlFor="budget">
                  {t(lang, 'scenario.budget')}
                </label>
              </div>
              <div className={styles.budgetWrap}>
                <span aria-hidden="true">Rp</span>
                <input
                  id="budget"
                  type="text"
                  inputMode="numeric"
                  aria-label={t(lang, 'scenario.budgetLabel')}
                  value={state.budget === null ? '' : state.budget.toLocaleString(lang === 'en' ? 'en-US' : 'id-ID')}
                  onChange={(event) => {
                    const digits = event.target.value.replace(/\D/g, '');
                    onChange({ ...state, budget: digits ? Number(digits) : null });
                  }}
                />
              </div>
            </div>

            <div className={styles.field}>
              <div className={styles.fieldHead}>
                <label className={styles.fieldLabel} htmlFor="equity">
                  {t(lang, 'scenario.equityLabel')} *
                </label>
              </div>
              <div className={styles.budgetWrap}>
                <input
                  id="equity"
                  type="text"
                  inputMode="decimal"
                  aria-label={t(lang, 'scenario.equityLabel')}
                  placeholder="0,6"
                  value={state.equityShare === null ? '' : String(state.equityShare)}
                  onChange={(event) => {
                    const raw = event.target.value.trim().replace(',', '.');
                    if (raw === '') {
                      onChange({ ...state, equityShare: null });
                      return;
                    }
                    const value = Number.parseFloat(raw);
                    if (!Number.isNaN(value) && value >= 0 && value <= 1) {
                      onChange({ ...state, equityShare: value });
                    }
                  }}
                />
              </div>
            </div>

            {/* Spacer keeps the action button right-aligned across both modes. */}
            <div aria-hidden="true" />
          </>
        )}

        <button
          type="button"
          className={styles.simulate}
          disabled={actionDisabled || busy}
          onClick={mode === 'optimize' ? onOptimize : onSimulate}
        >
          {busy ? (
            <>
              <Loader2 size={16} aria-hidden="true" /> {t(lang, 'scenario.calculating')}
            </>
          ) : (
            <>
              <Play size={16} aria-hidden="true" /> {actionLabel}
            </>
          )}
        </button>
      </div>

      {mode === 'optimize' && (
        <div className={styles.optimizeNote}>*{t(lang, 'scenario.equityHelp')}</div>
      )}
    </section>
  );
}