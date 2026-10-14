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
import { LAYERS, LAYER_ORDER, layerCopy, type LayerId } from '@/lib/layers';
import { t, type Lang } from '@/lib/i18n';
import styles from './Header.module.css';

interface HeaderProps {
  layer: LayerId;
  onLayerChange: (id: LayerId) => void;
  lang: Lang;
  onLangChange: (lang: Lang) => void;
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
          <span className={styles.coverage}>{t(lang, 'header.coverage')}</span>
        </span>
      </div>

      <div className={styles.group} role="group" aria-label={t(lang, 'header.layerGroup')}>
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
            {layerCopy(LAYERS[id], lang).label}
          </button>
        ))}
      </div>

      <div className={styles.spacer} />

      <div className={styles.search}>
        <Search size={16} aria-hidden="true" />
        <input
          type="search"
          placeholder={t(lang, 'header.searchPlaceholder')}
          aria-label={t(lang, 'header.searchLabel')}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onSearchSubmit(query);
          }}
        />
      </div>

      <div className={styles.group} role="group" aria-label={t(lang, 'header.langGroup')}>
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
        {t(lang, 'header.about')}
      </Link>
    </header>
  );
}
