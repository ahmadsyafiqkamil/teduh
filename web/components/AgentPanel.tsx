'use client';

/**
 * Chat thread, visible tool steps, and the composer.
 *
 * The step block is the point of this panel: it shows the agent reaching for data rather
 * than producing an answer from nowhere, which is what makes the provenance claim legible
 * to a sceptical user. Result cards render from step.response -- verified tool output --
 * never from the prose.
 */

import { Camera, Check, Loader2, Pencil, Send } from 'lucide-react';
import { useEffect, useRef } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentStep } from '@/lib/agent';
import { t, type Lang } from '@/lib/i18n';
import { ResultTable } from './ResultTable';
import styles from './AgentPanel.module.css';

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  text: string;
  steps: AgentStep[];
  error?: string;
  elapsedMs?: number;
}

interface AgentPanelProps {
  messages: ChatMessage[];
  draft: string;
  busy: boolean;
  lang?: Lang;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onNewThread: () => void;
  onHighlight: (kelIds: string[]) => void;
  onSelect: (kelId: string) => void;
}

function StepBlock({
  steps,
  elapsedMs,
  lang,
}: {
  steps: AgentStep[];
  elapsedMs?: number;
  lang: Lang;
}) {
  const done = steps.filter((step) => step.status === 'done').length;
  const seconds = elapsedMs
    ? (elapsedMs / 1000).toLocaleString(lang === 'en' ? 'en-US' : 'id-ID', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })
    : null;

  return (
    <div className={styles.steps}>
      <div className={styles.stepsHead}>
        {t(lang, 'agent.steps.done', { done, total: steps.length })}
        {seconds ? ` · ${t(lang, 'agent.steps.seconds', { seconds })}` : ''}
      </div>
      {steps.map((step, index) => (
        <div key={`${step.tool}-${index}`} className={styles.step}>
          {step.status === 'done' ? (
            <Check size={14} color="var(--color-canopy)" aria-hidden="true" />
          ) : (
            <Loader2 size={14} className={styles.spin} aria-hidden="true" />
          )}
          <span>{step.label}</span>
          <code className={styles.stepTool}>{step.tool}</code>
        </div>
      ))}
    </div>
  );
}

export function AgentPanel({
  messages,
  draft,
  busy,
  lang = 'id',
  onDraftChange,
  onSend,
  onNewThread,
  onHighlight,
  onSelect,
}: AgentPanelProps) {
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = threadRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages]);

  return (
    <aside className={styles.panel} aria-label={t(lang, 'agent.aria')}>
      <div className={styles.header}>
        <div>
          <div className={styles.headerTitle}>{t(lang, 'agent.title')}</div>
          <div className={styles.headerSub}>{t(lang, 'agent.subtitle')}</div>
        </div>
        <button
          type="button"
          className={styles.iconButton}
          onClick={onNewThread}
          aria-label={t(lang, 'agent.newThread')}
        >
          <Pencil size={16} />
        </button>
      </div>

      <div className={styles.thread} ref={threadRef}>
        {messages.map((message) =>
          message.role === 'user' ? (
            <div key={message.id} className={styles.user}>
              {message.text}
            </div>
          ) : (
            <div key={message.id}>
              {message.steps.length > 0 && (
                <StepBlock steps={message.steps} elapsedMs={message.elapsedMs} lang={lang} />
              )}
              {message.error && <div className={styles.error}>{message.error}</div>}
              {message.text && (
                <div className={styles.prose}>
                  {/*
                    The agent answers in Markdown, so it has to be rendered as Markdown --
                    otherwise a table arrives on screen as raw `| Indikator | Nilai |`.
                    react-markdown builds React elements rather than setting innerHTML, so
                    model output can never inject markup; raw HTML in the stream stays
                    inert, which is what we want from text an LLM produced. GFM is needed
                    for the tables themselves.
                  */}
                  <Markdown remarkPlugins={[remarkGfm]}>{message.text}</Markdown>
                </div>
              )}
              {message.steps
                .filter((step) => step.status === 'done' && step.response)
                .map((step, index) => (
                  <ResultTable
                    key={`${step.tool}-card-${index}`}
                    tool={step.tool}
                    response={step.response!}
                    lang={lang}
                    onHighlight={onHighlight}
                    onSelect={onSelect}
                  />
                ))}
            </div>
          ),
        )}
      </div>

      <div className={styles.composer}>
        <div className={styles.composerBox}>
          <textarea
            value={draft}
            placeholder={t(lang, 'agent.placeholder')}
            aria-label={t(lang, 'agent.composerLabel')}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (draft.trim() && !busy) onSend();
              }
            }}
          />
          <a
            href="/cek-atap"
            className={styles.iconButton}
            aria-label={t(lang, 'agent.cekAtap')}
          >
            <Camera size={16} />
          </a>
          <button
            type="button"
            className={styles.send}
            disabled={!draft.trim() || busy}
            onClick={onSend}
            aria-label={t(lang, 'agent.send')}
          >
            {busy ? <Loader2 size={16} className={styles.spin} /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </aside>
  );
}
