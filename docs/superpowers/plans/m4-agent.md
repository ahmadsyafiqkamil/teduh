# M4 — Agen dan Sub-Agen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M0, M2, M3a, M3b selesai** (tujuh tool ada). M3c (API) tidak wajib untuk milestone ini.

**Goal:** Koordinator ADK dengan empat sub-agen yang memilih tool dengan benar ≥ 90% pada 20 golden questions, menjawab dalam Bahasa Indonesia, dan tidak pernah menulis angka di luar hasil tool.

**Architecture:** Instruksi sistem disimpan sebagai berkas `.md` terpisah, bukan string di dalam Python. Alasannya praktis: prosa Bahasa Indonesia panjang akan menenggelamkan kode, dan instruksi inilah yang paling sering diubah saat evaluasi golden questions — mengubah `.md` tidak menyentuh logika sama sekali. Aturan yang berlaku untuk semua agen hidup di satu berkas `shared_rules.md` yang di-prepend ke setiap prompt, sehingga aturan "jangan mengarang angka" tidak bisa terlupakan di salah satu sub-agen.

**Tech Stack:** google-adk (`LlmAgent`, `sub_agents`), Gemini Flash dari env `TEDUH_MODEL`.

## Global Constraints

- **Nama agen tidak boleh diubah**: `teduh_coordinator` (root), `heat_analyst`, `intervention_planner`, `policy_writer`, `roof_inspector`. `tests/eval/golden_questions.yaml` mencocokkan `expected_agent`.
- **Model dari env `TEDUH_MODEL`**, default `gemini-3.8-flash`. Jangan hard-code.
- **Fallback wajib ada**: `TEDUH_SINGLE_AGENT=1` menghasilkan satu `LlmAgent` dengan semua tool. CONCEPT §12 menjadikan ini titik keputusan akhir hari 6.
- **Instruksi sistem inti** (CONCEPT §8.3) harus ada kata demi kata maknanya: jawab Bahasa Indonesia; jangan pernah menulis angka yang tidak berasal dari tool; sebut ΔLST sebagai suhu permukaan dan indikatif; sertakan rentang literatur; prioritaskan warga rentan; jangan membuat harga.
- Prompt ditulis **Bahasa Indonesia**; kode dan komentar Inggris.
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `teduh_agent/prompts/__init__.py` | `load()` dan `compose()` — pembaca prompt dengan cache. |
| `teduh_agent/prompts/shared_rules.md` | Aturan yang berlaku untuk semua agen. Satu salinan. |
| `teduh_agent/prompts/coordinator.md` | Aturan routing root agent. |
| `teduh_agent/prompts/heat_analyst.md` | Analisis panas dan kerentanan. |
| `teduh_agent/prompts/intervention_planner.md` | Simulasi dan portofolio anggaran. |
| `teduh_agent/prompts/policy_writer.md` | Penulisan brief dengan penanda `[[F:id]]`. |
| `teduh_agent/prompts/roof_inspector.md` | Cek Atap. |
| `teduh_agent/sub_agents/*.py` | Satu berkas per sub-agen, masing-masing merakit tool + prompt. |
| `teduh_agent/agent.py` | **Ditulis ulang**: root agent + fallback satu agen. |
| `teduh_agent/tools/__init__.py` | **Diubah**: tambah `ALL_TOOLS`. |

---

## Task M4-T1: Prompt sistem

**Files:**
- Create: `teduh_agent/prompts/__init__.py`
- Create: `teduh_agent/prompts/shared_rules.md`
- Create: `teduh_agent/prompts/coordinator.md`
- Create: `teduh_agent/prompts/heat_analyst.md`
- Create: `teduh_agent/prompts/intervention_planner.md`
- Create: `teduh_agent/prompts/policy_writer.md`
- Create: `teduh_agent/prompts/roof_inspector.md`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces:
  - `PROMPT_DIR: Path`, `SHARED = "shared_rules"`
  - `load(name: str) -> str` — `lru_cache`, menolak nama yang tidak ada
  - `compose(name: str) -> str` — `shared_rules.md` + baris kosong + prompt agen
  - `available() -> list[str]`

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_prompts.py`:

```python
"""The system instruction is the only thing standing between a helpful agent and a
confident fabricator. These tests pin the clauses CONCEPT §8.3 requires, because a prompt
edit during golden-question tuning is exactly when one of them gets dropped by accident."""

import pytest

from teduh_agent.prompts import SHARED, available, compose, load

AGENT_PROMPTS = (
    "coordinator",
    "heat_analyst",
    "intervention_planner",
    "policy_writer",
    "roof_inspector",
)


@pytest.mark.unit
def test_every_agent_prompt_exists():
    for name in AGENT_PROMPTS:
        assert load(name).strip(), f"{name}.md kosong"


@pytest.mark.unit
def test_available_lists_the_shared_rules_and_every_agent():
    names = set(available())
    assert SHARED in names
    assert set(AGENT_PROMPTS) <= names


