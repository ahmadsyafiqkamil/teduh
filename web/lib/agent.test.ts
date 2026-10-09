import { describe, expect, it } from 'vitest';
import { eventsToSteps, parseSseChunk } from './agent';

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
