# TEDUH — Product Requirements Document

> Turunan dari `docs/CONCEPT.md` (sumber kebenaran desain) dan `docs/DECISIONS.md` (penyimpangan yang sudah diputuskan). Dokumen ini menerjemahkan konsep menjadi **persyaratan yang bisa diterima/ditolak**. Kalau PRD dan CONCEPT berselisih, CONCEPT menang dan PRD diperbaiki.

| | |
|---|---|
| Versi | 1.0 — 9 Oktober 2026 |
| Status data | M1 selesai (grid + kelurahan + HVI nyata sudah ada di disk) |
| Batas submission | **18 Oktober 2026** |
| Rencana implementasi | `docs/superpowers/plans/README.md` |

---

## 1. Masalah dan peluang

Dinas di kota Indonesia tidak punya alat murah untuk mengubah data panas perkotaan menjadi keputusan intervensi yang berpihak pada warga rentan dan bisa dipertanggungjawabkan dalam dokumen kebijakan (CONCEPT §3.2).

Tiga celah yang TEDUH tutup:

1. **Celah implementasi.** Peta termal akademis tidak pernah masuk RDTR/RPJMD.
2. **Celah keahlian.** Alat yang ada butuh Rhino-Grasshopper, CFD, atau algoritma genetika.
3. **Celah keadilan.** Intervensi disebar merata, bukan diprioritaskan ke warga rentan.

## 2. Pengguna dan pekerjaan yang harus selesai

| Persona | Pekerjaan (job-to-be-done) | Bukti keberhasilan |
|---|---|---|
| **Perencana Bappeda/DLH** (persona utama demo) | "Tentukan 5 kelurahan prioritas, simulasikan intervensi dalam anggaran saya, dan beri saya dokumen yang bisa saya lampirkan." | Menyelesaikan rangkaian: ranking → simulasi → optimasi → unduh brief PDF, dalam satu percakapan < 5 menit. |
| **Lurah / fasilitator** | "Saya butuh angka untuk usulan Musrenbang kelurahan saya." | Membuka profil kelurahan dan menyalin ringkasan tanpa pelatihan. |
| **Warga** | "Bagaimana mendinginkan rumah saya dengan biaya wajar?" | Unggah foto atap di ponsel → rekomendasi + catatan keselamatan. |
| **Peneliti / juri** | "Dari mana angka ini?" | Setiap angka di UI punya chip sumber; model card terbuka. |

## 3. Prinsip produk (tidak bisa dinegosiasikan)

Diturunkan dari CONCEPT §6.2 dan `CLAUDE.md`:

| # | Prinsip | Konsekuensi teknis yang diuji |
|---|---|---|
| P1 | **LLM tidak menghitung angka.** | Semua angka dari fungsi Python deterministik di `model/` atau `teduh_agent/tools/`. |
| P2 | **Setiap angka punya asal-usul.** | Setiap tool mengembalikan `facts[]`; brief ditolak kalau memuat angka tanpa penanda. |
| P3 | **Data diolah di depan.** | Earth Engine tidak pernah dipanggil saat runtime; app membaca Parquet/GeoJSON. |
| P4 | **Jujur soal ketidakpastian.** | ΔLST selalu berlabel "indikatif" + rentang literatur + flag ekstrapolasi. |
| P5 | **Bahasa Indonesia lebih dulu.** | UI dan jawaban agen Bahasa Indonesia; toggle EN. Kode Inggris. |
| P6 | **Jangan mengarang konstanta.** | Harga/albedo/NDVI hanya di `config/*.yaml`, tiap entri wajib `source:`. |

## 4. Lingkup

### 4.1 P0 — wajib ada di demo

