# M8 — Evaluasi dan Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Baca `docs/superpowers/plans/README.md` bagian **Global Constraints** dan **Interface Registry**. Prasyarat: **M0–M7 selesai**.

**Goal:** Mengukur yang dijanjikan CONCEPT §13 dengan angka sebenarnya, lalu menerbitkan dua URL publik yang bisa dibuka juri tanpa login.

**Architecture:** Dua runner evaluasi berdiri di luar `pytest` dan dijalankan manual, karena keduanya memanggil Gemini sungguhan — memasukkannya ke suite tes akan membuat `uv run pytest` berbiaya dan tidak deterministik. Keduanya menulis laporan JSON sehingga hasilnya bisa dikutip di proposal tanpa menjalankan ulang.

**Tech Stack:** `google.adk.runners.Runner`, `InMemorySessionService`, gcloud, Firebase App Hosting.

## Global Constraints

- **Jangan mengubah `golden_questions.yaml` agar lulus.** Kalau agen salah pilih tool, perbaiki prompt atau deskripsi tool.
- **Jangan mengklaim angka yang belum diukur.** Akurasi Cek Atap tidak boleh disebut di proposal, video, atau brief sampai 30 foto terlabeli benar-benar dievaluasi.
- R² yang dikutip di mana pun harus sama dengan `data/model/model_card.json`.
- Foto atap tidak di-commit (CLAUDE.md aturan 8). Hanya `labels.csv` dan laporan agregat.
- URL prototipe harus bisa dibuka **tanpa login** (CONCEPT §16).
- `min-instances=1` selama periode penilaian 19 Okt – 6 Nov (CONCEPT §14).
- Commit conventional, diakhiri `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

### Target CONCEPT §13 yang diukur di sini

| Aspek | Target | Diukur oleh |
|---|---|---|
| Pemilihan tool | ≥ 90% benar dari 20 pertanyaan | `tests/eval/run_golden.py` |
| Provenance | 100% brief lolos validator | `run_golden.py` (pertanyaan brief) + `tests/test_provenance.py` |
| Cek Atap | `roof_form` ≥ 85%, `material` ≥ 70% | `tests/eval/eval_roof.py` |
| Latensi | p50 < 8 detik | `run_golden.py` melaporkan p50 dan p95 |
| Model panas | R² ≥ 0,75 spatial CV | sudah diukur di M2, dikutip dari model card |
| Arah fisika & optimasi | 100% lulus | sudah dijamin `pytest` di M3 |

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `tests/eval/run_golden.py` | Jalankan 20 pertanyaan, bandingkan tool yang terpanggil, laporkan skor dan latensi. |
| `tests/eval/eval_roof.py` | Hitung akurasi `roof_form` dan `material` terhadap `labels.csv`. |
| `infra/firebase.json` | Konfigurasi Firebase App Hosting untuk `teduh-web`. |
| `infra/deploy_web.sh` | Build dan deploy frontend, menyuntikkan URL API. |
| `docs/SUBMISSION.md` | Checklist submission dengan angka sebenarnya dan tautan final. |

---

## Task M8-T1: Runner golden questions

**Files:**
- Create: `tests/eval/__init__.py`
- Create: `tests/eval/run_golden.py`
- Output: `tests/eval/reports/golden_<timestamp>.json` (di-gitignore kecuali laporan final)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `teduh_agent.agent.root_agent`; `tests/eval/golden_questions.yaml` (20 entri dengan `id`, `question`, `expected_agent`, `expected_tools`, opsional `forbidden_tools`, `allow_extra`, `notes`).
- Produces:
  - `GOLDEN_PATH`, `REPORT_DIR`, `TOOL_ACCURACY_TARGET = 0.9`, `LATENCY_P50_TARGET_S = 8.0`
  - `Outcome` — frozen dataclass `(id, question, expected_tools, called_tools, forbidden_hit, allow_extra, passed, reason, elapsed_s, agents)`
  - `load_questions() -> list[dict]`
  - `run_one(runner, question: dict, index: int) -> Outcome`
  - `score(outcomes: list[Outcome]) -> dict`
  - `main()`, `check(summary: dict) -> None`

- [ ] **Step 1: Verifikasi API Runner ADK yang terpasang**

Signature `Runner` dan bentuk event berubah antar rilis. Periksa dulu:

```bash
uv run python -c "
import inspect
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
print('Runner  :', inspect.signature(Runner.__init__))
print('run_async:', inspect.signature(Runner.run_async))
print('sessions :', [m for m in dir(InMemorySessionService) if not m.startswith('_')])
"
```

Sesuaikan `run_one` di Step 3 dengan hasilnya. Yang dibutuhkan dari tiap event: bagian `content.parts` yang memuat `function_call` (nama tool) dan `function_response`, plus `event.author` untuk mencatat sub-agen yang menjawab.

- [ ] **Step 2: Tambahkan laporan ke `.gitignore`**

```gitignore
# Laporan evaluasi per-jalan. Laporan final yang dikutip di proposal dipaksa commit
# dengan `git add -f`.
tests/eval/reports/
```

- [ ] **Step 3: Tulis `tests/eval/run_golden.py`**

```python
"""Measure tool selection against tests/eval/golden_questions.yaml (CONCEPT §13, >= 90%).

Deliberately NOT a pytest test. Each question is a real Gemini call, so putting these in the
suite would make `uv run pytest` cost money, take minutes, and fail intermittently for
reasons unrelated to the code under change.

What is graded is which TOOLS the agent reached for, not the prose it produced. Prose is
judged separately by the provenance validator. That split matters: an answer can be
beautifully worded and still be wrong because it never consulted the data, and that is
exactly the failure this project exists to prevent.

Run: uv run python -m tests.eval.run_golden
Output: tests/eval/reports/golden_<timestamp>.json
"""

