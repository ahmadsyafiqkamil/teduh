import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CekAtap from './page';

const ASBESTOS = {
  roof: {
    roof_visible: true, roof_form: 'pitched', material: 'asbestos_cement',
    color_tone: 'medium', condition: 'worn', shade_from_trees: 'none',
    confidence: 0.82, notes: 'Atap bergelombang kelabu kusam.',
  },
  recommendation: {
    action: 'consult_professional', priority: 'tinggi',
    reason: 'Atap terindikasi asbes.',
    safety: ['JANGAN mengamplas, memotong, atau mengebor atap ini.'],
    evidence_ids: ['ev_green_curtain_tokyo'],
  },
  evidence: [],
  guidance: '',
  kelurahan: null,
  facts: [],
};

function mockRoof(payload: unknown = ASBESTOS) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ success: true, data: payload, error: null }),
    }),
  );
}

function photo() {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], 'atap.jpg', { type: 'image/jpeg' });
}

afterEach(() => vi.unstubAllGlobals());

describe('Cek Atap', () => {
  it('explains what to photograph before asking for a file', () => {
    render(<CekAtap />);
    expect(screen.getByText(/atap rumah/i)).toBeInTheDocument();
  });

  it('warns not to include identifying details in the frame', () => {
    // CLAUDE.md rule 8. The instruction has to be visible before the upload, not after.
    render(<CekAtap />);
    expect(screen.getByText(/nomor rumah|plat nomor|wajah/i)).toBeInTheDocument();
  });

  it('accepts only image files', () => {
    render(<CekAtap />);
    expect(screen.getByLabelText(/pilih foto/i)).toHaveAttribute('accept', 'image/jpeg,image/png');
  });

  it('shows the classification after upload', async () => {
    mockRoof();
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    // "asbes" appears in both the reason and the material label.
    expect((await screen.findAllByText(/asbes/i)).length).toBeGreaterThanOrEqual(1);
  });

  it('shows the asbestos safety warning prominently', async () => {
    mockRoof();
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    const warning = await screen.findByRole('alert');
    expect(warning).toHaveTextContent(/JANGAN mengamplas/);
  });

  it('asks for a retake when confidence is low', async () => {
    mockRoof({
      ...ASBESTOS,
      roof: { ...ASBESTOS.roof, confidence: 0.3 },
      recommendation: { action: 'retake_photo', priority: '-', reason: 'Belum jelas.', safety: [], evidence_ids: [] },
      guidance: 'Coba foto ulang dari sudut yang memperlihatkan bidang atap.',
    });
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    // "foto ulang" appears in both the action heading and the guidance line.
    expect((await screen.findAllByText(/foto ulang/i)).length).toBeGreaterThanOrEqual(1);
  });

  it('surfaces a server error instead of silently doing nothing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 415,
      json: async () => ({ success: false, data: null, error: 'Format foto harus image/jpeg.' }),
    }));
    const user = userEvent.setup();
    render(<CekAtap />);

    await user.upload(screen.getByLabelText(/pilih foto/i), photo());

    expect(await screen.findByText(/Format foto harus/)).toBeInTheDocument();
  });

  it('states that the photo is not stored', async () => {
    // docs/DECISIONS.md: the photo never touches disk. Saying so is the point.
    render(<CekAtap />);
    expect(screen.getByText(/tidak disimpan/i)).toBeInTheDocument();
  });

  it('links back to the main screen', () => {
    render(<CekAtap />);
    expect(screen.getByRole('link', { name: /TEDUH/i })).toHaveAttribute('href', '/');
  });
});
