/**
 * SSE client for the ADK agent endpoint.
 *
 * The step list is built from functionCall/functionResponse parts rather than from the
 * model's prose, and the structured response is kept alongside each step. That is what lets
 * the chat render result cards from verified tool output instead of parsing numbers back
 * out of generated text -- design/README.md is explicit that cards come from tool data
 * "agar angka terverifikasi".
 *
 * A malformed SSE frame is skipped rather than thrown, because one bad frame must not kill
 * a live answer halfway through.
 *
 * The /run_sse payload shape moves between ADK releases. Verify against
 * `curl localhost:8080/openapi.json` before changing anything here.
 */

import { API_BASE } from './api';

export const APP_NAME = 'teduh_agent';

/** Indonesian labels for the step list; keys are the tool names from M3/M5/M6. */
const TOOL_LABELS: Record<string, string> = {
  find_area: 'Mencari wilayah',
  get_area_profile: 'Mengambil profil kelurahan',
  rank_priority_areas: 'Menghitung indeks kerentanan',
  explain_drivers: 'Menganalisis faktor pendorong',
  simulate_intervention: 'Menyimulasikan intervensi',
  optimize_portfolio: 'Menyusun portofolio anggaran',
  get_evidence: 'Mengambil temuan literatur',
  get_session_facts: 'Mengumpulkan fakta percakapan',
  render_policy_brief: 'Menyusun policy brief',
  analyze_roof_photo: 'Menganalisis foto atap',
  recommend_roof_action: 'Menyusun rekomendasi atap',
};

export interface AgentStep {
  tool: string;
  label: string;
  args: Record<string, unknown>;
  status: 'running' | 'done';
  response?: Record<string, unknown>;
}

export type AgentEvent =
  | { kind: 'text'; text: string }
  | { kind: 'steps'; steps: AgentStep[] }
  | { kind: 'done' }
  | { kind: 'error'; message: string };

export async function createSession(userId: string): Promise<string> {
  const sessionId = `s-${Date.now().toString(36)}`;
  // ADK exposes POST /apps/{app}/users/{user}/sessions (CreateSessionRequest) as the current
  // path. The deprecated /sessions/{session_id} variant still exists but is slated for
  // removal; request the modern one with an explicit session id.
  const response = await fetch(
    `${API_BASE}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    },
  );
  if (!response.ok) {
    throw new Error(`Gagal membuat sesi agen (status ${response.status}).`);
  }
  return sessionId;
}

/** Split a buffer into complete SSE events, returning the unparsed tail. */
export function parseSseChunk(buffer: string): { events: unknown[]; rest: string } {
  const frames = buffer.split('\n\n');
  const rest = frames.pop() ?? '';
  const events: unknown[] = [];

  for (const frame of frames) {
    for (const line of frame.split('\n')) {
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;
      try {
        events.push(JSON.parse(payload));
      } catch {
        // One bad frame must not end a live answer.
      }
    }
  }
  return { events, rest };
}

interface RawPart {
  text?: string;
  functionCall?: { name: string; args?: Record<string, unknown> };
  functionResponse?: { name: string; response?: Record<string, unknown> };
}

function partsOf(event: unknown): RawPart[] {
  const content = (event as { content?: { parts?: RawPart[] } })?.content;
  return content?.parts ?? [];
}

export function eventsToSteps(raw: unknown[]): AgentStep[] {
  const steps: AgentStep[] = [];

  for (const event of raw) {
    for (const part of partsOf(event)) {
      if (part.functionCall) {
        const { name, args } = part.functionCall;
        steps.push({
          tool: name,
          label: TOOL_LABELS[name] ?? `Menjalankan ${name}`,
          args: args ?? {},
          status: 'running',
        });
      }
      if (part.functionResponse) {
        const { name, response } = part.functionResponse;
        const pending = [...steps].reverse().find(
          (step) => step.tool === name && step.status === 'running',
        );
        if (pending) {
          pending.status = 'done';
          pending.response = response ?? {};
        }
      }
    }
  }
  return steps;
}

export function textOf(raw: unknown[]): string {
  return raw
    .flatMap(partsOf)
    .map((part) => part.text ?? '')
    .join('');
}

export async function* streamAgent(options: {
  userId: string;
  sessionId: string;
  message: string;
  signal?: AbortSignal;
}): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${API_BASE}/run_sse`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    signal: options.signal,
    body: JSON.stringify({
      appName: APP_NAME,
      userId: options.userId,
      sessionId: options.sessionId,
      newMessage: { role: 'user', parts: [{ text: options.message }] },
      streaming: true,
    }),
  });

  if (!response.ok || !response.body) {
    yield {
      kind: 'error',
      message: `Agen tidak bisa dihubungi (status ${response.status}).`,
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const collected: unknown[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;

    if (events.length) {
      collected.push(...events);
      const text = textOf(collected);
      if (text) yield { kind: 'text', text };
      const steps = eventsToSteps(collected);
      if (steps.length) yield { kind: 'steps', steps };
    }
  }
  yield { kind: 'done' };
}