import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from teduh_agent.agent import root_agent

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "tests" / "eval" / "golden_questions.yaml"
REPORT_DIR = ROOT / "tests" / "eval" / "reports"

APP_NAME = "teduh_agent"
USER_ID = "eval"

# CONCEPT §13.
TOOL_ACCURACY_TARGET = 0.9
LATENCY_P50_TARGET_S = 8.0

# A question that hangs would otherwise stall the whole run.
PER_QUESTION_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class Outcome:
    id: str
    question: str
    expected_tools: list[str]
    called_tools: list[str]
    forbidden_hit: list[str]
    allow_extra: bool
    passed: bool
    reason: str
    elapsed_s: float
    agents: list[str]


def load_questions() -> list[dict]:
    questions = yaml.safe_load(GOLDEN_PATH.read_text())
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{GOLDEN_PATH} tidak memuat daftar pertanyaan")
    return questions


def _tools_and_agents(event) -> tuple[list[str], str | None]:
    """Extract tool names called in one event, plus the agent that authored it."""
    tools: list[str] = []
    content = getattr(event, "content", None)
    for part in getattr(content, "parts", None) or []:
        call = getattr(part, "function_call", None)
        if call is not None and getattr(call, "name", None):
            tools.append(call.name)
    return tools, getattr(event, "author", None)


async def _ask(runner: Runner, session_id: str, question: str) -> tuple[list[str], list[str]]:
    called: list[str] = []
    agents: list[str] = []
    message = types.Content(role="user", parts=[types.Part(text=question)])

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        tools, author = _tools_and_agents(event)
        called.extend(tools)
        if author and author not in agents:
            agents.append(author)
    return called, agents


def run_one(runner: Runner, question: dict, index: int) -> Outcome:
    """Ask one question in a fresh session and grade the tools it reached for."""
    session_id = f"golden-{index}"
    asyncio.run(
        runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
    )

    expected = list(question.get("expected_tools") or [])
    forbidden = list(question.get("forbidden_tools") or [])
    allow_extra = bool(question.get("allow_extra", True))

    started = time.perf_counter()
    try:
        called, agents = asyncio.run(
            asyncio.wait_for(
                _ask(runner, session_id, question["question"]),
                timeout=PER_QUESTION_TIMEOUT_S,
            )
        )
    except TimeoutError:
        return Outcome(
            id=question["id"],
            question=question["question"],
            expected_tools=expected,
            called_tools=[],
            forbidden_hit=[],
            allow_extra=allow_extra,
            passed=False,
            reason=f"waktu habis setelah {PER_QUESTION_TIMEOUT_S:.0f} detik",
            elapsed_s=time.perf_counter() - started,
            agents=[],
        )
    elapsed = time.perf_counter() - started

    called_set = set(called)
    missing = [tool for tool in expected if tool not in called_set]
    forbidden_hit = [tool for tool in forbidden if tool in called_set]
    extra = [tool for tool in called_set if tool not in expected]

    reasons: list[str] = []
    if missing:
        reasons.append(f"tool wajib tidak dipanggil: {', '.join(missing)}")
    if forbidden_hit:
        reasons.append(f"tool terlarang dipanggil: {', '.join(forbidden_hit)}")
    if not allow_extra and extra:
        reasons.append(f"tool di luar rute yang benar: {', '.join(sorted(extra))}")

    return Outcome(
        id=question["id"],
        question=question["question"],
        expected_tools=expected,
        called_tools=called,
        forbidden_hit=forbidden_hit,
        allow_extra=allow_extra,
        passed=not reasons,
        reason="; ".join(reasons) or "ok",
        elapsed_s=elapsed,
        agents=agents,
    )


