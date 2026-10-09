/**
 * Typed client for the TEDUH API.
 *
 * Unwraps the {success, data, error} envelope in one place and preserves the server's
 * Indonesian message when something fails. That matters: the API already writes an
 * explanation a planner can act on ("Coba naikkan anggaran atau turunkan porsi keadilan"),
 * and replacing it with a generic failure string throws away the only useful thing that
 * would have been on screen.
 */

import type {
  KelurahanCollection,
  ModelCard,
  OptimizeResponse,
  ProfileResponse,
  RoofResponse,
  SimulateResponse,
} from './types';

export const API_BASE =
  process.env.NEXT_PUBLIC_TEDUH_API ?? 'http://localhost:8080';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(
      `Server tidak mengembalikan JSON (status ${response.status}).`,
      response.status,
    );
  }

  const envelope = body as Envelope<T>;
  if (envelope && typeof envelope === 'object' && 'success' in envelope) {
    if (envelope.success && envelope.data !== null) return envelope.data;
    throw new ApiError(
      envelope.error ?? `Permintaan gagal (status ${response.status}).`,
      response.status,
    );
  }

  // FastAPI validation errors (422) are not enveloped.
  throw new ApiError(
    `Permintaan tidak valid (status ${response.status}).`,
    response.status,
  );
}

function jsonPost(payload: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  };
}

export function fetchKelurahan(): Promise<KelurahanCollection> {
  return request<KelurahanCollection>('/api/kelurahan');
}

export function fetchProfile(kelId: string): Promise<ProfileResponse> {
  return request<ProfileResponse>(`/api/kelurahan/${encodeURIComponent(kelId)}`);
}

export function postSimulate(payload: {
  kel_ids: string[];
  interventions: { type: string; level?: string; params?: Record<string, number> }[];
}): Promise<SimulateResponse> {
  return request<SimulateResponse>('/api/simulate', jsonPost(payload));
}

export function postOptimize(payload: {
  scope?: string;
  budget_idr: number;
  equity_share?: number | null;
  allowed?: string[] | null;
}): Promise<OptimizeResponse> {
  return request<OptimizeResponse>('/api/optimize', jsonPost(payload));
}

export function fetchModelCard(): Promise<ModelCard> {
  return request<ModelCard>('/api/model-card');
}

export function postRoof(photo: File, kelurahan?: string): Promise<RoofResponse> {
  const form = new FormData();
  form.append('photo', photo);
  if (kelurahan) form.append('kelurahan', kelurahan);
  // No content-type header: the browser must set the multipart boundary itself.
  return request<RoofResponse>('/api/roof', { method: 'POST', body: form });
}

export function briefUrl(briefId: string, format: 'md' | 'pdf' = 'md'): string {
  return `${API_BASE}/api/brief/${encodeURIComponent(briefId)}?format=${format}`;
}
