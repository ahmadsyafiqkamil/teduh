'use client';

/**
 * Minimal ID/EN segmented toggle for the standalone pages (Cek Atap, Sumber Data) that do
 * not carry the full Header. It reads and writes the same stored language as the main map
 * screen, so flipping it in one place flips everywhere.
 */

import type { Lang } from '@/lib/i18n';
import { useStoredLang } from '@/lib/useLang';

const GROUP_STYLE: React.CSSProperties = {
  display: 'inline-flex',
  padding: 3,
  border: '1px solid #E3DED4',
  borderRadius: 10,
  gap: 2,
};

function buttonStyle(active: boolean): React.CSSProperties {
  return {
    height: 28,
    padding: '0 12px',
    border: 0,
    borderRadius: 7,
    background: active ? '#1F5C4A' : 'transparent',
    color: active ? '#FFFFFF' : '#5E6662',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  };
}

export function LangToggle() {
  const [lang, setLang] = useStoredLang();
  return (
    <div role="group" aria-label="Bahasa / Language" style={GROUP_STYLE}>
      {(['id', 'en'] as const).map((code: Lang) => (
        <button
          key={code}
          type="button"
          aria-pressed={lang === code}
          style={buttonStyle(lang === code)}
          onClick={() => setLang(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}