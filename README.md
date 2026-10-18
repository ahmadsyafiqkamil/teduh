# TEDUH

**AI agent untuk perencanaan mitigasi Urban Heat Island di tingkat kelurahan.** Pilot DKI Jakarta.
Dibuat untuk **AI Builder Cup 2026**, kategori *Sustainability & Social Impact*.

Jakarta mencatat intensitas Urban Heat Island tertinggi di antara kota besar Indonesia yang diteliti,
dengan puncak sekitar 8 °C di musim kemarau. Pemetaan UHI berbasis machine learning sudah banyak dan
akurat, tetapi hasilnya jarang sampai ke dokumen perencanaan seperti RDTR, RPJMD, atau program
kelurahan — alat yang ada (CFD, NSGA-II, digital twin) terlalu teknis dan mahal untuk dinas daerah.

TEDUH menjembatani celah itu. Perencana cukup bertanya dalam bahasa sehari-hari, misalnya
*"Kelurahan mana di Jakarta Timur yang paling panas dan paling rentan, dan dengan anggaran
Rp 2 miliar intervensi apa yang paling efektif?"* — lalu agen menarik profil panas dari data satelit
yang sudah diolah, menghitung indeks kerentanan, menjalankan simulasi intervensi, menyusun portofolio
dalam batas anggaran, dan menulis draf policy brief yang setiap angkanya bisa ditelusuri ke sumbernya.

---

## Demo & materi submission

### 🎥 Video demo

**[`teduh-demo-annotated.mp4`](teduh-demo-annotated.mp4)** — rekaman aplikasi yang sudah berjalan di
Cloud Run, dengan anotasi di layar. Durasi **3 menit 26 detik**, 1198×720, H.264/AAC, 13,8 MB.

Alur yang ditunjukkan video, berurutan:

1. Peta panas & kerentanan 264 kelurahan Jakarta — lapisan LST, anomali, HVI, NDVI.
2. Tanya agen kelurahan prioritas → peta menyorot kelurahan nyata hasil `rank_priority_areas`.
3. "Kenapa yang teratas itu panas?" → faktor pendorong SHAP dengan label Bahasa Indonesia.
4. Simulasi skenario (mis. cool roof 50% di dua kelurahan teratas) → ΔLST model + rentang literatur.
5. Portofolio anggaran Rp 2 miliar → paket kelurahan × intervensi, total ≤ anggaran, porsi keadilan terjaga.
6. Policy brief → lencana angka terverifikasi dan unduhan PDF.
7. Halaman `/cek-atap` dari tampilan ponsel → klasifikasi atap + rekomendasi (termasuk peringatan asbes).

> Catatan: versi beranotasi ini **3:26**, di atas batas video submission ≤ 3 menit. Potong atau
> gunakan versi ringkas sebelum diunggah sebagai deliverable resmi (lihat `docs/SUBMISSION.md`).

### 📊 Deck presentasi

**[`docs/TEDUH_AI_Builder_Cup_Deck.pdf`](docs/TEDUH_AI_Builder_Cup_Deck.pdf)** — deck pitch 14 halaman
untuk AI Builder Cup: masalah dan bukti literatur, pengguna sasaran, arsitektur agen, data & model,
hasil evaluasi, serta potensi dampak dan skala. Sumber yang bisa diedit ada di
[`docs/TEDUH_AI_Builder_Cup_Deck.pptx`](docs/TEDUH_AI_Builder_Cup_Deck.pptx).

Mulai dari deck untuk gambaran menyeluruh dalam lima menit, lanjut ke video untuk melihat produknya
benar-benar berjalan, lalu ke [`docs/CONCEPT.md`](docs/CONCEPT.md) untuk detail desain.

---

## Fitur

