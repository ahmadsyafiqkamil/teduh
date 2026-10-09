'use client';

/**
 * Top bar: brand, layer picker, search, language toggle, sources link.
 *
 * The layer picker is a real segmented control with aria-pressed rather than a select,
 * because switching layers is the single most frequent action on this screen and the
 * colour swatches are what make the choropleth legible without reading the labels.
 */

import { BookOpen, Search, TreeDeciduous } from 'lucide-react';
import Link from 'next/link';
import { LAYERS, LAYER_ORDER, type LayerId } from '@/lib/layers';
import styles from './Header.module.css';

interface HeaderProps {
  layer: LayerId;
  onLayerChange: (id: LayerId) => void;
  lang: 'id' | 'en';
  onLangChange: (lang: 'id' | 'en') => void;
  query: string;
  onQueryChange: (query: string) => void;
  onSearchSubmit: (query: string) => void;
}

export function Header({
  layer,
  onLayerChange,
  lang,
  onLangChange,
  query,
  onQueryChange,
  onSearchSubmit,
}: HeaderProps) {
  return (
    <header className={styles.header} role="banner">
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true">
          <TreeDeciduous size={18} />
        </span>
        <span>
          <span className={styles.wordmark}>TEDUH</span>
          <br />
          <span className={styles.coverage}>DKI Jakarta · kelurahan</span>
        </span>
      </div>

      <div className={styles.group} role="group" aria-label="Lapisan peta">
        {LAYER_ORDER.map((id) => (
          <button
            key={id}
            type="button"
            className={styles.layerButton}
            aria-pressed={layer === id}
            onClick={() => onLayerChange(id)}
          >
            <span
              className={styles.swatch}
              style={{ background: LAYERS[id].swatch }}
              aria-hidden="true"
            />
            {LAYERS[id].label}
          </button>
        ))}
      </div>

      <div className={styles.spacer} />

      <div className={styles.search}>
        <Search size={16} aria-hidden="true" />
        <input
          type="search"
          placeholder="Cari kelurahan…"
          aria-label="Cari kelurahan"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onSearchSubmit(query);
          }}
        />
      </div>

      <div className={styles.group} role="group" aria-label="Bahasa">
        {(['id', 'en'] as const).map((code) => (
          <button
            key={code}
            type="button"
            className={styles.langButton}
            aria-pressed={lang === code}
            onClick={() => onLangChange(code)}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>

      <Link href="/sumber-data" className={styles.about}>
        <BookOpen size={16} stroke="var(--color-canopy)" aria-hidden="true" />
        Tentang &amp; Sumber Data
      </Link>
    </header>
  );
}
