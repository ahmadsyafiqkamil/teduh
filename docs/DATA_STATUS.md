# TEDUH — Status Data (audit celah)

Diaudit **9 Okt 2026** terhadap isi `data/` di disk, diperbarui setelah M5 selesai. Katalog lengkap tiap sumber ada di `docs/DATA_SOURCES.md`; file ini hanya menjawab satu pertanyaan: **apa yang sudah ada dan apa yang belum.**

Ringkas: **M0–M5 selesai, `uv run pytest -q` hijau (262 lulus, 1 skip).** Satu-satunya data yang masih benar-benar kosong adalah **30 foto uji atap**, dan itu hanya memblokir satu angka akurasi — bukan fiturnya.

---

## 1. Sudah ada

### Artefak olahan — siap dipakai aplikasi

| File | Isi | Di git? |
|---|---|---|
| `data/processed/grid_features.parquet` | 75.636 sel 100 m, 24 kolom, 264/264 kelurahan. 7 MB | tidak (regenerable) |
| `data/processed/kelurahan_metrics.parquet` | 264 kelurahan × 32 kolom: HVI + H/E/S/A, LST rata-rata & tertimbang penduduk, `exposed_vulnerable`, `hvi_rank` | ya, 81 KB |
| `data/boundaries/kelurahan.geojson` | 264 poligon kelurahan (HDX COD-AB) | ya, 2,2 MB |
| `data/processed/bmkg_ghcn_crosscheck.csv` | 7 station-month pembanding BMKG ↔ GHCN, lulus | ya |
| `tests/fixtures/*_sample.parquet` | 173 sel, 3 kelurahan — tes unit jalan tanpa data penuh | ya |
| `config/{hvi,scenario,costs}.yaml` | konstanta berlabel `source:` | ya |
| `data/evidence/interventions.json` | 10 entri bukti, 4 `verified=true` | ya |

### Artefak model — M2 selesai

| File | Isi |
|---|---|
| `data/model/model.txt` | LightGBM, 12 fitur, monotonic constraints pada albedo/ndvi/tree_frac/water_frac (−1) dan built_frac/ndbi (+1) |
| `data/model/model_card.json` | Spatial block CV 1000 m, GroupKFold 5 lipatan. **R² 0,755 (rentang fold 0,723–0,776)**, RMSE 1,243, MAE 0,940. Baseline linear R² 0,686 |
| `data/model/shap_by_kel.parquet` | Nilai SHAP per kelurahan, additivitas dijamin |

Tidak di-commit (dihasilkan ulang oleh `model/train.py`), dibakar ke image lewat `infra/Dockerfile` dengan guard artefak.

75.636 sel grid − 5 NaN `lst_c` − 28 sel kualitas rendah = **75.603 sel latih**. Angkanya rekonsiliasi.

### Data mentah — 239 MB, semua di `.gitignore`

| Sumber | File | Peran |
|---|---|---|
| GEE multiband (Landsat/Sentinel) | `raw/gee/teduh_jakarta_gee_100m.tif`, 4 MB | fitur LST, albedo, NDVI, NDBI, NDWI |
| WorldPop Global2 2025 | `raw/worldpop/pop_2025.tif` + 8 raster kelompok umur | penduduk, `pop_u5`, `pop_65p` |
| ESA WorldCover 2021 | `raw/worldcover/worldcover_2021.tif` | `tree_frac`, `built_frac`, `water_frac` |
| Copernicus DEM GLO-30 | `raw/dem/cop_dem_glo30.tif` | `elev_m` |
| HDX COD-AB Indonesia | `raw/hdx/idn_admin_boundaries.gdb.zip`, 209 MB | sumber batas kelurahan |
| Kepgub DKI 811/2025 | `raw/sbm/2025KEPGUB0031811.pdf` + `.md` | harga satuan (terverifikasi ke text layer) |
| Pergub DKI 17/2025 | `raw/costs/pergub_dki_17_2025_shs_2026.pdf` | pembanding harga |
| NOAA GHCN-Daily | `raw/bmkg/stations_daily.csv`, 3.270 baris, 4 stasiun | validasi suhu udara |
| BMKG dataonline | `raw/bmkg/stations_monthly.csv`, 32 baris + 3 XLSX | validasi suhu bulanan |

Regenerasi: `uv run --no-project --python 3.12 --with geopandas --with pyogrio --with rasterio python pipeline/fetch_public.py`.

