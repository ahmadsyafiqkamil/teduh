'use client';

/**
 * Scenario sliders and the budget field.
 *
 * Simulasikan stays disabled until at least one slider moves. That is not just polish: a
 * zero scenario returns a delta of exactly 0 for every kelurahan, and a planner reading
 * "0,00 °C" has no way to tell a real null result from a button they pressed too early.
 *
 * The canopy slider is in percentage POINTS of cell area, not a percentage of anything, so
 * the help text spells that out. "pp" alone means nothing to the intended user.
 */

import { Check, Loader2, Play } from 'lucide-react';
import styles from './ScenarioDock.module.css';

export interface ScenarioState {
  tree: number;
  coolRoof: number;
  greenRoof: number;
  budget: number | null;
}

export const EMPTY_SCENARIO: ScenarioState = {
  tree: 0,
  coolRoof: 0,
  greenRoof: 0,
  budget: null,
};

type SliderKey = 'tree' | 'coolRoof' | 'greenRoof';

interface SliderDefinition {
  key: SliderKey;
  label: string;
  help: string;
  min: number;
  max: number;
  step: number;
  render: (value: number) => string;
}

export const SLIDERS: SliderDefinition[] = [
  {
    key: 'tree',
    label: 'Tambah kanopi pohon',
    help: 'Poin persen lahan terbuka',
    min: 0,
    max: 20,
    step: 1,
    render: (value) => `+${value} pp`,
  },
  {
    key: 'coolRoof',
    label: 'Cool roof',
    help: 'Porsi atap dicat pemantul panas',
    min: 0,
    max: 100,
    step: 5,
    render: (value) => `${value}%`,
  },
  {
    key: 'greenRoof',
    label: 'Green roof',
    help: 'Porsi atap beton datar',
    min: 0,
    max: 50,
    step: 5,
    render: (value) => `${value}%`,
  },
];

interface ScenarioDockProps {
  state: ScenarioState;
  onChange: (next: ScenarioState) => void;
  targetLabel: string;
  status: string;
  busy: boolean;
  onSimulate: () => void;
  multiSelect: boolean;
  pickedCount: number;
  onToggleMultiSelect: () => void;
  onClearPicked: () => void;
}

export function ScenarioDock({
  state,
  onChange,
  targetLabel,
  status,
  busy,
  onSimulate,
  multiSelect,
  pickedCount,
  onToggleMultiSelect,
  onClearPicked,
}: ScenarioDockProps) {
  const hasIntervention = state.tree > 0 || state.coolRoof > 0 || state.greenRoof > 0;

  return (
    <section className={styles.dock} aria-label="Simulasi skenario">
      <div className={styles.titleRow}>
        <span className={styles.title}>Simulasi skenario</span>
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
          Pilih banyak kelurahan
        </button>
        {pickedCount > 0 && (
          <button type="button" className={styles.clearPicked} onClick={onClearPicked}>
            Bersihkan ({pickedCount})
          </button>
        )}
        <span className={styles.multiHint}>
          {multiSelect
            ? 'Klik kelurahan di peta untuk menambah atau menghapus pilihan.'
            : 'Nyalakan untuk memilih beberapa kelurahan secara manual.'}
        </span>
      </div>

      <div className={styles.grid}>
        {SLIDERS.map((slider) => {
          const value = state[slider.key];
          return (
            <div key={slider.key} className={styles.field}>
              <div className={styles.fieldHead}>
                <label className={styles.fieldLabel} htmlFor={`slider-${slider.key}`}>
                  {slider.label}
                </label>
                <span
                  className={`${styles.value} ${value > 0 ? styles.valueActive : ''}`}
                >
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
              <div className={styles.help}>{slider.help}</div>
            </div>
          );
        })}

        <div className={styles.field}>
          <label className={styles.fieldLabel} htmlFor="budget">
            Anggaran (Rp)
          </label>
          <div className={styles.budgetWrap}>
            <span aria-hidden="true">Rp</span>
            <input
              id="budget"
              type="text"
              inputMode="numeric"
              aria-label="Anggaran dalam rupiah"
              value={state.budget === null ? '' : state.budget.toLocaleString('id-ID')}
              onChange={(event) => {
                // Digits only: the displayed value carries dot separators, and parsing them
                // back as a number would multiply the budget by a thousand.
                const digits = event.target.value.replace(/\D/g, '');
                onChange({ ...state, budget: digits ? Number(digits) : null });
              }}
            />
          </div>
        </div>

        <button
          type="button"
          className={styles.simulate}
          disabled={!hasIntervention || busy}
          onClick={onSimulate}
        >
          {busy ? (
            <>
              <Loader2 size={16} aria-hidden="true" /> Menghitung…
            </>
          ) : (
            <>
              <Play size={16} aria-hidden="true" /> Simulasikan
            </>
          )}
        </button>
      </div>
    </section>
  );
}
