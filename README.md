# TEDUH

**An AI agent for planning Urban Heat Island mitigation at the sub-district (kelurahan) level.**
Pilot city: Jakarta, Indonesia. Built for the **AI Builder Cup 2026**, *Sustainability & Social Impact*.

Jakarta records the highest Urban Heat Island intensity among the major Indonesian cities that have
been studied, peaking at roughly 8 °C during the dry season. Machine-learning UHI mapping is by now
plentiful and accurate, yet its results rarely reach the documents that actually govern a city —
spatial plans, mid-term development plans, sub-district programs. The tools that could close that gap
(CFD simulation, NSGA-II optimization, digital twins) are too technical and too expensive for a
municipal agency.

TEDUH closes it with a conversation. A planner asks in plain language — *"Which sub-district in East
Jakarta is hottest and most vulnerable, and with a budget of IDR 2 billion, which intervention gives
the most cooling?"* — and the agent pulls each area's heat profile from processed satellite data,
computes a heat vulnerability index, runs intervention scenarios through an ML model, assembles a
portfolio that fits the budget, and drafts a policy brief in which every number traces back to its
source.

---

## Demo & submission material

### 🎥 Demo video

**[`teduh-demo-annotated.mp4`](teduh-demo-annotated.mp4)** — a screen recording of the app running on
Cloud Run, with on-screen annotations. **3 minutes 26 seconds**, 1198×720, H.264/AAC, 13.8 MB.