### NaN yang diketahui dan wajar

| Kolom | NaN | Sebab |
|---|---|---|
| `lst_c`, `lst_n` | 5 / 75.636 | sel tanpa observasi bebas awan yang lolos filter |
| `pop`, `pop_u5`, `pop_65p` | 1.207 / 75.636 | sel WorldPop nol penduduk (air, bandara, pelabuhan) |

`kelurahan_metrics.parquet`: **nol NaN di 32 kolom**.

---

## 2. Belum ada

### Foto uji Cek Atap — 0 dari 30

`data/roof_test/photos/` kosong; `labels.csv` hanya berisi baris contoh `EXAMPLE-00`.

**Yang diblokir hanya satu baris tabel §13**, bukan fiturnya. `/cek-atap` dan `POST /api/roof` berjalan dengan satu foto; `recommend_roof_action` adalah aturan murni tanpa LLM, jadi tidak dilatih dari set itu. Yang butuh 30 foto berlabel adalah **angka akurasinya** (`roof_form` ≥ 85%, `material` ≥ 70%), diukur di M8-T2.

Karena itu dokumen dan UI menulis **"belum diukur"** sejak sekarang, bukan menunggu. Kalau 30 foto terkumpul sebelum 18 Okt, satu baris itu dinaikkan; kalau tidak, submission tetap konsisten.

Cara mengumpulkan ada di `data/roof_test/README.md`. Jalankan `pipeline/strip_exif.py` **sebelum** foto apa pun masuk repo — foto atap ber-GPS adalah alamat rumah.

### Celah kualitas (tidak memblokir, tapi melemahkan klaim)

| Yang kurang | Catatan |
|---|---|
| **Harga cool roof & green roof per m²** | Nol item di Kepgub 811/2025, masih `"ASUMSI"`. Mengalir ke setiap rupiah di `calculate_cost`, portofolio, dan brief. **Celah paling berbobot yang tersisa** — satu penawaran vendor memperbaikinya dalam 1–2 jam |
| **6 dari 10 entri bukti belum terverifikasi** | `get_evidence` dan `recommend_roof_action` menyaring `verified=true`, jadi 6 entri itu tidak pernah terkutip — aman, tapi basis buktinya efektif cuma 4 entri |
| **Stasiun Halim 96747 kosong total** | 0/4 bulan, dicoba 2×. Validasi suhu bersandar pada Kemayoran + Priok |
| **RPJMD DKI 2025–2029 belum dilacak** | Satu dari empat rujukan di bagian brief "Keterkaitan dengan Dokumen Perencanaan" |
| Persen RTH resmi Jakarta | `tree_frac` kota 0,159 **bukan** angka RTH. Jangan disamakan. Bisa dilewati |
| Jakarta Satu Smart RDTR | Lisensi belum dievaluasi. Bisa dilewati |

### Sengaja tidak diunduh

- **PDF dokumen perencanaan** (Perda DKI 7/2024 RTRW, Pergub DKI 31/2022 RDTR, UU 26/2007 Psl 29). Brief hanya butuh sitasi nomor/tahun/pasal, sudah terkatalog di `DATA_SOURCES.md` §G.
- **Band `no2`** — nol di seluruh raster, dibuang (`docs/DECISIONS.md`).

---

## 3. Sisa pekerjaan

| Milestone | Status |
|---|---|
| M0 Kerangka … M5 Brief | **selesai**, 262 tes lulus |
| **M6 Cek Atap** | sedang dikerjakan |
| M7 Frontend | belum — **porsi waktu terbesar, satu-satunya yang juri lihat** |
| M8 Evaluasi & deploy | belum |

Dua jebakan yang sudah diketahui:

1. **Jangan ambil angka dari file desain hi-fi.** Di situ 267 kelurahan dan 34,3 °C; yang benar **264** dan **41,84 °C**. Kalau angka desain tersalin, choropleth rusak — semua kelurahan masuk kelas LST tertinggi. Sumbernya `kelurahan_metrics.parquet`.
2. **Laporkan R² sebagai rentang**, "0,755 (fold 0,723–0,776)". Rata-ratanya lewat target 0,75 hanya dengan selisih 0,0046 dan fold 2 ada di bawahnya. Lebih baik Anda yang menyebut lebih dulu daripada juri yang menemukannya di model card.