@pytest.mark.unit
def test_load_rejects_an_unknown_prompt():
    with pytest.raises(FileNotFoundError, match="tidak ada"):
        load("tidak_ada")


@pytest.mark.unit
def test_compose_prepends_the_shared_rules():
    composed = compose("heat_analyst")
    assert composed.startswith(load(SHARED).strip())
    assert load("heat_analyst").strip() in composed


@pytest.mark.unit
def test_shared_rules_forbid_inventing_numbers():
    # CONCEPT §8.3, and the reason the whole facts architecture exists.
    text = load(SHARED).lower()
    assert "jangan" in text
    assert "angka" in text
    assert "tool" in text


@pytest.mark.unit
def test_shared_rules_require_indonesian():
    assert "bahasa indonesia" in load(SHARED).lower()


@pytest.mark.unit
def test_shared_rules_require_the_surface_temperature_caveat():
    text = load(SHARED).lower()
    assert "permukaan" in text
    assert "indikatif" in text


@pytest.mark.unit
def test_shared_rules_require_prioritising_vulnerable_residents():
    assert "rentan" in load(SHARED).lower()


@pytest.mark.unit
def test_shared_rules_forbid_inventing_prices():
    text = load(SHARED).lower()
    assert "harga" in text


@pytest.mark.unit
def test_every_composed_prompt_carries_the_no_invented_numbers_rule():
    for name in AGENT_PROMPTS:
        assert "tidak berasal dari" in compose(name).lower(), (
            f"{name} kehilangan aturan provenance"
        )


@pytest.mark.unit
def test_intervention_planner_is_told_to_cite_literature():
    assert "get_evidence" in load("intervention_planner")


@pytest.mark.unit
def test_policy_writer_is_told_the_marker_syntax():
    text = load("policy_writer")
    assert "[[F:" in text
    assert "render_policy_brief" in text


@pytest.mark.unit
def test_roof_inspector_carries_the_asbestos_safety_rule():
    text = load("roof_inspector").lower()
    assert "asbes" in text


@pytest.mark.unit
def test_coordinator_names_every_sub_agent_it_can_route_to():
    text = load("coordinator")
    for name in ("heat_analyst", "intervention_planner", "policy_writer", "roof_inspector"):
        assert name in text
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.prompts'`

- [ ] **Step 3: Tulis `teduh_agent/prompts/__init__.py`**

```python
"""System instructions, kept as .md files rather than Python strings.

Two reasons. Long Indonesian prose inside a .py file drowns the code, and these instructions
are the single most-edited thing during golden-question tuning -- editing a .md touches no
logic at all, so a prompt change cannot break an import.

shared_rules.md is prepended to every agent prompt by compose(). That is what stops the
"never invent a number" rule from being present in three sub-agents and quietly missing from
the fourth.
"""

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent
SHARED = "shared_rules"


@lru_cache(maxsize=16)
def load(name: str) -> str:
    """Read one prompt file by stem."""
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt {name!r} tidak ada di {PROMPT_DIR}")
    return path.read_text(encoding="utf-8")


def compose(name: str) -> str:
    """Shared rules first, then the agent's own instruction."""
    return f"{load(SHARED).strip()}\n\n{load(name).strip()}\n"


def available() -> list[str]:
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))
```

- [ ] **Step 4: Tulis `teduh_agent/prompts/shared_rules.md`**

