# CLAUDE.md — TEDUH

TEDUH adalah AI agent (Gemini + Google ADK) untuk perencanaan mitigasi Urban Heat Island di tingkat kelurahan, pilot DKI Jakarta. Dibuat untuk AI Builder Cup 2026, tema Sustainability & Social Impact. **Batas submission 18 Okt 2026.**

Sumber kebenaran desain: `docs/CONCEPT.md`. Baca bagian yang relevan sebelum mengerjakan fitur. Kalau implementasi harus menyimpang dari konsep, catat alasannya di `docs/DECISIONS.md`.

## Aturan utama (jangan dilanggar)

1. **LLM tidak menghitung angka.** Semua angka berasal dari fungsi Python deterministik di `teduh_agent/tools/` atau `model/`. Gemini hanya memilih tool dan menulis narasi.
2. **Setiap tool mengembalikan `facts`** dengan `id`, `label`, `value`, `unit`, `source` (lihat CONCEPT §8.2). Jangan buat tool yang mengembalikan angka tanpa `facts`.
3. **Brief wajib lolos validator provenance** (`teduh_agent/tools/brief.py`, CONCEPT §8.4). Jangan melemahkan validator agar tes lulus.
4. **Jangan mengarang konstanta.** Harga, albedo, NDVI target, dsb. hanya di `config/*.yaml` dan setiap entri wajib punya `source:` (sitasi atau `"ASUMSI"`).
5. **Model ML:** LightGBM dengan monotonic constraints (CONCEPT §7.3), spatial block CV. Jangan pakai lat/lon sebagai fitur. Jangan melaporkan metrik dari random split.
6. **Earth Engine tidak dipanggil saat runtime.** Hanya di `pipeline/` (offline). Aplikasi membaca artefak Parquet/GeoJSON dari `TEDUH_DATA_URI`.
7. Teks UI dan jawaban agen: **Bahasa Indonesia**, toggle Inggris. Kode, nama variabel, dan komentar: Inggris.
8. Jangan commit kredensial, data mentah besar, atau foto pengguna.

## Stack

- Python 3.12 + `uv`. Paket: `google-adk`, `google-genai`, `fastapi`, `lightgbm`, `shap`, `scikit-learn`, `ortools`, `geopandas`, `pyarrow`, `earthengine-api` (pipeline saja), `weasyprint`.
- Frontend: Next.js (App Router) + TypeScript + Tailwind + MapLibre GL JS, di `web/`.
- Deploy: Cloud Run (`teduh-api`), Firebase App Hosting atau Cloud Run (`teduh-web`), GCS, Firestore, Secret Manager.
- Model Gemini dibaca dari env `TEDUH_MODEL` (default `gemini-2.5-flash`). Jangan hard-code model ID.
- Paket agen ADK ada di `teduh_agent/` dengan `root_agent` di `agent.py` dan `from . import agent` di `__init__.py`.

## Urutan build (milestone)

Kerjakan berurutan. Setiap milestone selesai = tes lulus + bisa didemokan.

1. **M0 Kerangka** — struktur repo sesuai CONCEPT §11.2, `pyproject.toml`, Dockerfile, ADK agent dengan satu tool dummy berjalan lokal (`adk web`) dan di Cloud Run.
2. **M1 Data** — `pipeline/` menghasilkan `grid_features.parquet` dan `kelurahan.geojson` + HVI (CONCEPT §7.1–7.4). Sediakan juga data sintetis kecil di `tests/fixtures/` agar M2–M4 bisa jalan sebelum data asli siap.
3. **M2 Model** — `model/train.py`, `model/explain.py`, `model/scenario.py`, plus `model_card.json`.
4. **M3 Tools** — semua tool di CONCEPT §8.2 dengan unit test. Endpoint REST di `api/`.
5. **M4 Agen** — root + sub-agen + instruksi sistem (CONCEPT §8.1, §8.3). Fallback satu agen tetap bisa dijalankan lewat flag `TEDUH_SINGLE_AGENT=1`.
6. **M5 Brief** — render Markdown → PDF + validator provenance.
7. **M6 Cek Atap** — Gemini vision dengan `response_schema` + aturan rekomendasi (CONCEPT §8.5).
8. **M7 Frontend** — peta, chat SSE, panel skenario, halaman `/cek-atap`.
9. **M8 Evaluasi & deploy** — golden questions, `min-instances=1`, halaman sumber data.

## Perintah

```bash
uv sync                                   # install
uv run pytest -q                          # tes
uv run adk web                            # UI dev ADK lokal
uv run uvicorn api.main:app --reload      # API lokal
uv run python -m pipeline.gee_extract     # pipeline offline (butuh akses Earth Engine)
uv run python -m model.train              # latih model
cd web && npm run dev                     # frontend
./infra/deploy_api.sh                     # deploy Cloud Run
```

## Tes yang wajib ada

- `test_scenario.py`: menambah pohon atau albedo tidak pernah menaikkan LST; ekstrapolasi diberi flag.
- `test_provenance.py`: angka liar di brief ditolak; tahun dan nomor bagian tidak ditolak.
- `test_optimize.py`: total biaya ≤ anggaran; kendala porsi keadilan terpenuhi.
- `tests/eval/golden_questions.yaml`: 20 pertanyaan + tool yang diharapkan.

## Hal yang perlu ditanyakan ke pengguna, bukan ditebak

- Harga satuan intervensi, sumber batas kelurahan, kota pilot jika berubah, region GCP, dan apa pun yang mengubah klaim di proposal.