| Fitur | Isi |
|---|---|
| Peta Panas & Kerentanan | Choropleth 264 kelurahan: LST musim kemarau, anomali terhadap rata-rata kota, Heat Vulnerability Index, NDVI, penduduk rentan |
| Chat agen | Bahasa Indonesia dengan toggle Inggris; memanggil tool dan menyorot kelurahan terkait di peta |
| Profil Kelurahan | Nilai panas, peringkat, faktor pendorong utama (SHAP), jumlah warga rentan |
| Simulasi Skenario | Pilih intervensi dan intensitas → ΔLST dari model + rentang literatur, lewat slider atau chat |
| Portofolio Anggaran | Input anggaran dan wilayah → paket kelurahan × intervensi yang memaksimalkan penurunan panas tertimbang warga rentan per rupiah, dengan kendala keadilan (OR-Tools CP-SAT) |
| Policy Brief | Draf Markdown → PDF dengan sitasi; validator menolak angka yang tidak punya asal-usul |
| Cek Atap | Unggah foto atap → Gemini vision mengklasifikasi, sistem merekomendasi berbasis aturan + bukti; halaman `/cek-atap` ramah ponsel |
| Sumber Data | Halaman `/sumber-data` dengan atribusi dataset dan model card |

## Prinsip yang tidak dilanggar

1. **LLM tidak menghitung angka.** Semua angka berasal dari fungsi Python deterministik di
   `teduh_agent/tools/` atau `model/`. Gemini hanya memilih tool dan menulis narasi.
2. **Setiap tool mengembalikan `facts`** dengan `id`, `label`, `value`, `unit`, `source`.
3. **Brief wajib lolos validator provenance** — angka liar ditolak, bukan divalidasi belakangan.
4. **Konstanta hanya di `config/*.yaml`**, setiap entri wajib punya `source:` (sitasi atau `ASUMSI`).
5. **Earth Engine tidak dipanggil saat runtime** — hanya di `pipeline/` (offline). Aplikasi membaca
   artefak Parquet/GeoJSON yang sudah dibakar ke image.
6. **Model ML:** LightGBM dengan monotonic constraints dan spatial block CV; lat/lon bukan fitur;
   metrik tidak pernah dilaporkan dari random split.

## Arsitektur

```
Next.js (web/)  ──SSE /run_sse──▶  ADK root_agent (teduh_agent/)
     │                                   ├── heat_analyst
     └──REST /api/*──▶ FastAPI (api/)    ├── intervention_planner
                             │           ├── policy_writer
                             │           └── roof_inspector
                             ▼                     │
                   fungsi tool yang sama ◀──────────┘
                             │
          model/ (LightGBM, SHAP, skenario, HVI) + data/ (Parquet, GeoJSON)
```

Handler REST memanggil **fungsi tool yang sama** dengan yang dipanggil agen, supaya UI dan agen tidak
pernah berselisih tentang angka yang sama. Earth Engine hanya hidup di `pipeline/` secara offline.

### Endpoint REST

| Method | Path | Fungsi |
|---|---|---|
| GET | `/api/health` | Readiness + apa yang ter-load (jumlah kelurahan/sel, model, SHAP) |
| GET | `/api/kelurahan` | GeoJSON ringan + metrik untuk peta |
| GET | `/api/kelurahan/{kel_id}` | Profil lengkap + driver SHAP |
| POST | `/api/simulate` | Skenario langsung dari slider (tanpa LLM) |
| POST | `/api/optimize` | Portofolio langsung dari form |
| POST | `/api/roof` | Unggah foto → klasifikasi + rekomendasi |
| GET | `/api/brief/{brief_id}` | Brief Markdown/PDF |
| GET | `/api/model-card` | Metrik dan batasan model |

Chat memakai endpoint ADK `/run_sse` dengan streaming.

## Stack

- **Python 3.12 + `uv`** — `google-adk`, `google-genai`, `fastapi`, `lightgbm`, `shap`, `scikit-learn`,
  `ortools`, `geopandas`, `pyarrow`, `weasyprint`; `earthengine-api` hanya di grup `pipeline`.
- **Frontend** — Next.js (App Router) + TypeScript + Tailwind + MapLibre GL JS, di `web/`.
- **Model** — Gemini 2.5 Flash di Vertex AI, region `asia-southeast1`; ID model dibaca dari env
  `TEDUH_MODEL`, tidak pernah di-hard-code.
- **Deploy** — Cloud Run `teduh-api` + `teduh-web` (`asia-southeast1`), build via Cloud Build,
  kunci di Secret Manager.

## Menjalankan lokal

```bash
uv sync                                   # install
cp .env.example .env                      # lalu isi kredensial
uv run pytest -q                          # tes
uv run adk web                            # UI dev ADK
uv run uvicorn api.main:app --reload      # API lokal di :8080
cd web && npm run dev                     # frontend di :3000
```

