'use client';

/**
 * Client-side active language, persisted to localStorage so the toggle sticks across
 * pages (map, Cek Atap, Sumber Data) and reloads.
 *
 * CONCEPT §6.2 principle 5 defaults to Bahasa Indonesia; English is the judge-facing
 * toggle. The hook reads the stored choice on first render, which is why the initial value
 * is a lazy initialiser rather than a constant — otherwise the first paint would always
 * flash Indonesian before the effect kicks in.
 */

import { useCallback, useEffect, useState } from 'react';
import type { Lang } from './i18n';

const STORAGE_KEY = 'teduh.lang';

export function useStoredLang(): [Lang, (lang: Lang) => void] {
  // Start at the server default so the first client render matches the SSR HTML exactly.
  // The stored language is rehydrated in an effect AFTER hydration, avoiding the text
  // mismatch that a localStorage read inside the initialiser would cause.
  const [lang, setLang] = useState<Lang>('id');

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === 'en') setLang('en');
  }, []);

  useEffect(() => {
    window.document.documentElement.lang = lang;
    window.localStorage.setItem(STORAGE_KEY, lang);
  }, [lang]);

  const set = useCallback((next: Lang) => setLang(next), []);
  return [lang, set];
}