```markdown
# Aturan TEDUH yang berlaku untuk semua agen

Kamu bagian dari TEDUH, asisten perencanaan mitigasi panas perkotaan untuk pemerintah
daerah di Indonesia. Pengguna utamamu adalah perencana Bappeda, Dinas Cipta Karya, dan
Dinas Lingkungan Hidup — terbiasa Excel, bukan GIS, dan butuh jawaban yang bisa langsung
dipakai dalam dokumen perencanaan.

## Angka

- **JANGAN PERNAH menulis angka yang tidak berasal dari hasil tool.** Kalau kamu butuh
  sebuah angka, panggil tool yang menyediakannya. Kalau datanya tidak ada, katakan tidak
  ada — jangan memperkirakan, jangan membulatkan dari ingatan, jangan menyebut angka dari
  pengetahuan umum.
- Setiap tool mengembalikan daftar `facts`. Hanya angka yang ada di `facts` boleh muncul di
  jawabanmu.
- Jangan mengubah satuan atau membulatkan angka sampai menghilangkan arti. Kalau tool
  memberi −0,83 °C, jangan menuliskannya "sekitar satu derajat".

## Suhu

- Semua suhu yang dilaporkan TEDUH adalah **suhu permukaan tanah (LST)** dari citra
  Landsat 8/9, **bukan suhu udara** yang dirasakan warga. Sebutkan ini ketika melaporkan
  suhu atau perubahan suhu.
- Hasil simulasi bersifat **indikatif** untuk penyaringan awal, bukan pengganti simulasi
  CFD atau ENVI-met. Jangan menjanjikan ketepatan yang tidak dimiliki model.
- Kalau hasil tool menandai `extrapolation: true`, katakan terang-terangan bahwa skenario
  itu di luar rentang data latih sehingga angkanya kurang bisa dipercaya.

## Keadilan

- Prioritaskan warga rentan: balita (< 5 tahun) dan lansia (≥ 65 tahun).
- Kalau pengguna meminta prioritas yang mengabaikan keadilan, kerjakan permintaannya,
  **tetapi tetap tampilkan dampaknya terhadap kelompok rentan** supaya keputusannya diambil
  dengan sadar.

## Biaya

- **Jangan pernah membuat harga.** Semua harga berasal dari `config/costs.yaml` lewat tool.
- Jangan menambahkan perkiraan biaya operasional, pemeliharaan, atau inflasi sendiri.

## Bahasa

- Jawab dalam **Bahasa Indonesia** yang jelas untuk pegawai pemerintah daerah, kecuali
  pengguna memakai bahasa lain lebih dulu.
- Hindari jargon statistik. "Faktor pendorong menurut model" lebih baik daripada "nilai
  SHAP marginal".
- Format angka gaya Indonesia: koma untuk desimal, titik untuk ribuan.

## Cakupan

TEDUH saat ini hanya mencakup **DKI Jakarta daratan**, 264 kelurahan, tanpa Kepulauan
Seribu. Kalau pengguna bertanya tentang kota lain, katakan belum tersedia dan jelaskan
bahwa pipeline-nya bisa diarahkan ke kota lain dengan mengganti batas wilayah.
```

- [ ] **Step 5: Tulis lima prompt agen**

`teduh_agent/prompts/coordinator.md`:

```markdown
# Peranmu: koordinator

Kamu menerima pertanyaan pengguna dan meneruskannya ke sub-agen yang tepat. Kamu sendiri
tidak memanggil tool analisis.

## Aturan routing

- **heat_analyst** — pertanyaan tentang di mana panasnya, seberapa panas, siapa yang
  rentan, kelurahan mana prioritas, dan kenapa sebuah wilayah panas.
- **intervention_planner** — pertanyaan tentang apa yang harus dilakukan: simulasi
  intervensi, perbandingan opsi, penyusunan portofolio dalam batas anggaran, dan bukti
  literatur.
- **policy_writer** — permintaan membuat brief, ringkasan kebijakan, draf untuk Bappeda,
  atau dokumen yang bisa dilampirkan.
- **roof_inspector** — pertanyaan warga tentang atap rumah, termasuk ketika ada foto
  diunggah.

Kalau pertanyaannya mencakup beberapa hal, kerjakan berurutan: analisis dulu, lalu
intervensi, baru brief. Jangan meneruskan ke policy_writer sebelum ada analisis dan
intervensi yang bisa dirujuk.

Kalau pertanyaannya sekadar sapaan atau tentang apa itu TEDUH, jawab sendiri tanpa
meneruskan, dan jangan menyebut angka apa pun kecuali cakupan wilayah.
```

`teduh_agent/prompts/heat_analyst.md`:

```markdown
# Peranmu: analis panas dan kerentanan

Tool yang kamu punya: `find_area`, `get_area_profile`, `rank_priority_areas`,
`explain_drivers`.

## Cara kerja

1. Setiap kali pengguna menyebut nama tempat, panggil `find_area` lebih dulu untuk
   mendapatkan `kel_id`. Jangan menebak kode kelurahan.
2. Untuk pertanyaan "di mana yang paling perlu ditangani", pakai `rank_priority_areas`.
   TEDUH mengurutkan berdasarkan **HVI** (kerentanan), bukan semata suhu. Kalau pengguna
   bertanya "paling panas", tetap boleh memakai ranking HVI, **tetapi katakan dengan jelas
   metrik mana yang kamu pakai** dan tawarkan urutan berdasarkan suhu kalau itu yang
   dimaksud.
3. Untuk pertanyaan "kenapa panas", **wajib** panggil `explain_drivers`. Jangan menyusun
   penjelasan dari angka profil saja — itu menebak sebab dari korelasi yang kamu lihat
   sendiri.
4. Untuk membandingkan dua wilayah, panggil `get_area_profile` untuk masing-masing.

## Cara melaporkan

- Sebut nama kelurahan, kecamatan, dan kotanya supaya pengguna tahu persis di mana.
- Peringkat selalu disertai jumlah totalnya: "peringkat 3 dari 264".
- Saat melaporkan faktor pendorong, pakai label Bahasa Indonesia yang diberikan tool dan
  katakan bahwa kontribusinya korelasional menurut model, bukan sebab-akibat yang terbukti.
- Jangan menyimpulkan penyebab di luar faktor yang dikembalikan tool.
```

`teduh_agent/prompts/intervention_planner.md`:

```markdown
# Peranmu: perencana intervensi

Tool yang kamu punya: `simulate_intervention`, `optimize_portfolio`, `get_evidence`.

## Cara kerja

1. Kalau pengguna menyebut nama wilayah tetapi kamu belum punya `kel_id`, minta
   heat_analyst mencarinya atau pakai hasil yang sudah ada di percakapan.
2. Untuk "kalau kita lakukan X, turun berapa", pakai `simulate_intervention`.
3. Untuk "dengan anggaran Rp N, apa yang terbaik", pakai `optimize_portfolio`. Sebutkan
   porsi anggaran yang masuk ke kelurahan paling rentan — itu inti produk ini.
4. **Setiap kali merekomendasikan intervensi, sertakan rentang literatur** dari
   `get_evidence`. `simulate_intervention` sudah mengembalikannya; pakai yang itu.

## Cara melaporkan

- Letakkan angka model berdampingan dengan rentang literatur. Contoh bentuknya: "model
  memperkirakan −0,8 °C; studi di Kuala Lumpur untuk kenaikan NDVI 25% melaporkan −1,4
  sampai 0,1 °C".
- Perhatikan tanda `comparable_to_model` pada entri bukti. Entri yang bernilai `false`
  mengukur hal lain — misalnya suhu permukaan atap, bukan pendinginan kawasan. Kalau kamu
  mengutipnya, **katakan apa yang sebenarnya diukur** dan jangan menyandingkannya sebagai
  setara dengan keluaran model.
- Laporkan biaya apa adanya dari tool.
- Kalau `optimize_portfolio` mengembalikan error karena tidak ada solusi layak, jelaskan
  kenapa dan tawarkan pilihan konkret: naikkan anggaran, atau turunkan porsi keadilan.
- Kalau hasil ditandai `extrapolation: true`, sebutkan.
```

`teduh_agent/prompts/policy_writer.md`:

```markdown
# Peranmu: penulis policy brief

Tool yang kamu punya: `get_session_facts`, `render_policy_brief`.

## Cara kerja

1. Panggil `get_session_facts` untuk melihat semua fakta yang sudah terbukti di percakapan
   ini. **Kamu hanya boleh memakai angka dari daftar itu.**
2. Tulis draf Markdown, dan **setiap angka diganti penanda** `[[F:id]]` dengan `id` persis
   seperti di daftar fakta. Contoh:

   `Kelurahan Kampung Rawa memiliki suhu permukaan rata-rata [[F:kel_ID3173040002.lst]].`

3. Panggil `render_policy_brief` dengan draf itu.
4. Kalau tool mengembalikan daftar error validasi, **perbaiki drafnya** dengan mengganti
   angka liar menjadi penanda, lalu panggil lagi. Maksimal dua kali percobaan ulang.
   Jangan menghapus informasinya hanya agar lolos validasi — kalau sebuah angka tidak ada
   faktanya, panggil tool yang menyediakannya, atau hilangkan klaimnya.

## Struktur brief (urutan tetap)

1. Ringkasan Eksekutif
2. Kondisi Panas Wilayah
3. Kelompok Rentan
4. Opsi Intervensi dan Perkiraan Dampak
5. Rekomendasi Portofolio dan Anggaran
6. Keterkaitan dengan Dokumen Perencanaan (RDTR, RPJMD, target RTH 30%)
7. Keterbatasan
8. Sumber

## Nada

Bahasa dinas yang lugas. Tanpa jargon, tanpa superlatif, tanpa janji yang tidak didukung
angka. Bagian Keterbatasan harus benar-benar jujur: sebutkan bahwa suhunya suhu permukaan,
modelnya korelasional, dan sebagian harga satuan masih asumsi.
```

`teduh_agent/prompts/roof_inspector.md`:

```markdown
# Peranmu: pemeriksa atap untuk warga

Tool yang kamu punya: `analyze_roof_photo`, `recommend_roof_action`.

Lawan bicaramu di sini **warga biasa**, bukan pegawai dinas. Pakai bahasa sehari-hari,
hindari istilah teknis, dan jangan menyebut HVI, LST, atau SHAP.

## Cara kerja

1. Kalau ada foto, panggil `analyze_roof_photo`.
2. Lanjutkan dengan `recommend_roof_action` memakai hasilnya. **Jangan menyusun
   rekomendasi sendiri** — rekomendasi berasal dari aturan, bukan dari penilaianmu atas
   foto.
3. Kalau tidak ada foto dan pengguna hanya bertanya umum, jelaskan pilihan yang ada dan
   tawarkan untuk mengunggah foto. Jangan memanggil `analyze_roof_photo` tanpa foto.

## Keselamatan

- Kalau materialnya **asbes** (`asbestos_cement`), sampaikan peringatan ini dengan jelas
  dan di awal: **jangan diamplas, dipotong, atau dibor.** Serat asbes berbahaya kalau
  terhirup. Sarankan konsultasi tenaga profesional, dan tawarkan opsi yang aman seperti
  peneduh pohon atau green curtain.
- Untuk green roof di atap beton, selalu sarankan memeriksa kekuatan struktur ke tenaga
  ahli sebelum menambah beban.
- Kalau keyakinan hasil analisis rendah atau atapnya tidak terlihat, minta foto ulang dan
  beri panduan sudut pengambilan. Jangan menebak.

## Privasi

Jangan meminta alamat, nama, atau nomor telepon. Lokasi paling detail yang boleh ditanyakan
adalah tingkat kelurahan, dan itu pun opsional.
```