| ID | Fitur | Definisi selesai (acceptance) |
|---|---|---|
| F1 | **Peta panas & kerentanan** | Choropleth 264 kelurahan, 4 lapisan (LST, HVI, Vegetasi, Penduduk rentan), legenda + palet sesuai `design/README.md`, atribusi data tampil. |
| F2 | **Chat agen (ID)** | Pertanyaan bahasa sehari-hari → tool dipilih benar ≥ 90% pada 20 golden questions; langkah kerja tool terlihat di UI; jawaban menyorot kelurahan di peta. |
| F3 | **Profil kelurahan** | LST, anomali, peringkat HVI, 4 komponen HVI, SHAP 3–5 faktor, tutupan lahan, jumlah warga rentan. Jumlah kontribusi SHAP = selisih prediksi (divalidasi backend). |
| F4 | **Simulasi skenario** | 3 slider (kanopi pp, cool roof %, green roof %) → ΔLST rata-rata & tertimbang penduduk, luas, biaya, flag ekstrapolasi, pembanding literatur. |
| F5 | **Portofolio anggaran** | Input anggaran → paket terpilih dengan total biaya ≤ anggaran dan ≥ 60% anggaran ke kuintil HVI teratas. |
| F6 | **Policy brief** | Markdown → PDF, 8 bagian tetap, lencana "Semua angka terverifikasi (n fakta)", unduh PDF. |
| F7 | **Cek Atap** | Foto → klasifikasi terstruktur Gemini vision → rekomendasi berbasis aturan + catatan keselamatan asbes. Halaman `/cek-atap` ramah ponsel. |
| F8 | **Halaman Tentang & Sumber Data** | Atribusi WorldPop, ESA WorldCover, Google Open Buildings, Copernicus, USGS Landsat, HDX COD-AB + model card. |

### 4.2 P1 — kalau waktu cukup
Optimasi multi-objektif NSGA-II (Pareto front), peta laporan warga anonim, split-map sebelum/sesudah, ekspor brief ke Google Docs.

### 4.3 Di luar lingkup (sengaja)
- Bukan pengganti CFD/ENVI-met — hasil **indikatif** untuk penyaringan awal.
- Model memprediksi **suhu permukaan (LST)**, bukan suhu udara. Batas ini tampil di UI.
- Tidak membuat angka biaya sendiri.
- Tidak ada autentikasi pengguna, tidak ada multi-kota, tidak ada basis data riwayat selain sesi.

## 5. Persyaratan fungsional per fitur

### F1 — Peta panas & kerentanan
- **FR1.1** Peta memuat GeoJSON 264 kelurahan dari `GET /api/kelurahan` (geometri disederhanakan agar payload wajar).
- **FR1.2** Lapisan default `hvi`. Pengguna bisa ganti ke `lst`, `veg`, `pop`; fill, legenda, judul, dan format tooltip ikut berubah.
- **FR1.3** Palet dan batas kelas persis `design/README.md` §2.
- **FR1.4** Hover kelurahan → outline + tooltip (nama, sub, nilai lapisan). Klik → drawer profil + peta di-pan.
- **FR1.5** Sorotan 5 kelurahan prioritas dari hasil tool agen, dengan penanda bernomor 1–5 di centroid.
- **FR1.6** Sel `lst_quality == "low"` (28 sel) tetap tampil di peta tetapi tidak masuk statistik termal.

### F2 — Chat agen
- **FR2.1** Chat lewat endpoint ADK `/run_sse` dengan streaming.
- **FR2.2** Event tool call di-stream ke UI sebagai blok langkah kerja (nama tool, label, status, durasi).
- **FR2.3** Kartu hasil dirender dari output tool terstruktur, **bukan** dari teks LLM.
- **FR2.4** Agen menolak menulis angka yang tidak berasal dari tool; kalau data tidak ada, agen bilang tidak ada.
- **FR2.5** Routing sub-agen bisa dimatikan lewat env `TEDUH_SINGLE_AGENT=1` (satu `LlmAgent` dengan semua tool).

### F3 — Profil kelurahan
- **FR3.1** `get_area_profile(kel_id)` mengembalikan LST rata-rata, anomali terhadap rata-rata kota (**41,84 °C**, dihitung dari sel `good`), peringkat HVI dari 264, komponen H/E/S/A, NDVI, fraksi pohon/bangunan/air, penduduk, warga rentan.
- **FR3.2** `explain_drivers(kel_id)` mengembalikan 3–5 fitur SHAP teratas dengan arah dan besarnya dalam °C.
- **FR3.3** Jumlah semua kontribusi SHAP + nilai dasar model = prediksi LST kelurahan, dalam toleransi 0,01 °C.

