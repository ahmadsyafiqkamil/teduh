import { describe, expect, it } from 'vitest';
import { errorOf, eventsToSteps, isPartial, parseSseChunk, textOf } from './agent';

describe('parseSseChunk', () => {
  it('extracts complete events and keeps the partial tail', () => {
    const { events, rest } = parseSseChunk('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c"');
    expect(events).toEqual([{ a: 1 }, { b: 2 }]);
    expect(rest).toBe('data: {"c"');
  });

  it('returns nothing when no event is complete yet', () => {
    const { events, rest } = parseSseChunk('data: {"partial":');
    expect(events).toEqual([]);
    expect(rest).toBe('data: {"partial":');
  });

  it('ignores the [DONE] sentinel', () => {
    expect(parseSseChunk('data: [DONE]\n\n').events).toEqual([]);
  });

  it('skips a malformed event rather than throwing', () => {
    // A single bad frame must not kill a live stream mid-answer.
    const { events } = parseSseChunk('data: {bukan json}\n\ndata: {"ok":true}\n\n');
    expect(events).toEqual([{ ok: true }]);
  });
});

describe('eventsToSteps', () => {
  it('turns a function call into a running step', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'find_area', args: { query: 'Jakarta Timur' } } }] } },
    ]);
    expect(steps).toEqual([
      expect.objectContaining({ tool: 'find_area', status: 'running' }),
    ]);
  });

  it('marks a step done once its response arrives', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'find_area', args: {} } }] } },
      { content: { parts: [{ functionResponse: { name: 'find_area', response: { matches: [] } } }] } },
    ]);
    expect(steps[0].status).toBe('done');
  });

  it('labels each known tool in Indonesian', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'rank_priority_areas', args: {} } }] } },
    ]);
    expect(steps[0].label).toMatch(/kerentanan|prioritas/i);
  });

  it('keeps the tool name for an unknown tool instead of hiding the step', () => {
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'tool_baru', args: {} } }] } },
    ]);
    expect(steps[0].label).toContain('tool_baru');
  });

  it('keeps the structured tool response so result cards render from data', () => {
    // design/README.md: "kartu hasil dirender dari output tool terstruktur, bukan dari
    // teks LLM, agar angka terverifikasi."
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'rank_priority_areas', args: {} } }] } },
      {
        content: {
          parts: [
            {
              functionResponse: {
                name: 'rank_priority_areas',
                response: { areas: [{ kel_id: 'ID3173040002', hvi: 0.93 }] },
              },
            },
          ],
        },
      },
    ]);
    expect(steps[0].response).toEqual({ areas: [{ kel_id: 'ID3173040002', hvi: 0.93 }] });
  });

  it('ignores plain text parts, which are prose not steps', () => {
    expect(eventsToSteps([{ content: { parts: [{ text: 'Lima kelurahan…' }] } }])).toEqual([]);
  });

  it('tolerates an event with no content', () => {
    expect(eventsToSteps([{}, { content: {} }])).toEqual([]);
  });
});

describe('isPartial', () => {
  // ADK streams a token delta per event with `partial: true`, then repeats the whole turn
  // once with the flag absent. Counting both renders every answer twice and inflates the
  // step list -- one real tool call was showing up as fifteen.
  it('recognises a streaming delta', () => {
    expect(isPartial({ partial: true, content: { parts: [{ text: 'Rawa' }] } })).toBe(true);
  });

  it('treats an aggregated event as final', () => {
    expect(isPartial({ content: { parts: [{ text: 'Rawa Buaya' }] } })).toBe(false);
  });

  it('treats a non-streaming backend, which never sets the flag, as final', () => {
    expect(isPartial({ partial: false, content: { parts: [] } })).toBe(false);
    expect(isPartial({})).toBe(false);
  });
});

describe('textOf with streaming deltas', () => {
  it('counts the answer once when deltas are followed by the aggregate', () => {
    const final = [{ content: { parts: [{ text: 'Rawa Buaya 42,01 °C' }] } }];
    expect(textOf(final)).toBe('Rawa Buaya 42,01 °C');
  });

  it('still joins multiple distinct final events in order', () => {
    const events = [
      { content: { parts: [{ text: 'Bagian satu. ' }] } },
      { content: { parts: [{ text: 'Bagian dua.' }] } },
    ];
    expect(textOf(events)).toBe('Bagian satu. Bagian dua.');
  });

  it('drops a preamble that shares its event with a tool call', () => {
    // The model narrates what it is about to do ("I'll route this to…", "I'll start by
    // locating…") in the same turn it calls the tool. That text is reasoning, not an
    // answer, and must not reach the screen.
    const events = [
      {
        content: {
          parts: [
            { text: "I'll route this to the heat analyst first." },
            { functionCall: { name: 'find_area', args: {} } },
          ],
        },
      },
      {
        content: { parts: [{ text: 'Berikut analisis panas Karet Tengsin.' }] },
      },
    ];
    expect(textOf(events)).toBe('Berikut analisis panas Karet Tengsin.');
  });

  it('drops a thought part from a thinking model', () => {
    const events = [
      {
        content: {
          parts: [
            { text: 'pertimbangan internal', thought: true },
            { text: 'Jawaban untuk pengguna.' },
          ],
        },
      },
    ];
    expect(textOf(events)).toBe('Jawaban untuk pengguna.');
  });
});

describe('eventsToSteps with streaming deltas', () => {
  it('records one step per tool call, not one per delta', () => {
    // The same functionCall arrives on every partial frame while the args stream in.
    const steps = eventsToSteps([
      { content: { parts: [{ functionCall: { name: 'find_area', args: {} } }] } },
    ]);
    expect(steps).toHaveLength(1);
  });
});

describe('errorOf', () => {
  // An ADK failure arrives as HTTP 200 with an error frame in the stream, so response.ok
  // is useless here. Without this the panel sat empty with nothing explaining why.
  it('reads the ADK errorMessage frame', () => {
    expect(
      errorOf({ errorCode: 'ValueError', errorMessage: 'No API key was provided.' }),
    ).toBe('No API key was provided.');
  });

  it('reads the plain error frame', () => {
    expect(errorOf({ error: 'ValueError: kunci API tidak ada' })).toBe(
      'ValueError: kunci API tidak ada',
    );
  });

  it('returns null for an ordinary content event', () => {
    expect(errorOf({ content: { parts: [{ text: 'halo' }] } })).toBeNull();
  });

  it('returns null for a non-object frame', () => {
    expect(errorOf(null)).toBeNull();
    expect(errorOf('kosong')).toBeNull();
  });
});