def score(outcomes: list[Outcome]) -> dict:
    latencies = sorted(outcome.elapsed_s for outcome in outcomes)
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return {
        "n_questions": len(outcomes),
        "n_passed": passed,
        "tool_accuracy": passed / len(outcomes) if outcomes else 0.0,
        "latency_p50_s": statistics.median(latencies) if latencies else 0.0,
        "latency_p95_s": latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0,
        "latency_max_s": latencies[-1] if latencies else 0.0,
        "targets": {
            "tool_accuracy": TOOL_ACCURACY_TARGET,
            "latency_p50_s": LATENCY_P50_TARGET_S,
        },
    }


def main() -> None:
    questions = load_questions()
    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=InMemorySessionService()
    )
    print(f"evaluasi    : {len(questions)} pertanyaan terhadap {root_agent.name}")

    outcomes: list[Outcome] = []
    for index, question in enumerate(questions):
        outcome = run_one(runner, question, index)
        outcomes.append(outcome)
        mark = "OK  " if outcome.passed else "GAGAL"
        print(
            f"  {mark} {outcome.id}  {outcome.elapsed_s:5.1f}s  "
            f"[{', '.join(outcome.called_tools) or '-'}]"
        )
        if not outcome.passed:
            print(f"        {outcome.reason}")

    summary = score(outcomes)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = REPORT_DIR / f"golden_{stamp}.json"
    report.write_text(
        json.dumps(
            {
                "run_at": datetime.now(UTC).isoformat(),
                "agent": root_agent.name,
                "summary": summary,
                "outcomes": [asdict(outcome) for outcome in outcomes],
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        f"\nakurasi tool: {summary['n_passed']}/{summary['n_questions']} = "
        f"{summary['tool_accuracy']:.1%} (target {TOOL_ACCURACY_TARGET:.0%})"
    )
    print(
        f"latensi     : p50 {summary['latency_p50_s']:.1f}s · "
        f"p95 {summary['latency_p95_s']:.1f}s · maks {summary['latency_max_s']:.1f}s "
        f"(target p50 < {LATENCY_P50_TARGET_S:.0f}s)"
    )
    print(f"laporan     : {report.relative_to(ROOT)}")

    check(summary)


def check(summary: dict) -> None:
    """Report honestly against the targets. Never adjust the eval set to pass."""
    if summary["tool_accuracy"] < TOOL_ACCURACY_TARGET:
        print(
            f"\nPERINGATAN: akurasi pemilihan tool {summary['tool_accuracy']:.1%} di bawah "
            f"target {TOOL_ACCURACY_TARGET:.0%}. Perbaiki prompt sistem atau deskripsi tool. "
            "JANGAN mengubah golden_questions.yaml agar lulus, dan JANGAN mengklaim 90% "
            "di proposal."
        )
    if summary["latency_p50_s"] > LATENCY_P50_TARGET_S:
        print(
            f"PERINGATAN: p50 {summary['latency_p50_s']:.1f}s melewati target "
            f"{LATENCY_P50_TARGET_S:.0f}s. Periksa cache store dan jumlah tool call per jawaban."
        )
    assert summary["n_questions"] == 20, (
        f"{summary['n_questions']} pertanyaan dievaluasi, CONCEPT §13 menyebut 20"
    )
    print("check ok")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Jalankan evaluasi**

Run: `uv run python -m tests.eval.run_golden`
Expected: 20 baris hasil, akurasi dan latensi tercetak, laporan JSON terbentuk.

Catat hasil sebenarnya: akurasi tool `_____%`, p50 `_____ s`.

- [ ] **Step 5: Perbaiki kegagalan di tempat yang benar**

Untuk setiap pertanyaan yang gagal, baca `reason` lalu perbaiki **salah satu** dari:
- **Tool wajib tidak dipanggil** → perjelas kapan tool itu dipakai di `teduh_agent/prompts/<sub_agent>.md`, atau perjelas docstring tool.
- **Tool terlarang dipanggil** → tambahkan larangan eksplisit di prompt sub-agen terkait. Contoh: `q` yang melarang `analyze_roof_photo` gagal kalau agen memanggilnya tanpa foto; prompt `roof_inspector.md` sudah memuat aturan itu, jadi perkuat kalimatnya.
- **Rute salah sub-agen** → perbaiki `DESCRIPTION` sub-agen di `teduh_agent/sub_agents/*.py`; itulah yang dipakai koordinator untuk routing.

Jalankan ulang setelah tiap perubahan. **Jangan** menyentuh `golden_questions.yaml`.

Kalau akurasi tetap di bawah 90% setelah dua putaran perbaikan prompt, jalankan dengan `TEDUH_SINGLE_AGENT=1` dan bandingkan:

```bash
TEDUH_SINGLE_AGENT=1 uv run python -m tests.eval.run_golden
```

Kalau mode satu agen lebih baik, pakai itu untuk demo — CONCEPT §12 memang menjadikannya titik keputusan, dan kontrak tool tidak berubah. Catat keputusannya di `docs/DECISIONS.md`.

- [ ] **Step 6: Commit laporan final**

```bash
git add -f tests/eval/reports/golden_*.json
git add tests/eval/__init__.py tests/eval/run_golden.py .gitignore
git commit -m "test: tambah runner evaluasi 20 golden questions

Menilai tool yang dipanggil, bukan prosanya: jawaban bisa terdengar bagus dan tetap
salah karena tidak pernah menyentuh data.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M8-T2: Evaluasi Cek Atap

**Files:**
- Create: `tests/eval/eval_roof.py`
- Output: `tests/eval/reports/roof_<timestamp>.json`

**Interfaces:**
- Consumes: `teduh_agent.tools.roof.analyze_roof_bytes` (M6-T1); `data/roof_test/labels.csv`; foto di `data/roof_test/photos/` (di-gitignore).
- Produces:
  - `LABELS_PATH`, `PHOTO_DIR`, `TARGETS = {"roof_form": 0.85, "material": 0.70}`, `MIN_PHOTOS = 30`
  - `load_labels() -> list[dict]` — membuang baris `is_placeholder == "true"`
  - `evaluate(labels: list[dict]) -> list[dict]`
  - `accuracy(results: list[dict], field: str) -> float`
  - `confusion(results: list[dict], field: str) -> dict[str, dict[str, int]]`
  - `main()`, `check(results: list[dict]) -> None`

**Status saat ini: 0 dari 30 foto tim.** Skrip ini **harus menolak melaporkan akurasi** di bawah 30 foto, karena akurasi dari 5 foto bukan bukti dan angkanya akan terbawa ke proposal.

- [ ] **Step 1: Tulis `tests/eval/eval_roof.py`**

```python
"""Measure Cek Atap accuracy against the hand-labelled set (CONCEPT §13).

Refuses to report accuracy below MIN_PHOTOS on purpose. An accuracy figure computed from
five photos is not evidence, and once it is printed it tends to end up in a proposal. The
labels file currently has zero team photos, so this script exists to be run AFTER the set is
collected, not to produce a number now.

Photos are never committed (CLAUDE.md rule 8). Only labels.csv and the aggregate report are.

Run: uv run python -m tests.eval.eval_roof
Output: tests/eval/reports/roof_<timestamp>.json
"""

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from teduh_agent.tools.roof import analyze_roof_bytes

ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "data" / "roof_test" / "labels.csv"
PHOTO_DIR = ROOT / "data" / "roof_test" / "photos"
REPORT_DIR = ROOT / "tests" / "eval" / "reports"

# CONCEPT §13.
TARGETS = {"roof_form": 0.85, "material": 0.70}
MIN_PHOTOS = 30

GRADED_FIELDS = ("roof_form", "material")
SUFFIXES = (".jpg", ".jpeg", ".png")


def load_labels() -> list[dict]:
    """Hand labels, excluding the example row that ships with the CSV."""
    with LABELS_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row for row in rows
        if (row.get("is_placeholder") or "").strip().lower() != "true"
    ]


def _photo_for(photo_id: str) -> Path | None:
    for suffix in SUFFIXES:
        candidate = PHOTO_DIR / f"{photo_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def evaluate(labels: list[dict]) -> list[dict]:
    results: list[dict] = []

    for row in labels:
        photo_id = row["photo_id"]
        path = _photo_for(photo_id)
        if path is None:
            print(f"  LEWAT {photo_id}: berkas foto tidak ada di {PHOTO_DIR.name}/")
            continue

        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        try:
            predicted = analyze_roof_bytes(path.read_bytes(), mime_type)
        except Exception as error:  # noqa: BLE001 -- any genai/network failure
            print(f"  GAGAL {photo_id}: {error}")
            continue

        entry = {"photo_id": photo_id, "confidence": predicted.get("confidence")}
        for field in GRADED_FIELDS:
            entry[f"true_{field}"] = row[field]
            entry[f"pred_{field}"] = predicted.get(field)
            entry[f"ok_{field}"] = row[field] == predicted.get(field)
        results.append(entry)

        marks = " ".join("OK" if entry[f"ok_{f}"] else "X " for f in GRADED_FIELDS)
        print(f"  {marks} {photo_id}  keyakinan {entry['confidence']}")

    return results


def accuracy(results: list[dict], field: str) -> float:
    if not results:
        return 0.0
    return sum(1 for entry in results if entry[f"ok_{field}"]) / len(results)


def confusion(results: list[dict], field: str) -> dict[str, dict[str, int]]:
    """True label -> predicted label -> count. Shows WHICH materials get confused."""
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entry in results:
        matrix[entry[f"true_{field}"]][str(entry[f"pred_{field}"])] += 1
    return {true: dict(predictions) for true, predictions in matrix.items()}


def main() -> None:
    labels = load_labels()
    print(f"label       : {len(labels)} foto berlabel (minimal {MIN_PHOTOS} untuk melaporkan)")

    results = evaluate(labels)
    summary = {
        "n_labelled": len(labels),
        "n_evaluated": len(results),
        "min_photos": MIN_PHOTOS,
        "reportable": len(results) >= MIN_PHOTOS,
        "accuracy": {field: accuracy(results, field) for field in GRADED_FIELDS},
        "targets": TARGETS,
        "confusion": {field: confusion(results, field) for field in GRADED_FIELDS},
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = REPORT_DIR / f"roof_{stamp}.json"
    report.write_text(
        json.dumps(
            {"run_at": datetime.now(UTC).isoformat(), "summary": summary, "results": results},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"laporan     : {report.relative_to(ROOT)}")

    check(results)


def check(results: list[dict]) -> None:
    """Withhold the accuracy figure until the set is big enough to mean something."""
    if len(results) < MIN_PHOTOS:
        print(
            f"\nBELUM BISA DILAPORKAN: {len(results)} foto dievaluasi, butuh {MIN_PHOTOS}. "
            "Akurasi dari sampel kecil bukan bukti. JANGAN sebut akurasi Cek Atap di "
            "proposal, video, atau brief sampai set ini lengkap "
            "(lihat data/roof_test/README.md)."
        )
        return

    for field, target in TARGETS.items():
        value = accuracy(results, field)
        verdict = "memenuhi" if value >= target else "DI BAWAH"
        print(f"  {field:12s} {value:.1%}  target {target:.0%}  {verdict}")

    for field in GRADED_FIELDS:
        if accuracy(results, field) < TARGETS[field]:
            print(
                f"\nPERINGATAN: {field} di bawah target. Lihat matriks kebingungan di laporan "
                "untuk melihat kelas mana yang tertukar, lalu perjelas panduannya di "
                "VISION_PROMPT. Jangan menurunkan targetnya."
            )
    print("check ok")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Jalankan dengan keadaan sekarang dan pastikan menolak melapor**

Run: `uv run python -m tests.eval.eval_roof`
Expected: `label : 0 foto berlabel` dan pesan `BELUM BISA DILAPORKAN`. Itu perilaku yang benar, bukan kegagalan.

- [ ] **Step 3: Kumpulkan dan labeli 30 foto (tugas pemilik proyek)**

Ikuti `data/roof_test/README.md`: potret atap tanpa wajah, nomor rumah, plat nomor, atau nama jalan; taruh di `data/roof_test/photos/`; jalankan `uv run --no-project --python 3.12 --with pillow python pipeline/strip_exif.py`; labeli satu baris per foto di `labels.csv` memakai enum dari `ROOF_SCHEMA`.

Usahakan sebarannya mewakili kenyataan Jakarta: genteng tanah liat, genteng beton, seng gelap, pelat beton datar, dan **minimal tiga foto asbes** — kelas itu yang memicu peringatan keselamatan, jadi akurasinya paling penting.

- [ ] **Step 4: Jalankan evaluasi sebenarnya dan catat hasilnya**

Run: `uv run python -m tests.eval.eval_roof`

Catat: `roof_form` `_____%`, `material` `_____%`. **Hanya angka ini** yang boleh muncul di proposal.

- [ ] **Step 5: Commit skrip dan laporan agregat**

```bash
git add tests/eval/eval_roof.py data/roof_test/labels.csv
git add -f tests/eval/reports/roof_*.json
git commit -m "test: tambah evaluasi Cek Atap yang menolak melapor di bawah 30 foto

Akurasi dari sampel kecil bukan bukti, dan angka yang sudah tercetak cenderung
terbawa ke proposal.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task M8-T3: Deploy dan checklist submission

**Files:**
- Create: `infra/firebase.json`
- Create: `infra/deploy_web.sh` (mode `755`)
- Create: `docs/SUBMISSION.md`
- Modify: `infra/deploy_api.sh` (tambah `TEDUH_WEB_ORIGIN` ke env var layanan)

**Interfaces:**
- Consumes: `infra/deploy_api.sh` (M0-T6); build Next.js dari M7.
- Produces: dua URL publik dan checklist terisi.

- [ ] **Step 1: Izinkan origin web di API**

Di `infra/deploy_api.sh`, ganti baris `--set-env-vars` menjadi:

```bash
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_ENTERPRISE=True,TEDUH_MODEL=${MODEL},TEDUH_WEB_ORIGIN=${TEDUH_WEB_ORIGIN:-}"
```

`api/main.py` sudah membaca `TEDUH_WEB_ORIGIN` untuk CORS (M3-T9). Tanpa ini, frontend yang sudah ter-deploy akan diblokir browser dan gejalanya hanya muncul sebagai peta kosong.

- [ ] **Step 2: Tulis `infra/firebase.json`**

```json
{
  "hosting": {
    "source": "../web",
    "frameworksBackend": {
      "region": "asia-southeast1"
    },
    "ignore": ["**/.git/**", "**/node_modules/**", "**/.next/cache/**"]
  }
}
```

Catatan: Firebase App Hosting menyajikan Next.js App Router termasuk komponen server. Kalau App Hosting tidak tersedia di proyek ini, pakai jalur Cloud Run di Step 3 — kedua jalur sah menurut CONCEPT §2.1.

- [ ] **Step 3: Tulis `infra/deploy_web.sh`**

```bash
#!/usr/bin/env bash
# Build and deploy teduh-web.
#
# Resolves the API URL from the deployed Cloud Run service rather than taking it as an
# argument, because a frontend built against the wrong API URL fails as an empty map with no
# error message -- the worst possible failure during judging.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT belum diisi}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast2}"
WEB_REGION="${TEDUH_WEB_REGION:-asia-southeast1}"
API_SERVICE="teduh-api"
WEB_SERVICE="teduh-web"
REPO="teduh"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_URL="$(gcloud run services describe "$API_SERVICE" \
  --project "$PROJECT" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)"

if [[ -z "$API_URL" ]]; then
  echo "GAGAL: layanan $API_SERVICE belum ada di $REGION." >&2
  echo "Jalankan ./infra/deploy_api.sh lebih dulu." >&2
  exit 1
fi
echo "==> API: $API_URL"

# Fail now rather than shipping a frontend that cannot reach its data.
if ! curl -fsS "${API_URL}/api/health" > /dev/null; then
  echo "GAGAL: ${API_URL}/api/health tidak menjawab." >&2
  exit 1
fi

cd web
NEXT_PUBLIC_TEDUH_API="$API_URL" npm run build

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${WEB_SERVICE}:$(date +%Y%m%d-%H%M%S)"

cat > Dockerfile.deploy <<'DOCKERFILE'
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY . .
ENV NODE_ENV=production PORT=8080
EXPOSE 8080
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "8080"]
DOCKERFILE

gcloud builds submit . --project "$PROJECT" --tag "$IMAGE"
rm -f Dockerfile.deploy

gcloud run deploy "$WEB_SERVICE" \
  --project "$PROJECT" \
  --region "$WEB_REGION" \
  --image "$IMAGE" \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances "${TEDUH_MIN_INSTANCES:-0}" \
  --max-instances 4 \
  --set-env-vars "NEXT_PUBLIC_TEDUH_API=${API_URL}"

WEB_URL="$(gcloud run services describe "$WEB_SERVICE" \
  --project "$PROJECT" --region "$WEB_REGION" --format 'value(status.url)')"

echo "==> web: $WEB_URL"
echo
echo "LANGKAH TERAKHIR: izinkan origin ini di API, kalau tidak browser akan memblokir"
echo "semua permintaan dan petanya tampil kosong tanpa pesan error:"
echo "  TEDUH_WEB_ORIGIN=${WEB_URL} ./infra/deploy_api.sh"
```

```bash
chmod +x infra/deploy_web.sh
```

- [ ] **Step 4: Deploy keduanya dan uji URL publiknya**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
export GOOGLE_CLOUD_PROJECT=<proyek>
export GOOGLE_CLOUD_LOCATION=asia-southeast2

./infra/deploy_api.sh
./infra/deploy_web.sh
# lalu, dengan URL web dari output di atas:
TEDUH_WEB_ORIGIN=<url-web> ./infra/deploy_api.sh
```

Verifikasi dari jaringan lain (atau jendela incognito, tanpa login Google):

```bash
curl -s <url-api>/api/health | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' <url-web>
```
Expected: `model_loaded: true`, `n_kelurahan: 264`, dan `200` untuk web.

Lalu buka `<url-web>` di incognito dan jalankan rangkaian demo penuh: ranking → faktor pendorong → simulasi → portofolio → brief → unduh PDF → `/cek-atap`. Kalau peta kosong, hampir pasti CORS: ulangi langkah `TEDUH_WEB_ORIGIN`.

- [ ] **Step 5: Naikkan `min-instances` untuk periode penilaian**

Mulai 19 Okt sampai 6 Nov (CONCEPT §14):

```bash
gcloud run services update teduh-api --project "$GOOGLE_CLOUD_PROJECT" \
  --region asia-southeast2 --min-instances 1
gcloud run services update teduh-web --project "$GOOGLE_CLOUD_PROJECT" \
  --region asia-southeast1 --min-instances 1
```

Pasang juga peringatan anggaran supaya tagihan tidak mengejutkan:

```bash
gcloud billing budgets create \
  --billing-account="$(gcloud billing projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(billingAccountName)' | cut -d/ -f2)" \
  --display-name="TEDUH penilaian" \
  --budget-amount=50USD \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9
```

**Turunkan kembali ke 0 setelah 6 Nov** — instance yang menyala terus tanpa pengunjung adalah biaya murni.

- [ ] **Step 6: Tulis `docs/SUBMISSION.md`**

```markdown
# Checklist Submission TEDUH

Batas: **18 Oktober 2026** (submit pagi, sisakan waktu untuk masalah unggah).
Kategori: **Sustainability & Social Impact**.

## Tautan

| Item | Tautan | Status |
|---|---|---|
| Prototipe (web) | `<url-web>` | ⬜ bisa dibuka tanpa login |
| API | `<url-api>` | ⬜ `/api/health` menjawab |
| Video demo (≤ 3 menit) | `<url-video>` | ⬜ publik |
| Proposal PDF | `docs/proposal/...` | ⬜ |
| Repo | `<url-repo>` | ⬜ |

## Angka yang boleh dikutip

Isi dari hasil pengukuran sebenarnya. **Kosongkan yang belum diukur — jangan pakai target sebagai hasil.**

| Klaim | Sumber angka | Nilai |
|---|---|---|
| Kelurahan tercakup | `kelurahan_metrics.parquet` | 264 |
| Sel grid 100 m | `grid_features.parquet` | 75.636 |
| Rata-rata LST kota | sel `lst_quality = good` | 41,84 °C |
| R² spatial block CV | `data/model/model_card.json` | ______ |
| RMSE | `model_card.json` | ______ °C |
| Akurasi pemilihan tool | laporan `golden_*.json` | ______% dari 20 pertanyaan |
| Latensi p50 chat | laporan `golden_*.json` | ______ s |
| Akurasi `roof_form` | laporan `roof_*.json` | ______% (butuh 30 foto) |
| Akurasi `material` | laporan `roof_*.json` | ______% (butuh 30 foto) |
| Validasi penduduk | DECISIONS 2026-10-09 | selisih 0,54% vs Dukcapil |

**Jangan diklaim:** target CONCEPT yang belum tercapai, akurasi Cek Atap sebelum 30 foto ada, dan R² 0,92 dari literatur (desain evaluasi kita berbeda).

## Checklist CONCEPT §16

- [ ] Tim 2–4 orang terdaftar sebelum 11 Okt 2026
- [ ] URL prototipe publik bisa dibuka tanpa login
- [ ] Video ≤ 3 menit, publik, ada narasi atau teks
- [ ] Proposal PDF: masalah, solusi, manfaat warga, kelayakan, skala, arsitektur, tim
- [ ] Kategori: Sustainability & Social Impact
- [ ] Halaman "Tentang & Sumber Data" ada di aplikasi (`/sumber-data`)
- [ ] Model card dan keterbatasan tercantum
- [ ] Semua angka literatur sudah dicek ke naskah asli (`data/evidence/interventions.json` semuanya `verified: true`)
- [ ] `min-instances=1` aktif untuk 19 Okt – 6 Nov
- [ ] Peringatan anggaran billing terpasang
- [ ] Tidak ada kredensial atau foto pengguna ter-commit

## Rangkaian demo yang harus lolos di URL publik

1. "Kelurahan mana di Jakarta Pusat yang paling perlu diprioritaskan?" → peta menyorot kelurahan nyata
2. "Kenapa yang teratas itu panas?" → faktor SHAP dengan label Bahasa Indonesia
3. "Kalau cool roof 50% di dua teratas, turun berapa?" → ΔLST + rentang literatur
4. "Anggaran kami Rp 2 miliar, susun paketnya." → total ≤ anggaran, porsi keadilan ≥ 60%
5. "Buatkan policy brief untuk Bappeda." → lencana angka terverifikasi + unduh PDF
6. `/cek-atap` dari ponsel → klasifikasi + rekomendasi + peringatan asbes bila relevan
7. Pertanyaan tentang data yang tidak dimiliki → agen menjawab "tidak ada", bukan angka
```

- [ ] **Step 7: Jalankan seluruh suite terakhir**

Run: `uv run pytest -q`
Expected: hijau semua.

Run: `cd web && npm test && npm run build`
Expected: hijau dan build sukses.

- [ ] **Step 8: Commit**

```bash
cd /Users/ahmadsyafiqkamil/Documents/Project/Teduh
git add infra/firebase.json infra/deploy_web.sh infra/deploy_api.sh docs/SUBMISSION.md
git commit -m "chore: tambah deploy frontend dan checklist submission

deploy_web.sh membaca URL API dari layanan yang sudah ter-deploy dan menolak jalan
kalau /api/health tidak menjawab, karena frontend yang dibangun terhadap URL salah
gagal sebagai peta kosong tanpa pesan error.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Definisi M8 selesai

- [ ] `uv run python -m tests.eval.run_golden` menjalankan 20 pertanyaan dan menulis laporan JSON.
- [ ] Akurasi pemilihan tool sebenarnya tercatat; kalau < 90%, perbaikan dilakukan di prompt dan deskripsi tool, **bukan** di `golden_questions.yaml`.
- [ ] p50 latensi tercatat dan dibandingkan dengan target 8 detik.
- [ ] `uv run python -m tests.eval.eval_roof` **menolak** melaporkan akurasi di bawah 30 foto.
- [ ] Dua URL publik hidup dan bisa dibuka tanpa login; CORS sudah diizinkan sehingga peta terisi.
- [ ] Rangkaian tujuh langkah demo lolos di URL publik, bukan hanya di lokal.
- [ ] `min-instances=1` dan peringatan anggaran aktif untuk periode penilaian.
- [ ] `docs/SUBMISSION.md` terisi dengan angka terukur, dan yang belum terukur dibiarkan kosong.
- [ ] `uv run pytest -q` dan `npm test` hijau.

**Selesai.** Lihat `docs/SUBMISSION.md` untuk langkah submission terakhir.