Pipeline dan pelatihan model (opsional, butuh akses Earth Engine):

```bash
uv run python -m pipeline.gee_extract
uv run python -m model.train
```

Deploy:

```bash
./infra/deploy_api.sh
./infra/deploy_web.sh
```

Env var penting (lihat [`.env.example`](.env.example)): `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION`, `TEDUH_MODEL`, `TEDUH_DATA_DIR`, `TEDUH_WEB_ORIGIN`,
`TEDUH_SINGLE_AGENT` (set `1` untuk fallback satu agen), `TEDUH_MIN_INSTANCES`.

## Angka yang sudah terukur

| Klaim | Nilai | Sumber |
|---|---|---|
| Kelurahan tercakup | 264 | `kelurahan_metrics.parquet` |
| Sel grid 100 m | 75.636 | `grid_features.parquet` |
| Rata-rata LST kota | 41,84 °C | sel `lst_quality = good` |
| R² spatial block CV | 0,755 (rata-rata 5 lipatan, terendah 0,723) | `data/model/model_card.json` |
| RMSE / MAE | 1,24 °C / 0,94 °C | `model_card.json` |
| Baseline regresi linear | R² 0,686 — LightGBM unggul 0,069 | `model_card.json` |
| Validasi penduduk | selisih 0,54% vs Dukcapil | `docs/DECISIONS.md` |
| Bukti literatur terverifikasi | 4 dari 10 entri | `data/evidence/interventions.json` |

Yang **belum** memenuhi target dan karena itu tidak diklaim sebagai capaian: akurasi pemilihan tool
(65%, target 90%), latensi p50 chat (9,4 s, target 8 s), dan akurasi Cek Atap (belum terukur, foto
berlabel masih 0 dari 30). Daftar lengkap beserta aturan kutipnya ada di
[`docs/SUBMISSION.md`](docs/SUBMISSION.md).

## Struktur repo

```
docs/        CONCEPT.md (sumber kebenaran desain), DECISIONS.md, PRD.md,
             DATA_SOURCES.md, DATA_STATUS.md, SUBMISSION.md, deck PDF/PPTX
config/      scenario.yaml, costs.yaml, hvi.yaml — konstanta berlabel sumber
pipeline/    offline Earth Engine: gee_extract, build_grid, aggregate_kelurahan, verify_costs
model/       hvi, train (LightGBM + spatial CV), explain (SHAP), scenario, costs
data/        boundaries/, processed/, model/, evidence/, briefs/, roof_test/
teduh_agent/ paket ADK: agent.py (root_agent), llm.py, store.py, sub_agents/, tools/, prompts/
api/         FastAPI: main.py, routes.py, schemas.py
web/         Next.js App Router: /, /cek-atap, /sumber-data
infra/       Dockerfile, cloudbuild.yaml, deploy_api.sh, deploy_web.sh
tests/       unit + integrasi + tests/eval/golden_questions.yaml
```

## Tes

```bash
uv run pytest -q
```

Tes yang menjaga invarian inti:

- `test_scenario.py` — menambah pohon atau albedo tidak pernah menaikkan LST; ekstrapolasi diberi flag.
- `test_provenance.py` — angka liar di brief ditolak; tahun dan nomor bagian tidak ikut ditolak.
- `test_optimize.py` — total biaya ≤ anggaran; kendala porsi keadilan terpenuhi.
- `tests/eval/golden_questions.yaml` — 20 pertanyaan beserta tool yang diharapkan.

## Dokumentasi

| Dokumen | Isi |
|---|---|
| [`docs/CONCEPT.md`](docs/CONCEPT.md) | Sumber kebenaran desain: masalah, arsitektur, data, model, desain agen, UX |
| [`docs/PRD.md`](docs/PRD.md) | Persyaratan yang bisa diterima/ditolak |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Penyimpangan dari konsep beserta alasannya |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Katalog data, lisensi, sitasi, harga satuan |
| [`docs/DATA_STATUS.md`](docs/DATA_STATUS.md) | Apa yang sudah dan belum ada di disk |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Checklist submission, tautan, dan angka yang boleh dikutip |
| [`CLAUDE.md`](CLAUDE.md) | Aturan kerja untuk kontributor dan agen coding |