[![Demo video](https://img.youtube.com/vi/6eDuZJqVK7A/0.jpg)](https://youtu.be/6eDuZJqVK7A?si=uasUPShFLBrPG_Wa)
> **Klik gambar di atas untuk memutar video demo di YouTube.**  
> Jika tidak dapat memuat video, [klik di sini untuk membuka link YouTube](https://youtu.be/6eDuZJqVK7A?si=uasUPShFLBrPG_Wa).

[YouTube demo video (`6eDuZJqVK7A`)](https://youtu.be/6eDuZJqVK7A?si=uasUPShFLBrPG_Wa)

What the video walks through, in order:

1. The heat and vulnerability map across Jakarta's 264 sub-districts — LST, anomaly, HVI, NDVI layers.
2. Asking the agent for priority areas → the map highlights the real areas returned by `rank_priority_areas`.
3. "Why is the top one hot?" → SHAP driver factors with plain-language labels.
4. A scenario simulation (cool roof at 50% coverage in the top two areas) → model ΔLST plus the literature range.
5. A IDR 2 billion budget portfolio → area × intervention packages, total within budget, equity share held.
6. The policy brief → verified-number badges and a PDF download.
7. The `/cek-atap` (roof check) page on a phone viewport → roof classification, recommendation, and the asbestos warning when relevant.

> Note: this annotated cut runs **3:26**, over the competition's 3-minute ceiling. Trim it or use a
> shorter cut before uploading it as the official deliverable (see `docs/SUBMISSION.md`).

### 📊 Pitch deck

**[`docs/TEDUH_AI_Builder_Cup_Deck.pdf`](docs/TEDUH_AI_Builder_Cup_Deck.pdf)** — the 14-page AI Builder
Cup deck: the problem and its evidence base, target users, agent architecture, data and model,
evaluation results, and the impact and scaling case. The editable source is
[`docs/TEDUH_AI_Builder_Cup_Deck.pptx`](docs/TEDUH_AI_Builder_Cup_Deck.pptx).

Start with the deck for the whole picture in five minutes, watch the video to see the product actually
running, then read [`docs/CONCEPT.md`](docs/CONCEPT.md) for the design detail.

---

## Features

| Feature | What it does |
|---|---|
| Heat & vulnerability map | Choropleth over 264 sub-districts: dry-season LST, anomaly against the city mean, Heat Vulnerability Index, NDVI, vulnerable population |
| Agent chat | Indonesian with an English toggle; calls tools and highlights the relevant areas on the map |
| Area profile | Heat values, ranking, dominant driver factors (SHAP), vulnerable resident counts |
| Scenario simulation | Pick an intervention and its intensity → model ΔLST plus the literature range, via slider or chat |
| Budget portfolio | Enter a budget and a scope → area × intervention packages that maximize cooling weighted by vulnerable residents per rupiah, under equity constraints (OR-Tools CP-SAT) |
| Policy brief | Markdown → PDF draft with citations; a validator rejects any number without provenance |
| Roof check | Upload a roof photo → Gemini vision classifies it, rules plus evidence produce the recommendation; `/cek-atap` is mobile-friendly |
| Data sources | `/sumber-data` page with dataset attribution and the model card |

## Non-negotiable principles

1. **The LLM never computes a number.** Every figure comes from deterministic Python in
   `teduh_agent/tools/` or `model/`. Gemini only selects tools and writes prose.
2. **Every tool returns `facts`** carrying `id`, `label`, `value`, `unit`, `source`.
3. **A brief must pass the provenance validator** — stray numbers are rejected, not reviewed later.
4. **Constants live only in `config/*.yaml`**, and every entry carries a `source:` (a citation or `ASUMSI`).
5. **Earth Engine is never called at runtime** — only in `pipeline/`, offline. The app reads Parquet
   and GeoJSON artifacts baked into the image.
6. **The ML model** is LightGBM with monotonic constraints and spatial block CV; lat/lon are not
   features; metrics are never reported from a random split.

## Architecture

```
Next.js (web/)  ──SSE /run_sse──▶  ADK root_agent (teduh_agent/)
     │                                   ├── heat_analyst
     └──REST /api/*──▶ FastAPI (api/)    ├── intervention_planner
                             │           ├── policy_writer
                             │           └── roof_inspector
                             ▼                     │
                   the same tool functions ◀────────┘
                             │
          model/ (LightGBM, SHAP, scenario, HVI) + data/ (Parquet, GeoJSON)
```

The REST handlers call **the same tool functions** the agent calls, so the UI and the agent can never
disagree about the same number. Earth Engine lives only in `pipeline/`, offline.

### REST endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Readiness plus what loaded (area/cell counts, model, SHAP) |
| GET | `/api/kelurahan` | Lightweight GeoJSON plus map metrics |
| GET | `/api/kelurahan/{kel_id}` | Full profile plus SHAP drivers |
| POST | `/api/simulate` | Scenario straight from the slider (no LLM) |
| POST | `/api/optimize` | Portfolio straight from the form |
| POST | `/api/roof` | Photo upload → classification plus recommendation |
| GET | `/api/brief/{brief_id}` | Brief as Markdown/PDF |
| GET | `/api/model-card` | Model metrics and limitations |

Chat runs over the ADK `/run_sse` streaming endpoint.

## Stack

- **Python 3.12 + `uv`** — `google-adk`, `google-genai`, `fastapi`, `lightgbm`, `shap`, `scikit-learn`,
  `ortools`, `geopandas`, `pyarrow`, `weasyprint`; `earthengine-api` only in the `pipeline` group.
- **Frontend** — Next.js (App Router) + TypeScript + Tailwind + MapLibre GL JS, under `web/`.
- **Model** — Gemini 2.5 Flash on Vertex AI, region `asia-southeast1`; the model ID is read from
  `TEDUH_MODEL` and never hard-coded.
- **Deploy** — Cloud Run `teduh-api` + `teduh-web` (`asia-southeast1`), built via Cloud Build, keys in
  Secret Manager.

## Running locally

```bash
uv sync                                   # install
cp .env.example .env                      # then fill in credentials
uv run pytest -q                          # tests
uv run adk web                            # ADK dev UI
uv run uvicorn api.main:app --reload      # API on :8080
cd web && npm run dev                     # frontend on :3000
```

Pipeline and model training (optional, needs Earth Engine access):

```bash
uv run python -m pipeline.gee_extract
uv run python -m model.train
```

Deploy:

```bash
./infra/deploy_api.sh
./infra/deploy_web.sh
```

Key environment variables (see [`.env.example`](.env.example)): `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION`, `TEDUH_MODEL`, `TEDUH_DATA_DIR`, `TEDUH_WEB_ORIGIN`,
`TEDUH_SINGLE_AGENT` (set to `1` for the single-agent fallback), `TEDUH_MIN_INSTANCES`.

## Measured numbers

| Claim | Value | Source |
|---|---|---|
| Sub-districts covered | 264 | `kelurahan_metrics.parquet` |
| 100 m grid cells | 75,636 | `grid_features.parquet` |
| City mean LST | 41.84 °C | cells with `lst_quality = good` |
| R², spatial block CV | 0.755 (mean of 5 folds, lowest 0.723) | `data/model/model_card.json` |
| RMSE / MAE | 1.24 °C / 0.94 °C | `model_card.json` |
| Linear regression baseline | R² 0.686 — LightGBM ahead by 0.069 | `model_card.json` |
| Population validation | 0.54% deviation vs. Dukcapil | `docs/DECISIONS.md` |
| Verified literature evidence | 4 of 10 entries | `data/evidence/interventions.json` |

Not yet at target, and therefore **not claimed** as an achievement: tool-selection accuracy (65%,
target 90%), chat p50 latency (9.4 s, target 8 s), and roof-check accuracy (unmeasured — 0 of 30
labeled photos collected). The full list, with the rules on what may be quoted, is in
[`docs/SUBMISSION.md`](docs/SUBMISSION.md).

## Repository layout

```
docs/        CONCEPT.md (design source of truth), DECISIONS.md, PRD.md,
             DATA_SOURCES.md, DATA_STATUS.md, SUBMISSION.md, deck PDF/PPTX
config/      scenario.yaml, costs.yaml, hvi.yaml — constants, each with a source label
pipeline/    offline Earth Engine: gee_extract, build_grid, aggregate_kelurahan, verify_costs
model/       hvi, train (LightGBM + spatial CV), explain (SHAP), scenario, costs
data/        boundaries/, processed/, model/, evidence/, briefs/, roof_test/
teduh_agent/ the ADK package: agent.py (root_agent), llm.py, store.py, sub_agents/, tools/, prompts/
api/         FastAPI: main.py, routes.py, schemas.py
web/         Next.js App Router: /, /cek-atap, /sumber-data
infra/       Dockerfile, cloudbuild.yaml, deploy_api.sh, deploy_web.sh
tests/       unit + integration + tests/eval/golden_questions.yaml
```

## Tests

```bash
uv run pytest -q
```

The tests that guard the core invariants:

- `test_scenario.py` — adding trees or albedo never raises LST; extrapolation gets flagged.
- `test_provenance.py` — stray numbers in a brief are rejected; years and section numbers are not.
- `test_optimize.py` — total cost stays within budget; the equity-share constraint holds.
- `tests/eval/golden_questions.yaml` — 20 questions with their expected tool calls.

## Documentation

| Document | Contents |
|---|---|
| [`docs/CONCEPT.md`](docs/CONCEPT.md) | Design source of truth: problem, architecture, data, model, agent design, UX |
| [`docs/PRD.md`](docs/PRD.md) | Requirements that can be accepted or rejected |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Deviations from the concept and why they were made |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Data catalog, licenses, citations, unit costs |
| [`docs/DATA_STATUS.md`](docs/DATA_STATUS.md) | What is and is not on disk |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Submission checklist, links, and quotable numbers |
| [`CLAUDE.md`](CLAUDE.md) | Working rules for contributors and coding agents |

UI copy and agent answers are in Indonesian with an English toggle; code, identifiers, and comments
are in English.