### F4 — Simulasi skenario
- **FR4.1** Intervensi diterjemahkan ke perubahan fitur sesuai CONCEPT §7.5, memakai konstanta dari `config/scenario.yaml`.
- **FR4.2** Kanopi tambahan dibatasi lahan non-bangunan non-air di sel tersebut.
- **FR4.3** Output per kelurahan: ΔLST rata-rata, ΔLST tertimbang penduduk, jumlah warga rentan di sel dengan ΔLST ≤ −0,5 °C, luas (m²), biaya (IDR).
- **FR4.4** Flag `extrapolation: true` kalau fitur hasil skenario melewati persentil 99 data latih.
- **FR4.5** Setiap hasil menyertakan rentang literatur dari `data/evidence/interventions.json`.
- **FR4.6** **Arah fisika dijamin:** menambah pohon atau albedo tidak boleh pernah menaikkan LST.

### F5 — Portofolio anggaran
- **FR5.1** Kandidat = kelurahan × intervensi × level (rendah/sedang/tinggi).
- **FR5.2** Nilai kandidat = `Σ (pop_u5 + pop_65p + λ·pop) × (−ΔLST)`.
- **FR5.3** Solver OR-Tools CP-SAT. Kendala: total biaya ≤ anggaran; maksimal satu level per (kelurahan, intervensi); ≥ `equity_share` (default 0,6) anggaran ke kuintil HVI teratas.
- **FR5.4** Kalau kendala keadilan membuat masalah infeasible, tool mengembalikan penjelasan, bukan exception.

### F6 — Policy brief
- **FR6.1** `policy_writer` menulis draf dengan penanda `[[F:id]]`.
- **FR6.2** `render_policy_brief` menukar penanda dengan nilai + satuan dan membuat catatan kaki sumber.
- **FR6.3** Validator menolak angka di luar penanda. Daftar putih: tahun (19xx/20xx), nomor bagian, nomor peraturan.
- **FR6.4** Kalau validasi gagal, tool mengembalikan daftar error dan agen menulis ulang, maksimal 2 kali.
- **FR6.5** Bagian brief tetap dan berurutan: Ringkasan Eksekutif · Kondisi Panas Wilayah · Kelompok Rentan · Opsi Intervensi & Perkiraan Dampak · Rekomendasi Portofolio & Anggaran · Keterkaitan dengan Dokumen Perencanaan · Keterbatasan · Sumber.
- **FR6.6** Brief **tidak** merender disclaimer "harga ini asumsi" (DECISIONS 2026-10-09), tetapi `source:` tetap dibawa di `facts` agar angka biaya lolos validator.

### F7 — Cek Atap
- **FR7.1** `analyze_roof_photo` memanggil Gemini vision dengan `response_schema` CONCEPT §8.5 (8 field).
- **FR7.2** `recommend_roof_action` **tidak memakai LLM** — murni aturan CONCEPT §8.5.
- **FR7.3** `asbestos_cement` → peringatan keselamatan eksplisit: jangan diamplas, dipotong, atau dibor.
- **FR7.4** `confidence < 0,6` atau `roof_visible: false` → minta foto ulang dengan panduan sudut.
- **FR7.5** EXIF dihapus sebelum foto disimpan; lokasi paling detail setingkat kelurahan; lifecycle GCS 30 hari.

## 6. Persyaratan non-fungsional