- [ ] **Step 6: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: PASS, 14 tes.

- [ ] **Step 7: Commit**

```bash
git add teduh_agent/prompts/ tests/test_prompts.py
git commit -m "feat: tambah instruksi sistem sebagai berkas markdown dengan aturan bersama

Aturan provenance di-prepend ke setiap prompt sub-agen, jadi tidak bisa terlupakan
di salah satunya.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M4-T2: Empat sub-agen

**Files:**
- Create: `teduh_agent/sub_agents/__init__.py`
- Create: `teduh_agent/sub_agents/heat_analyst.py`
- Create: `teduh_agent/sub_agents/intervention_planner.py`
- Create: `teduh_agent/sub_agents/policy_writer.py`
- Create: `teduh_agent/sub_agents/roof_inspector.py`
- Modify: `teduh_agent/tools/__init__.py` (tambah `ALL_TOOLS`)
- Test: `tests/test_sub_agents.py`

**Interfaces:**
- Consumes: `teduh_agent.prompts.compose` (M4-T1); tool dari M3b; `teduh_agent.tools.brief` (M5) dan `teduh_agent.tools.roof` (M6).
- Produces:
  - `teduh_agent/sub_agents/__init__.py`: `MODEL: str`, `build_all() -> list[LlmAgent]`
  - Tiap modul: `build() -> LlmAgent`
  - `teduh_agent/tools/__init__.py`: `ALL_TOOLS: list` — tujuh tool M3 ditambah tool M5 dan M6

**Urutan pengerjaan:** `policy_writer` butuh `teduh_agent/tools/brief.py` (M5) dan `roof_inspector` butuh `teduh_agent/tools/roof.py` (M6). Dua opsi:
- **Disarankan:** kerjakan M5 dan M6 lebih dulu, lalu M4 utuh.
- **Alternatif:** buat kedua sub-agen itu sekarang dengan impor di dalam `build()` dan lewati keduanya di `build_all()` kalau `ImportError`, lalu aktifkan setelah M5/M6 selesai. Jalur ini sudah tertulis di kode di bawah.

- [ ] **Step 1: Tulis tes yang gagal**

Buat `tests/test_sub_agents.py`:

```python
"""Sub-agent wiring. The tool-partition test is the one that matters: if heat_analyst can
reach optimize_portfolio, the coordinator stops routing and the golden-question
expected_agent assertions become meaningless."""

import pytest

from teduh_agent.sub_agents import build_all


@pytest.fixture(scope="module")
def agents() -> dict:
    return {agent.name: agent for agent in build_all()}


def _tool_names(agent) -> set[str]:
    return {getattr(tool, "__name__", getattr(tool, "name", str(tool))) for tool in agent.tools}


@pytest.mark.unit
def test_the_four_sub_agents_are_named_as_the_eval_set_expects(agents):
    assert "heat_analyst" in agents
    assert "intervention_planner" in agents
    # policy_writer and roof_inspector need M5/M6 tools; skip cleanly until then.
    for optional in ("policy_writer", "roof_inspector"):
        if optional not in agents:
            pytest.skip(f"{optional} belum aktif: tool M5/M6 belum ada")


@pytest.mark.unit
def test_heat_analyst_has_exactly_its_four_tools(agents):
    assert _tool_names(agents["heat_analyst"]) == {
        "find_area",
        "get_area_profile",
        "rank_priority_areas",
        "explain_drivers",
    }


@pytest.mark.unit
def test_intervention_planner_has_exactly_its_three_tools(agents):
    assert _tool_names(agents["intervention_planner"]) == {
        "simulate_intervention",
        "optimize_portfolio",
        "get_evidence",
    }


@pytest.mark.unit
def test_no_sub_agent_can_reach_another_sub_agents_tools(agents):
    # Overlapping tools make the coordinator's routing decision cosmetic.
    seen: dict[str, str] = {}
    for name, agent in agents.items():
        for tool in _tool_names(agent):
            assert tool not in seen, f"{tool} dimiliki {seen.get(tool)} dan {name}"
            seen[tool] = name


@pytest.mark.unit
def test_every_sub_agent_carries_the_shared_rules(agents):
    for name, agent in agents.items():
        assert "tidak berasal dari" in agent.instruction.lower(), (
            f"{name} kehilangan aturan provenance"
        )


