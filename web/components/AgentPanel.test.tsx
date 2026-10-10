import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AgentPanel, type ChatMessage } from './AgentPanel';

/**
 * The agent writes Markdown -- headings, bold, and GFM tables -- because that is what the
 * prompt asks for. Rendering it as plain text put raw `**` and `| Indikator | Nilai |` on
 * screen, which tells the "angka terverifikasi" story badly.
 */

const NOOP = {
  draft: '',
  busy: false,
  onDraftChange: vi.fn(),
  onSend: vi.fn(),
  onNewThread: vi.fn(),
  onHighlight: vi.fn(),
  onSelect: vi.fn(),
};

function agentMessage(text: string): ChatMessage {
  return { id: 'm1', role: 'agent', text, steps: [] };
}

function renderWith(text: string) {
  render(<AgentPanel messages={[agentMessage(text)]} {...NOOP} />);
}

describe('AgentPanel prose', () => {
  it('renders a GFM table as a real table', () => {
    renderWith(
      ['| Indikator | Nilai |', '|---|---|', '| Tutupan pohon | 8,5% |'].join('\n'),
    );

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Indikator' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Tutupan pohon' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '8,5%' })).toBeInTheDocument();
  });

  it('leaves no raw pipe syntax on screen', () => {
    renderWith(['| Indikator | Nilai |', '|---|---|', '| HVI | 0,21 |'].join('\n'));
    expect(screen.queryByText(/\|---\|/)).toBeNull();
  });

  it('renders a heading as a heading, not as hash characters', () => {
    renderWith('## Kelurahan Rawa Buaya');
    expect(
      screen.getByRole('heading', { name: 'Kelurahan Rawa Buaya' }),
    ).toBeInTheDocument();
  });

  it('renders bold emphasis instead of printing the asterisks', () => {
    renderWith('Suhu permukaan rata-rata: **42,01 °C** di wilayah itu.');
    expect(screen.getByText('42,01 °C').tagName).toBe('STRONG');
    expect(screen.queryByText(/\*\*/)).toBeNull();
  });

  it('renders a bullet list as list items', () => {
    renderWith(['- Lahan terbangun: 84,9%', '- Tutupan pohon: 8,5%'].join('\n'));
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('keeps a plain-text answer intact', () => {
    renderWith('Rawa Buaya berada di peringkat 136 dari 264 kelurahan.');
    expect(
      screen.getByText('Rawa Buaya berada di peringkat 136 dari 264 kelurahan.'),
    ).toBeInTheDocument();
  });

  it('shows the user turn as written, without Markdown treatment', () => {
    // A question containing * or # is the user's own text, not a formatting instruction.
    render(
      <AgentPanel
        messages={[{ id: 'u1', role: 'user', text: 'Apa arti **HVI**?', steps: [] }]}
        {...NOOP}
      />,
    );
    expect(screen.getByText('Apa arti **HVI**?')).toBeInTheDocument();
  });
});