| Aspek | Target | Cara ukur |
|---|---|---|
| Model panas | R² ≥ 0,75 pada spatial block CV | `model/train.py` melaporkan per-lipatan; dicatat di `model_card.json` |
| Arah fisika skenario | 100% lulus | `tests/test_scenario.py` |
| Provenance | 100% brief lolos validator | `tests/test_provenance.py` |
| Pemilihan tool | ≥ 90% benar | `tests/eval/golden_questions.yaml` (20 pertanyaan) |
| Cek Atap | `roof_form` ≥ 85%, `material` ≥ 70% | 30 foto berlabel manual di `data/roof_test/` |
| Latensi chat | p50 < 8 detik | diukur pada URL publik |
| Optimasi | kendala anggaran & keadilan 100% terpenuhi | `tests/test_optimize.py` |
| Cold start | `min-instances=1` selama 19 Okt–6 Nov | konfigurasi Cloud Run |
| Cakupan tes | ≥ 80% pada `model/` dan `teduh_agent/` | `pytest --cov` |
| Aksesibilitas | fokus terlihat, tooltip aktif saat focus bukan hanya hover, kontras lolos | audit manual + axe |

## 7. Kondisi data saat ini (sudah ada, jangan dibangun ulang)

Angka berikut adalah **kenyataan di disk**, bukan perkiraan. Gunakan ini, bukan contoh di `design/README.md`.

| Artefak | Isi |
|---|---|
| `data/processed/grid_features.parquet` | 75.636 sel 100 m, 24 kolom. 75.608 `lst_quality=good`, 28 `low`. |
| `data/processed/kelurahan_metrics.parquet` | **264** kelurahan, 32 kolom, termasuk `H,E,S,A,hvi,hvi_rank`. |
| `data/boundaries/kelurahan.geojson` | 264 MultiPolygon, CRS84, properti `kel_id, kel_name, kec_id, kec_name, kota_id, kota_name`. |
| `data/evidence/interventions.json` | 10 entri bukti, semua `verified: true`, 6 jenis intervensi. |
| `config/{scenario,costs,hvi}.yaml` | Semua konstanta berlabel `source:` atau `ASUMSI`. |
| `tests/fixtures/*.parquet` | 3 kelurahan × 173 sel, sengaja punya sebaran kanopi dan HVI. |
| `tests/eval/golden_questions.yaml` | 20 pertanyaan dengan `expected_tools` dan `forbidden_tools`. |

Nilai acuan: rata-rata LST kota **41,8376 °C**. Kode kota: `ID3171` Jakarta Selatan, `ID3172` Jakarta Timur, `ID3173` Jakarta Pusat, `ID3174` Jakarta Barat, `ID3175` Jakarta Utara.

**Koreksi terhadap `design/README.md`:** prototipe desain memakai data contoh fiktif (267 kelurahan, rata-rata kota 34,3 °C, WorldPop 2020, R² 0,78, 5 prioritas di Jakarta Timur). Yang benar: 264 kelurahan, 41,84 °C, WorldPop **2025**, R² diisi dari hasil latih sebenarnya, dan 5 prioritas nyata ada di Jakarta Pusat/Barat (Kampung Rawa, Serdang, Johar Baru, Galur, Krendang). Palet, token, tata letak, dan komponen desain tetap dipakai apa adanya; hanya **angkanya** yang diganti data nyata.

## 8. Risiko yang masih terbuka

| Risiko | Mitigasi yang sudah diputuskan |
|---|---|
| Model korelasional dibaca kausal | Monotonic constraints, label "indikatif", pembanding literatur, flag ekstrapolasi |
| Harga cool roof & green roof masih ASUMSI | Berlabel di YAML, bisa diedit, `verify_costs.py` menjaga yang bersumber |
| Routing multi-agen tidak stabil | Flag `TEDUH_SINGLE_AGENT=1` |
| 0 dari 30 foto uji atap terkumpul | Target akurasi Cek Atap **belum boleh diklaim** sampai 30 foto ada |
| Gemini mengarang angka | Validator provenance memblokir brief |
| Biaya API saat penilaian | Model Flash, batas token per sesi, billing alert |

## 9. Pertanyaan yang harus dijawab pemilik proyek

Tidak boleh ditebak (CLAUDE.md): harga satuan cool roof & green roof dari vendor, region GCP final, nama bucket GCS, apakah 30 foto atap akan dikumpulkan sebelum 15 Okt, dan anggota tim final sebelum 11 Okt.