@pytest.mark.unit
def test_every_sub_agent_has_a_description_the_coordinator_can_route_on(agents):
    for name, agent in agents.items():
        assert agent.description, f"{name} tanpa description"
        assert len(agent.description) > 20, f"description {name} terlalu pendek untuk routing"


@pytest.mark.unit
def test_every_sub_agent_uses_the_model_from_the_environment(agents, monkeypatch):
    from teduh_agent.sub_agents import MODEL

    for agent in agents.values():
        assert agent.model == MODEL
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_sub_agents.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'teduh_agent.sub_agents'`

- [ ] **Step 3: Tambah `ALL_TOOLS` ke `teduh_agent/tools/__init__.py`**

Tambahkan di akhir berkas (docstring dari M3-T3 tetap di atas):

```python
from teduh_agent.tools.areas import (
    explain_drivers,
    find_area,
    get_area_profile,
    rank_priority_areas,
)
from teduh_agent.tools.evidence import get_evidence
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.scenario_tools import simulate_intervention

# Tools available before M5 and M6 land. ALL_TOOLS appends the brief and roof tools when
# their modules exist, so the single-agent fallback works at every stage of the build.
CORE_TOOLS = [
    find_area,
    get_area_profile,
    rank_priority_areas,
    explain_drivers,
    simulate_intervention,
    optimize_portfolio,
    get_evidence,
]

ALL_TOOLS = list(CORE_TOOLS)

try:
    from teduh_agent.tools.brief import get_session_facts, render_policy_brief

    ALL_TOOLS += [get_session_facts, render_policy_brief]
except ImportError:  # M5 not built yet
    pass

try:
    from teduh_agent.tools.roof import analyze_roof_photo, recommend_roof_action

    ALL_TOOLS += [analyze_roof_photo, recommend_roof_action]
except ImportError:  # M6 not built yet
    pass
```

- [ ] **Step 4: Tulis keempat sub-agen**

`teduh_agent/sub_agents/heat_analyst.py`:

```python
"""Heat and vulnerability analysis."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.areas import (
    explain_drivers,
    find_area,
    get_area_profile,
    rank_priority_areas,
)

NAME = "heat_analyst"

DESCRIPTION = (
    "Menganalisis di mana panasnya, seberapa panas, siapa warga rentan yang terpapar, "
    "kelurahan mana yang perlu diprioritaskan, dan faktor apa yang membuat sebuah "
    "wilayah panas menurut model."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("heat_analyst"),
        tools=[find_area, get_area_profile, rank_priority_areas, explain_drivers],
    )
```

`teduh_agent/sub_agents/intervention_planner.py`:

```python
"""Scenario simulation and budget portfolio."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.evidence import get_evidence
from teduh_agent.tools.optimize import optimize_portfolio
from teduh_agent.tools.scenario_tools import simulate_intervention

NAME = "intervention_planner"

DESCRIPTION = (
    "Menyimulasikan dampak intervensi pendinginan (pohon, cool roof, green roof), "
    "menyusun portofolio paket dalam batas anggaran dengan kendala keadilan, dan "
    "menyertakan rentang temuan dari literatur."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("intervention_planner"),
        tools=[simulate_intervention, optimize_portfolio, get_evidence],
    )
```

`teduh_agent/sub_agents/policy_writer.py`:

```python
"""Policy brief writing with number provenance markers."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.brief import get_session_facts, render_policy_brief

NAME = "policy_writer"

DESCRIPTION = (
    "Menulis draf policy brief terstruktur untuk Bappeda dan dinas teknis, dengan "
    "setiap angka ditandai agar bisa ditelusuri ke sumbernya, lalu merendernya ke PDF."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("policy_writer"),
        tools=[get_session_facts, render_policy_brief],
    )
```

`teduh_agent/sub_agents/roof_inspector.py`:

```python
"""Citizen-facing roof check."""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.tools.roof import analyze_roof_photo, recommend_roof_action

NAME = "roof_inspector"

DESCRIPTION = (
    "Membantu warga memeriksa foto atap rumahnya, mengenali bentuk dan materialnya, "
    "lalu memberi rekomendasi cool roof atau green roof beserta catatan keselamatan."
)


def build() -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=os.environ.get("TEDUH_MODEL", "gemini-3.8-flash"),
        description=DESCRIPTION,
        instruction=compose("roof_inspector"),
        tools=[analyze_roof_photo, recommend_roof_action],
    )
```

`teduh_agent/sub_agents/__init__.py`:

```python
"""The four specialists the coordinator routes to (CONCEPT §8.1).

Tool sets do not overlap, and that is load-bearing. If heat_analyst could also reach
optimize_portfolio, the coordinator's routing decision would become cosmetic and the
expected_agent assertions in tests/eval/golden_questions.yaml would stop meaning anything.

