import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, briefUrl, fetchKelurahan, fetchProfile, postSimulate } from './api';

function mockFetch(body: unknown, ok = true, status = 200) {
  const spy = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('envelope unwrapping', () => {
  it('returns the data field on success', async () => {
    mockFetch({ success: true, data: { type: 'FeatureCollection', features: [] }, error: null });
    const result = await fetchKelurahan();
    expect(result.features).toEqual([]);
  });

  it('throws ApiError carrying the server message on a failed envelope', async () => {
    // The API puts a human Indonesian message in `error`; swallowing it and showing
    // "something went wrong" throws away the only useful thing on screen.
    mockFetch({ success: false, data: null, error: 'Kelurahan tidak ada di data TEDUH.' }, false, 404);
    await expect(fetchProfile('ID9999999999')).rejects.toThrow('Kelurahan tidak ada');
  });

  it('throws ApiError with the status when the body is not an envelope', async () => {
    mockFetch('bukan json', false, 502);
    await expect(fetchKelurahan()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('request shapes', () => {
  it('posts the simulate body as JSON', async () => {
    const spy = mockFetch({ success: true, data: { results: [] }, error: null });
    await postSimulate({
      kel_ids: ['ID3173040002'],
      interventions: [{ type: 'cool_roof', level: 'medium' }],
    });

    const [, init] = spy.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.headers['content-type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({
      kel_ids: ['ID3173040002'],
      interventions: [{ type: 'cool_roof', level: 'medium' }],
    });
  });

  it('builds the profile URL from the kelurahan id', async () => {
    const spy = mockFetch({ success: true, data: {}, error: null });
    await fetchProfile('ID3173040002');
    expect(spy.mock.calls[0][0]).toContain('/api/kelurahan/ID3173040002');
  });
});

describe('briefUrl', () => {
  it('defaults to markdown', () => {
    expect(briefUrl('abc123def456')).toContain('/api/brief/abc123def456');
  });

  it('asks for pdf when requested', () => {
    expect(briefUrl('abc123def456', 'pdf')).toContain('format=pdf');
  });
});