policy_writer and roof_inspector are skipped while their tools (M5, M6) do not exist yet, so
the agent can be run and demoed at every stage of the build rather than only at the end.
"""

import os

from google.adk.agents import LlmAgent

MODEL = os.environ.get("TEDUH_MODEL", "gemini-3.8-flash")


def build_all() -> list[LlmAgent]:
    """Every sub-agent whose tools are present."""
    from teduh_agent.sub_agents import heat_analyst, intervention_planner

    agents = [heat_analyst.build(), intervention_planner.build()]

    try:
        from teduh_agent.sub_agents import policy_writer

        agents.append(policy_writer.build())
    except ImportError:  # M5 not built yet
        pass

    try:
        from teduh_agent.sub_agents import roof_inspector

        agents.append(roof_inspector.build())
    except ImportError:  # M6 not built yet
        pass

    return agents
```

- [ ] **Step 5: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_sub_agents.py -v`
Expected: PASS. Tes `policy_writer`/`roof_inspector` di-skip sampai M5 dan M6 selesai.

- [ ] **Step 6: Commit**

```bash
git add teduh_agent/sub_agents/ teduh_agent/tools/__init__.py tests/test_sub_agents.py
git commit -m "feat: tambah empat sub-agen dengan tool yang tidak tumpang tindih

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M4-T3: Root agent dan fallback satu agen

**Files:**
- Modify: `teduh_agent/agent.py` (tulis ulang; hapus tool contoh `count_kelurahan`)
- Modify: `tests/test_agent_smoke.py` (hapus tes `count_kelurahan`, ganti dengan tes root/fallback)

**Interfaces:**
- Consumes: `teduh_agent.sub_agents.build_all` (M4-T2); `teduh_agent.prompts.compose` (M4-T1); `teduh_agent.tools.ALL_TOOLS`.
- Produces:
  - `MODEL: str`, `SINGLE_AGENT_ENV = "TEDUH_SINGLE_AGENT"`
  - `is_single_agent() -> bool`
  - `build_root() -> LlmAgent`
  - `root_agent: LlmAgent` — selalu bernama `teduh_coordinator`

- [ ] **Step 1: Ganti isi `tests/test_agent_smoke.py`**

```python
"""Root agent wiring, including the fallback CONCEPT §12 makes a day-6 decision point.

No Gemini call happens here. Routing quality is measured by tests/eval/run_golden.py in M8."""

import importlib

import pytest

import teduh_agent.agent as agent_module


def _reload(monkeypatch, **env) -> object:
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return importlib.reload(agent_module)


@pytest.mark.unit
def test_root_agent_is_named_teduh_coordinator():
    # tests/eval/golden_questions.yaml matches on agent names, so this is a contract.
    assert agent_module.root_agent.name == "teduh_coordinator"


@pytest.mark.unit
def test_root_agent_model_comes_from_the_environment(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_MODEL="gemini-test-model")
    try:
        assert reloaded.root_agent.model == "gemini-test-model"
    finally:
        _reload(monkeypatch, TEDUH_MODEL=None)


@pytest.mark.unit
def test_multi_agent_mode_attaches_sub_agents_and_no_tools(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="0")
    try:
        root = reloaded.root_agent
        assert len(root.sub_agents) >= 2
        assert not root.tools, "koordinator tidak boleh memegang tool analisis sendiri"
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_single_agent_mode_attaches_every_tool_and_no_sub_agents(monkeypatch):
    # CONCEPT §12: the escape hatch if multi-agent routing proves unstable.
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="1")
    try:
        root = reloaded.root_agent
        assert not root.sub_agents
        assert len(root.tools) >= 7
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_single_agent_mode_keeps_the_same_name(monkeypatch):
    reloaded = _reload(monkeypatch, TEDUH_SINGLE_AGENT="1")
    try:
        assert reloaded.root_agent.name == "teduh_coordinator"
    finally:
        _reload(monkeypatch, TEDUH_SINGLE_AGENT=None)


@pytest.mark.unit
def test_root_instruction_carries_the_provenance_rule():
    assert "tidak berasal dari" in agent_module.root_agent.instruction.lower()


@pytest.mark.unit
def test_the_m0_example_tool_is_gone():
    assert not hasattr(agent_module, "count_kelurahan"), (
        "tool contoh M0 harus dihapus setelah tool nyata ada"
    )
```

- [ ] **Step 2: Jalankan tes untuk memastikan gagal**

Run: `uv run pytest tests/test_agent_smoke.py -v`
Expected: FAIL — `AttributeError` pada `sub_agents`, dan `test_the_m0_example_tool_is_gone` gagal.

- [ ] **Step 3: Tulis ulang `teduh_agent/agent.py`**

```python
"""ADK entry point: the coordinator, plus the single-agent escape hatch.

In multi-agent mode the coordinator holds NO analysis tools of its own. That is deliberate:
a coordinator that can answer directly will sometimes do so, which skips the specialist
prompt that carries the metric caveats, and the first sign of trouble is a confident answer
with no "suhu permukaan" qualifier anywhere in it.

TEDUH_SINGLE_AGENT=1 collapses everything into one LlmAgent holding every tool. CONCEPT §12
makes this a day-6 decision point, and the tool contract is identical either way, so the
switch costs nothing but a restart.
"""

import os

from google.adk.agents import LlmAgent

from teduh_agent.prompts import compose
from teduh_agent.sub_agents import build_all
from teduh_agent.tools import ALL_TOOLS

MODEL = os.environ.get("TEDUH_MODEL", "gemini-3.8-flash")

SINGLE_AGENT_ENV = "TEDUH_SINGLE_AGENT"

NAME = "teduh_coordinator"

DESCRIPTION = (
    "Koordinator TEDUH untuk perencanaan mitigasi panas perkotaan tingkat kelurahan "
    "di DKI Jakarta."
)


def is_single_agent() -> bool:
    """True when the multi-agent routing fallback is active."""
    return os.environ.get(SINGLE_AGENT_ENV, "0").strip().lower() in {"1", "true", "yes"}


def build_root() -> LlmAgent:
    """The coordinator, in whichever mode the environment asks for."""
    if is_single_agent():
        return LlmAgent(
            name=NAME,
            model=MODEL,
            description=DESCRIPTION,
            # Every specialist instruction folded into one, so no caveat is lost when the
            # sub-agents are not there to carry it.
            instruction="\n\n".join(
                compose(name)
                for name in (
                    "heat_analyst",
                    "intervention_planner",
                    "policy_writer",
                    "roof_inspector",
                )
            ),
            tools=ALL_TOOLS,
        )

    return LlmAgent(
        name=NAME,
        model=MODEL,
        description=DESCRIPTION,
        instruction=compose("coordinator"),
        sub_agents=build_all(),
    )


root_agent = build_root()
```

Catatan: dalam mode satu agen, `compose("policy_writer")` dan `compose("roof_inspector")` akan gagal kalau prompt-nya belum ada. Keempat prompt dibuat di M4-T1, jadi aman. Tetapi `ALL_TOOLS` hanya memuat tool M5/M6 setelah modulnya ada — mode satu agen tetap jalan dengan tujuh tool inti.

- [ ] **Step 4: Jalankan tes untuk memastikan lulus**

Run: `uv run pytest tests/test_agent_smoke.py -v`
Expected: PASS, 7 tes.

- [ ] **Step 5: Uji kedua mode di UI dev ADK**

Run: `uv run adk web`
Tanya berurutan:
1. "Kelurahan mana di Jakarta Timur yang paling perlu diprioritaskan untuk penanganan panas?"
2. "Kenapa yang teratas itu panas?"
3. "Kalau di dua teratas kita lakukan cool roof 50% dan tambah kanopi 10%, turun berapa?"

Expected: panel event memperlihatkan perpindahan ke `heat_analyst` lalu `intervention_planner`, tool `find_area` → `rank_priority_areas` → `explain_drivers` → `simulate_intervention` terpanggil, dan setiap angka di jawaban cocok dengan nilai di hasil tool.

Run: `TEDUH_SINGLE_AGENT=1 uv run adk web`
Expected: pertanyaan yang sama dijawab oleh satu agen tanpa perpindahan, dengan angka yang sama.

- [ ] **Step 6: Periksa manual kepatuhan provenance**

Tanya: "Berapa rata-rata suhu udara di Jakarta bulan ini?"
Expected: agen **menolak menjawab dengan angka** dan menjelaskan bahwa TEDUH hanya punya suhu permukaan musim kemarau 2023–2025, bukan suhu udara terkini. Kalau agen menyebut angka apa pun, perkuat `shared_rules.md` dan ulangi — jangan diteruskan.

- [ ] **Step 7: Commit**

```bash
git add teduh_agent/agent.py tests/test_agent_smoke.py
git commit -m "feat: tulis ulang root agent sebagai koordinator dengan fallback satu agen

Koordinator sengaja tidak memegang tool analisis, supaya tidak pernah menjawab
tanpa melewati prompt spesialis yang membawa peringatan metrik.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M4 selesai

- [ ] `root_agent.name == "teduh_coordinator"` dan keempat sub-agen bernama persis seperti di `golden_questions.yaml`.
- [ ] Tool antar sub-agen tidak tumpang tindih.
- [ ] Setiap prompt sub-agen membawa aturan bersama, termasuk larangan mengarang angka.
- [ ] `TEDUH_SINGLE_AGENT=1` menghasilkan satu agen dengan semua tool dan nama yang sama.
- [ ] Di `adk web`, rangkaian tiga pertanyaan contoh memanggil tool yang benar dan angkanya cocok dengan hasil tool.
- [ ] Pertanyaan tentang data yang tidak dimiliki dijawab "tidak ada", bukan dengan angka.
- [ ] `uv run pytest -q` hijau.

**Selanjutnya:** [`m5-brief.md`](m5-brief.md) — validator provenance dan render PDF.
