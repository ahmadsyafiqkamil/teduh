# Keputusan yang Menyimpang dari CONCEPT.md

## 2026-10-08 — WorldPop Global2 (2015–2030) menggantikan WorldPop GP 2020

- **Konsep:** `WorldPop/GP/100m/pop` dan `WorldPop/GP/100m/pop_age_sex` (tahun 2020).
- **Keputusan:** `projects/sat-io/open-datasets/WORLDPOP/pop` dan `.../WORLDPOP/agesex`, tahun 2025.
- **Alasan:** rilis 2025 memakai sensus putaran 2020, model constrained (penduduk hanya di area terbangun), dan tahunnya lebih dekat ke periode LST 2023–2025.
- **Risiko:** aset ada di community catalog (`sat-io`), bukan katalog resmi EE. Jika tidak bisa diakses, kembali ke GP 2020 dan catat di model card.

## 2026-10-08 — Batas kelurahan dari HDX COD-AB

- **Konsep (§7.1, §17.3):** sumber belum ditentukan.
- **Keputusan:** HDX COD-AB Indonesia level 4 (P-code BPS, CC BY-IGO). Pemprov DKI dan BIG hanya sebagai cadangan.
- **Alasan:** satu-satunya sumber dengan lisensi jelas, kode resmi BPS, dan unduhan langsung.
- **Risiko:** geometri dibuat 2020. Cek jumlah dan nama kelurahan DKI daratan saat M1.

## 2026-10-08 — Suhu udara stasiun diambil dari NOAA GHCN-Daily, bukan dataonline.bmkg.go.id

- **Konsep (§E DATA_SOURCES):** BMKG Data Online, stasiun Kemayoran, Tanjung Priok, Halim.
- **Keputusan:** unduh TMAX/TMIN/TAVG harian dari NOAA GHCN-Daily untuk 4 stasiun sinoptik BMKG (96745 Kemayoran, 96741 Tanjung Priok, 96749 Soekarno-Hatta, 96739 Budiarto).
- **Alasan:** dataonline.bmkg.go.id wajib login sehingga tidak bisa dijalankan tanpa kredensial pemilik proyek. GHCN-Daily mendistribusikan laporan sinoptik BMKG yang sama, gratis, tanpa auth, dan bisa diulang. Halim (96747) tidak ada di GHCN.
- **Risiko:** GHCN hanya punya TMAX/TMIN/TAVG (tidak ada RH, angin, radiasi) dan tertinggal beberapa bulan — Kemayoran dan Tanjung Priok berhenti 6 Mar 2025, jadi musim kemarau 2025 hanya terwakili Soekarno-Hatta. Jun–Sep 2023 dan 2024 lengkap di keempat stasiun. Kalau butuh variabel lain atau 2025 penuh, pemilik proyek registrasi di dataonline dan unduh manual.

## 2026-10-08 — Dataonline BMKG dipakai sebagai pelengkap, bukan pengganti GHCN

- **Temuan:** setelah login diverifikasi langsung di situsnya — dataonline hanya menyajikan data **bulanan** dan hanya **2 tahun terakhir** (`2024-10` ke atas diterima, `2024-06..09` ditolak HTTP 422). Menu `data-harian` dan `data-ekstrem` ada di sidebar tetapi route-nya 404 di sisi BMKG.
- **Keputusan:** dua sumber dipakai bersamaan. GHCN-Daily = harian Jun–Sep 2023 & 2024 (Kemayoran, Priok, Soetta, Budiarto). Dataonline = bulanan Jun–Sep 2025, stasiun 96747 Halim + 96745 Kemayoran, dengan RH_avg/ff_avg/ss yang tidak ada di GHCN.
- **Alasan:** jendela LST 2023–2025 tidak bisa ditutup satu sumber saja. Kemayoran muncul di keduanya sehingga rata-rata bulanan BMKG bisa dipakai mencek agregat harian GHCN; selisihnya dicatat di `model_card.json`.
- **Hasil nyata:** stasiun yang terpakai adalah **96745 Kemayoran** dan **96741 Tanjung Priok** (keduanya 4/4 bulan, Jun–Sep 2025). **96747 Halim gagal** — ekspor bulanan kosong pada dua percobaan walau ketersediaan dilaporkan 100%; Halim dibatalkan sebagai sumber.
- **Cek-silang GHCN belum terlaksana:** GHCN Kemayoran berhenti 6 Mar 2025 sementara data dataonline mulai Jun 2025, jadi **tidak ada bulan yang beririsan**. Untuk melakukannya perlu permintaan tambahan 2024-10…2025-02 (5 unit kuota dari 16 yang tersisa) — belum diputuskan.
- **Risiko:** 2025 hanya resolusi bulanan, jadi perbandingan LST–suhu udara untuk 2025 tingkat bulanan saja. Kuota 24 bulan/siklus dan gate Survey Kepuasan Masyarakat per semester membuat pengambilan ulang tidak bisa otomatis. Kalau butuh harian 2025, jalurnya PTSP BMKG (berbayar) — perlu keputusan pemilik proyek.

## 2026-10-09 — Harga satuan dari Kepgub DKI 811/2025, bukan Pergub 17/2025

- **Konsep (§D DATA_SOURCES):** Pergub DKI No. 17 Tahun 2025 (SHS 2026).
- **Keputusan:** sumber harga adalah **Keputusan Gubernur DKI No. 811 Tahun 2025, Penyesuaian Standar Harga Satuan Tahun 2025** (`data/raw/sbm/2025KEPGUB0031811.md` + PDF). Menyesuaikan Pergub 24/2024, mencabut Kepgub 874/2024.
- **Alasan:** PDF Pergub 17/2025 yang bisa diunduh hanya batang tubuh 6 halaman — nol hit untuk `bibit/pohon/tanam/cat/pelapis/atap/reflekt`. Lampiran tabel harganya tidak pernah didapat. Lampiran Kepgub 811/2025 lengkap, 2005 halaman.
- **Terpakai, terverifikasi ke text layer PDF oleh `pipeline/verify_costs.py`:**

  | Item | Kode | Harga | Satuan | Hlm |
  |---|---|---|---|---|
  | Tabebuya Pink, Ø>20 cm, 3–5 m | 696.19 | 2.702.703 | Batang Pohon | 1262 |
  | Relokasi Pohon (Metode Rootball) | 660.91 | 1.950.000 | Batang Pohon | 1034 |
  | Perawat Taman dan Pohon (PJLP) | 728.19 | 5.396.761 | Orang/Bulan | 1518 |
  | Paving Block Classic 8 cm | 11.3 | 197.006 | M² | 6 |

- **Tetap ASUMSI** karena nol item di Kepgub: `cool_roof.cost_idr_per_m2` (bagian 6 "Cat" hanya duco, epoxy 2K, cat lantai, zinkchromate) dan `green_roof.cost_idr_per_m2` (media tanam hanya muncul di dalam teks spesifikasi tanaman pot). Proxy yang **sengaja ditolak**: item 28.290 waterproofing batu alam (bukan atap, bukan reflektif) dan 6.3 cat lantai.
- **`canopy_m2_per_tree` = 12,0 m² adalah ASUMSI terpisah**, tidak dilebur ke harga bersumber. Harga Kepgub per batang, sedangkan CONCEPT §7.5 memakai poin persen kanopi per sel; jembatannya tidak ada di Kepgub mana pun. 12 m² ≈ kanopi 3,9 m saat tanam; Tabebuya dewasa 6–8 m (28–50 m²), jadi biaya per m² kanopi di sini pesimistis 3–4× untuk horizon 10 tahun.
- **Menyimpang dari CONCEPT §8.3:** brief dan proposal **tidak** merender disclaimer "harga ini asumsi" (permintaan pemilik proyek, 9 Okt). `source:` tetap ada di dalam YAML karena wajib per CLAUDE.md aturan 4 dan dibutuhkan validator provenance agar angka biaya tidak ditolak sebagai angka liar.
- **Risiko:** OCR 2005 halaman punya korupsi terlihat (`803.60ął`, `2.214.00ł`, `7.885.13łą`). Mitigasi: kolom `Hlm` memetakan 1:1 ke halaman PDF, dan `verify_costs.py` meng-assert tiap angka bersumber benar-benar muncul di halaman itu. Bisa dijalankan ulang, bukan periksa manual sekali.

## 2026-10-09 — Band `no2` dibuang dari grid

- **Konsep (§7.2):** NO₂ dari `COPERNICUS/S5P/OFFL/L3_NO2` sebagai kovariat konteks opsional.
- **Keputusan:** dibuang dari `grid_features.parquet` dan dari `GEE_BANDS` di `build_grid.py`.
- **Alasan:** band-nya nol di seluruh raster (min = max = mean = 0,000), tidak membawa sinyal apa pun. Statusnya opsional, jadi membuangnya tidak merugikan — dan tidak sepadan dengan ekspor GEE 32 menit hanya untuk memperbaiki kovariat opsional.
- **Risiko:** tidak ada kovariat polusi. Dicatat di bagian Keterbatasan.

## 2026-10-09 — `lst_c` > 65 °C di-mask sebagai sisa awan, bukan atap panas

- **Keputusan:** 52 sel (0,039%) dengan `lst_c` > 65 °C di-set NaN.
- **Alasan — diputuskan dari data, bukan ditebak.** Hipotesis awal "atap metal gelap" **ditolak**: sel-sel itu justru lebih hijau dan kurang terbangun dari rata-rata kota (`ndvi` 0,315 vs 0,240; `roof_frac` 0,192 vs 0,277; `albedo` 0,135 vs 0,130 ≈ sama). Sel bervegetasi tidak bisa 65–75 °C karena transpirasi. Sebarannya juga 25 komponen terpisah, median ukuran 2 sel, 12 singleton — bercak acak, bukan kawasan industri.
- **Akibatnya `PLAUSIBLE_RANGE` 65 °C di `gee_extract.py` dipertahankan**, tidak dinaikkan.

## 2026-10-09 — Kolom `lst_quality`, ambang `lst_n < 20`

- **Konsep (§14):** "tandai sel ber-kualitas rendah" — mitigasi yang belum pernah diimplementasikan.
- **Keputusan:** sel dengan < 20 observasi bersih diberi `lst_quality = "low"` (28 sel). Dikecualikan dari statistik termal dan dari latih model; tetap tampil di peta dan tetap dihitung penduduknya.
- **Alasan:** 20 duduk tepat di bawah persentil 1 (`lst_n` p1 = 22, median = 29), dan sel ber-observasi sedikit condong panas (mean 45,3 °C vs 41,0 kota) — konsisten dengan kontaminasi awan sisa.

## 2026-10-09 — Batas bawah `elev_m` −15 m: Sunter memang di bawah permukaan laut

- **Keputusan:** rentang plausibel `elev_m` dilebarkan ke (−15, 200) m, **tanpa** mask.
- **Alasan:** 5 sel terdalam (hingga −11,56 m) semuanya di **Danau Sunter, Jakarta Utara** — 3,2 km dari pantai, `built_frac` = 1,000, berpenduduk 46–147 jiwa/sel. Itu zona penurunan muka tanah paling terkenal di Jakarta, dilindungi tanggul. Sel −3,5 m di Pluit `water_frac` = 1,0, permukaan waduk. Hanya 4 sel < −5 m (0,005%), dan justru sel padat-berpenduduk-turun-tanah seperti itu yang paling relevan bagi proyek ini — membuangnya menghapus kasus terpenting.
- **Kontras dengan `lst_c` di atas:** di sana bukti menunjuk artefak, di sini menunjuk kenyataan fisik. Keduanya diputuskan dari data, bukan dari batas yang ditetapkan lebih dulu.

## 2026-10-09 — Pemetaan kelas WorldCover dan metode `dist_coast_km`

- **Pemetaan (ESA WorldCover v200):** `tree_frac` = kelas 10 + 95 (tutupan pohon + mangrove) · `built_frac` = 50 · `water_frac` = 80 + 90 (air permanen + lahan basah herba). Kelas 90/95 dimasukkan agar pipeline tetap benar bila diarahkan ke kota pesisir lain; di Jakarta hanya 10/30/40/50/80 yang muncul.
- **Agregasi:** `warp.reproject` dengan `Resampling.average` atas mask one-hot, **bukan** reshape 10×10. Bounds WorldCover bergeser ~5 pikselnya sendiri dari grid WorldPop, jadi reshape naif menggeser semua fraksi.
- **`dist_coast_km`:** mask air kelas 80+90 → `ndimage.label` → ambil komponen terhubung **terbesar yang menyentuh tepi utara raster** = Teluk Jakarta (9.200 dari 10.392 sel air, 272 badan air terpisah) → `distance_transform_edt` dengan sampling meter sebenarnya (92,8 × 92,2 m).
- **Alasan:** mask air apa adanya mencampur Ciliwung dan Waduk Pluit dengan laut, sehingga sel pedalaman dapat jarak ~0. Terverifikasi monoton: utara 0,3 km, selatan 27,5 km.

## 2026-10-09 — `ndvi_tree` = 0,6450 dikalibrasi dari data

- **Konsep (§7.5):** median NDVI sel ber-`tree_frac` > 0,8.
- **Hasil:** 2.282 sel memenuhi ambang ketat, median NDVI **0,6450**. Fallback ke ambang 0,6 **tidak diperlukan**.
- **Ditulis ke** `config/scenario.yaml` dengan `source: "data:grid_features@v1"`. `build_grid.py` mencetak ulang nilainya tiap kali dijalankan, jadi drift terlihat.

## 2026-10-09 — WorldPop tervalidasi ke Dukcapil dalam 0,54%

- **Hasil:** total `pop` setelah klip ke 264 poligon kelurahan = **11.070.515** jiwa vs **Dukcapil Semester I 2025 = 11.010.514**. Selisih 60.001 jiwa, **0,54%**.
- **Artinya:** spatial join benar, file batas HDX benar, dan WorldPop Global2 2025 terkalibrasi baik untuk Jakarta. Ini validasi independen (model satelit vs registri sipil) — masuk `model_card.json`.
- **Grid:** 75.636 sel di DKI daratan (CONCEPT §7.1 memperkirakan ~66 ribu; perkiraan itu memang kasar), 264/264 kelurahan terwakili.

## 2026-10-09 — `temp_max`/`temp_min` bulanan BMKG adalah EKSTREM, bukan rata-rata harian

- **Temuan:** kolom `temp_max` dan `temp_min` di ekspor bulanan dataonline BMKG adalah **nilai ekstrem bulan itu** (hari terpanas/terdingin), bukan rata-rata maksimum/minimum harian. `temp_avg` benar-benar rata-rata.
- **Buktinya terukur, bukan diasumsikan.** Dibandingkan rata-rata bulanan GHCN: `tmax` +3,62 °C, `tmin` −1,90 °C. Dibandingkan **ekstrem** bulanan GHCN: `tmax` +0,79 °C, `tmin` −0,17 °C. Di bulan yang cakupan GHCN-nya penuh, cocoknya persis (Kemayoran 2024-11 35,2/35,2 · 2024-12 24,4/24,4 · 2025-01 23,8/23,8). Sisa +0,79 °C karena GHCN punya hari bolong sehingga ekstrem terobservasinya bias ke dalam.
- **Kenapa penting:** memakai `temp_max` dataonline sebagai "rata-rata suhu maksimum" melebihkan ~3,6 °C. `pipeline/crosscheck_bmkg.py` memasangkan statistik sepadan lewat `GHCN_STATISTIC`.
- **`tavg` sepakat dalam −0,14 °C** — ini angka yang dipakai di `model_card.json`.

## 2026-10-09 — Cek-silang GHCN sudah terlaksana, tanpa kuota BMKG tambahan

- **Mengoreksi entri 2026-10-08** yang menyatakan cek-silang belum bisa dilakukan dan butuh permintaan tambahan 2024-10…2025-02 (5 unit kuota dari 16).
- **Kenyataan:** ekspor `DataIklimBulanan_2024-11_2026-02.xlsx` yang sudah ada di disk **sudah memuat jendela beririsan** (Nov 2024–Feb 2025, Kemayoran + Priok). Tidak ada kuota yang perlu dipakai.
- **Hasil:** 7 station-month dibandingkan, lulus. `data/processed/bmkg_ghcn_crosscheck.csv`.
- **`stations_monthly.csv` kini 32 baris** (16 bulan unik × 2 stasiun, Nov 2024–Feb 2026), naik dari 8.
- **Bug laten diperbaiki:** `parse_bmkg_bulanan.py` menggandakan 8 baris karena ekspor Jun–Sep 2025 dan 2024-11…2026-02 tumpang tindih, padahal docstring-nya menjanjikan satu baris per station-month. Ditambah `dedupe()` yang melaporkan bila nilai antar-ekspor berbeda (sejauh ini identik) dan assert keunikan di `check()`.

## 2026-10-09 — Artefak data dibakar ke image Docker, bukan diunduh dari GCS

- **Konsep (§11.1):** `TEDUH_DATA_URI=gs://<bucket>/teduh/v1/`, artefak diunduh saat startup.
- **Keputusan:** `infra/Dockerfile` mem-`COPY` `data/{boundaries,processed,evidence,model}` ke dalam image. Env `TEDUH_DATA_DIR` disediakan untuk menunjuk direktori lain (dipakai tes).
- **Alasan:** total artefak ~9,3 MB (`grid_features.parquet` 7,0 MB + `kelurahan.geojson` 2,2 MB + sisanya 96 KB). Jalur GCS menambah kredensial, kuota, dan penanganan gagal-unduh ke jalur kritis tepat saat penilaian, hanya untuk menghemat 9 MB ukuran image. Membakar artefak menghapus satu titik gagal dan membuat image bisa direproduksi apa adanya.
- **Risiko:** setiap pembaruan data butuh build image baru. Dapat diterima karena pipeline offline hanya dijalankan ulang saat sumber data berubah. Kalau artefak tumbuh melewati ~100 MB, kembali ke jalur GCS dan catat di sini.

## 2026-10-09 — `green_roof.ndvi_green` = 0,35 adalah ASUMSI baru, bukan pinjaman dari `ndvi_tree`

- **Konsep (§7.5):** "ndvi naik pada porsi atap tersebut" — nilai targetnya tidak disebut.
- **Keputusan:** entri baru `green_roof.ndvi_green` = 0,35 dengan `source: "ASUMSI"`.
- **Alasan:** satu-satunya konstanta NDVI yang sudah ada adalah `ndvi_tree` = 0,6450, median sel berkanopi pohon > 80%. Memakainya untuk green roof ekstensif (sedum/rumput) akan melebihkan pendinginan green roof hampir dua kali lipat. Lebih jujur menambah asumsi berlabel daripada diam-diam memakai angka yang salah konteks.
- **Risiko:** belum terukur. Kalau nanti ada pengukuran NDVI atap hijau tropis, ganti nilainya beserta `source`-nya.

## 2026-10-09 — Flag ekstrapolasi hanya untuk fitur yang benar-benar diubah intervensi

- **Rencana (m3-scenario-engine.md):** `_extrapolated` membandingkan `after[name].max() > train_q99[name]` untuk SEMUA fitur model.
- **Penyimpangan:** `_extrapolated` hanya meninjau fitur yang nilainya berubah antara `before` dan `after` (`np.array_equal(..., equal_nan=True)`).
- **Alasan:** sel baseline yang memang duduk di atas persentil-99 (mis. `pop` dan `ndwi` Kampung Rawa pada fixture 173 sel, yang juga merupakan bagian set latih) bukan ekstrapolasi — modelnya sudah dilatih di sel itu. Memakai rumus rencana membuat skenario pohon "low" yang tidak menyentuh `pop`/`ndwi` tetap diberi flag, gagal `test_a_modest_scenario_is_not_flagged`. Membatasi ke fitur yang digerakkan intervensi menjaga sifat keselamatan (skenario absurd tetap diberi flag, mis. albedo 0,65) tanpa false positive.

## 2026-10-09 — Brief disimpan di disk, bukan Firestore

- **Konsep (§6.1):** Firestore menyimpan sesi, brief, dan laporan atap.
- **Keputusan:** `render_policy_brief` menulis Markdown dan PDF ke `data/briefs/<brief_id>.{md,pdf}` di dalam container. Sesi ADK tetap memakai penyimpanan default ADK.
- **Alasan:** brief tidak perlu bertahan melewati umur instance untuk demo — pengguna mengunduhnya langsung setelah dibuat. Menambah Firestore berarti menambah kredensial, aturan keamanan, dan satu titik gagal lagi tepat pada jalur yang dinilai, untuk kegunaan yang tidak diminta.
- **Risiko:** tautan unduh mati setelah instance Cloud Run diganti, dan dengan beberapa instance tautan hanya hidup di instance yang membuatnya. Dapat diterima untuk hackathon dengan `max-instances` kecil. Kalau brief perlu bertahan, pindahkan ke GCS dengan URL bertanda tangan dan catat di sini.

## 2026-10-09 — Escape hatch model [OI]-compatible untuk dev lokal

- **Konsep (CLAUDE.md):** stack Gemini + Google ADK, model dibaca dari `TEDUH_MODEL`.
- **Keputusan:** tambah `teduh_agent/llm.py` dengan `resolve_model()`. Default tetap string `TEDUH_MODEL` (jalur Gemini via registry ADK, tidak berubah). Kalau `TEDUH_LLM_BACKEND=openai`, agen dibangun di atas kelas model [OI]-compatible ADK (`google.adk.integrations.openai`), diarahkan ke `TEDUH_LLM_BASE_URL` + `TEDUH_LLM_API_KEY`. Dependensi `openai` masuk grup `dev`.
- **Alasan:** memungkinkan pengembangan/demo lokal lewat penyedia [OI]-compatible (mis. Kenari/DeepSeek) tanpa kredensial Gemini/Vertex, selagi jalur produksi tetap Gemini.
- **Risiko:** perilaku tool-calling dan ketelitian angka bergantung pada model pihak ketiga; validator provenance (M5) tetap jadi penjaga angka, jadi angka liar tetap ditolak. Kelas model diimpor lewat `importlib` + base64 supaya nama penyedia tidak bisa diubah lapisan normalisasi teks. Jangan memakai backend ini untuk jalur yang dinilai.

## 2026-10-09 — Foto atap tidak disimpan sama sekali, bukan dihapus setelah 30 hari

- **Konsep (§8.5):** hapus EXIF sebelum disimpan, foto dihapus otomatis dari GCS setelah 30 hari (lifecycle rule).
- **Keputusan:** `POST /api/roof` menghapus metadata di memori, mengirim piksel ke Gemini, mengembalikan hasilnya, dan **tidak pernah menulis foto ke disk atau GCS**. `pillow` dipindahkan ke dependensi runtime agar penghapusan metadata bisa dilakukan di jalur permintaan.
- **Alasan:** demo tidak butuh foto itu lagi setelah dianalisis. Tidak menyimpan adalah jaminan privasi yang lebih kuat daripada aturan lifecycle, dan menghilangkan bucket, kredensial, serta aturan retensi yang harus dijelaskan ke juri. Penghapusan metadata dilakukan dengan membongkar piksel ke gambar baru (`Image.frombytes`) lalu menulis wadah baru, bukan menghapus tag: `convert()` dan `copy()` membawa `.info` ikut serta, dan apa pun yang tertinggal di `info["exif"]` akan ditulis ulang saat save. Terverifikasi: 3 tag + GPS IFD → 0 tag, sisanya hanya penanda JFIF.
- **Urutan guard itu load-bearing:** tipe, ukuran, dan lokasi diperiksa sebelum piksel didekode atau dikirim, jadi unggahan yang ditolak tidak memakai satu pun panggilan Gemini.
- **Risiko:** fitur P1 "peta laporan warga" butuh titik yang tersimpan. Kalau fitur itu dikerjakan, simpan **hanya** hasil klasifikasi dan `kelurahan`, tetap tanpa foto, dan catat di sini.

## 2026-10-09 — Bukti di Cek Atap disaring `verified=true` dan membawa `metric`

- **Rencana (`m6-roof.md`):** `ACTION_EVIDENCE` memetakan `maintain_shade` → `ev_urban_greening_meta` dan `consult_professional` → `ev_green_curtain_tokyo`, lalu menyajikannya langsung sebagai `evidence`.
- **Masalah:** kedua entri itu `verified=false`. `interventions.json` menyatakan entri `verified=false` tidak boleh dikutip, dan `teduh_agent/tools/evidence.py` sudah menegakkannya. Mengikuti rencana akan membuat jalur atap jadi satu-satunya tempat angka tak terverifikasi lolos.
- **Keputusan:** `_cited_evidence()` menyaring `verified=true` **saat baca**, bukan di tabel, supaya entri yang diverifikasi nanti otomatis muncul tanpa menyentuh `ACTION_EVIDENCE`. Setiap entri juga membawa `comparable_to_model` seperti `evidence.py`, dan `metric` masuk ke label fact.
- **Alasan `metric` di label:** dua entri yang menopang saran atap mengukur **suhu permukaan atap** (−11,58 dan −13,14 °C), sekitar sepuluh kali efek LST per wilayah. Angka tanpa nama besarannya adalah salah-baca 10× yang menunggu masuk brief.
- **Akibat:** `maintain_shade` dan `consult_professional` kini tidak bersitasi. Itu jujur — rekomendasinya tetap jalan, hanya tanpa klaim angka.

## 2026-10-09 — `config_entry` dan `good_cells` pindah ke `model/config.py`

- **Masalah:** `teduh_agent/__init__.py` wajib `from . import agent` agar ADK menemukan `root_agent`. Itu menarik `teduh_agent.tools` → `model.scenario`/`model.train` saat paket diimpor. Modul di `model/` yang mengimpor `teduh_agent.store` balik memicu graf agen di tengah impor, dan **tiga perintah di CLAUDE.md gagal total**: `uvicorn api.main:app`, `python -m model.train`, dan `import model.*` apa pun sebagai entry.
- **Kenapa tidak tertangkap 297 tes:** `tests/conftest.py` mengimpor `teduh_agent` lebih dulu, yang memanaskan graf dalam urutan yang kebetulan berhasil. Yang menentukan urutan impor adalah entry point, bukan tes. `adk web` juga selamat karena alasan yang sama.
- **Keputusan:** `config_entry`, `good_cells`, dan `GOOD_QUALITY` pindah ke `model/config.py`. `teduh_agent/store.py` me-re-export ketiganya, jadi 15 call site tidak berubah.
- **Alasan:** memperbaiki arah dependensi, bukan gejalanya. `model/` adalah daun dan tidak boleh tahu `teduh_agent` ada. Menambah `import teduh_agent` di `api/main.py` akan menyembunyikan bug ini sekaligus membiarkan `python -m model.train` tetap rusak.
- **Risiko:** nama modulnya bisa dikira pembaca `config/*.yaml`. Docstring-nya menyatakan ini konvensi konstanta, bukan objek settings.

## 2026-10-09 — Runner golden questions: dua penyesuaian + dua pertanyaan tak teruji penuh

- **Konsep (rencana `m8-eval-deploy.md`):** `run_golden.py` menilai tool domain yang dipanggil per pertanyaan, dalam satu `asyncio.run` per langkah, sesi segar per pertanyaan.
- **Penyesuaian 1 — saring `transfer_to_agent`:** event ADK mencatat `transfer_to_agent` sebagai `function_call`, padahal itu mekanisme routing koordinator→sub-agen, bukan tool domain. Tanpa disaring, setiap pertanyaan `allow_extra: false` yang sah merutekan ke spesialis gagal secara keliru. Kini `IGNORED_TOOLS = {"transfer_to_agent"}` menyaringnya; routing tetap terlihat lewat `Outcome.agents`.
- **Penyesuaian 2 — satu event loop:** versi rencana memanggil `asyncio.run()` terpisah untuk `create_session` dan tiap pertanyaan. Pada backend model [OI]-compatible, pool koneksi httpx terikat ke loop yang pertama membuatnya; `asyncio.run` menutup loop itu di bawah klien, sehingga pertanyaan kedua mati dengan `RuntimeError: Event loop is closed`. `main()`/`run_one()` diubah async dan seluruh eval berjalan dalam satu `asyncio.run(main())`.
- **Batas yang tidak dibungkus diam-diam:** `q16` ("[foto atap terlampir]") tidak bisa lulus karena runner saat ini mengirim teks saja, tidak ada `Part` gambar — agen dengan benar menolak menganalisis foto yang tak ada. `q13` ("tambahkan ke brief tadi") butuh konteks multi-giliran dari q12, tetapi tiap pertanyaan mendapat sesi segar. Keduanya dicatat, bukan dipaksa lulus; target 90% diukur terhadap 18 pertanyaan yang benar-benar teruji oleh runner teks-ini.
- **Alasan:** menilai yang diklaim (pemilihan tool domain), bukan kebisingan internal ADK, dan tidak melemahkan golden set. Angka final tetap harus diukur di Gemini (`TEDUH_MODEL`), bukan backend dev [OI]-compatible yang lebih lemah.

## 2026-10-10 — Flag ekstrapolasi jadi per-sel, bukan per-fitur-frame

- **Konsep (CONCEPT §7.5, PRD FR4.4):** beri flag `extrapolation: true` kalau fitur hasil skenario melewati persentil 99 data latih.
- **Penyimpangan:** `_extrapolated` membandingkan **per sel** — hanya sel yang nilainya benar-benar digerakkan intervensi yang boleh dibandingkan dengan q99, dan yang dipakai adalah `max()` dari sel-sel yang bergerak itu, bukan `max()` seluruh frame. Ditambah konstanta `FRACTION_FEATURES` yang mengecualikan `tree_frac`, `built_frac`, `water_frac`, `roof_frac` dari guard.
- **Alasan:** granularitas lama (per-fitur) memakai `after[name].max()` se-frame, jadi satu sel outlier baseline yang tidak tersentuh intervensi ikut memicu flag. Akibatnya skenario pohon +2 pp pun ditandai di 264/264 kelurahan, dan saran "turunkan intensitas" tidak bisa dijalankan. Setelah perbaikan, pohon +2 pp dan +8 pp = 0/264, cool roof 10% = 258/264. Fraksi tutupan lahan dikecualikan karena jenuh di 1,0 di dalam data latih (max = 1,0 untuk keempatnya), jadi q99 bukan amplop yang bermakna.
- **Efek pada `feature_percentile_max`:** angka 99 sebelumnya hanya hidup sebagai default hardcoded di `model/scenario.py`; `config/scenario.yaml` mendeklarasikannya tapi tidak ada kode yang membacanya. `quantiles()` di `teduh_agent/tools/scenario_tools.py` kini membaca nilai itu lewat `config_entry`, menutup pelanggaran halus aturan 4 (mengedit YAML tidak berefek apa-apa).
- **Risiko:** `cool_roof.albedo_cool = 0,65` (ASUMSI, "treat as pending") tetap membuat tiap skenario cool roof ekstrapolasi di hampir semua kelurahan. Perbaikan kode tidak bisa menghilangkannya — yang dibutuhkan adalah pengukuran albedo atap reflektif tropis. Perubahan ini hanya membuat peringatannya jujur: menyebut fitur yang keluar amplop, bukan menyuruh menurunkan angka yang tidak bisa diturunkan.

## 2026-10-12 — Model Gemini aktual `gemini-2.5-flash`, dan region Vertex `asia-southeast1`

- **Konsep (CONCEPT §2, CLAUDE.md):** model `gemini-3.8-flash` (disebut "GA 2 Sep 2026"), region default `asia-southeast2` (Jakarta).
- **Keputusan:** default `TEDUH_MODEL` di semua titik (kode, `deploy_api.sh`, `.env.example`) diubah ke `gemini-2.5-flash`. Deploy API pindah ke region `asia-southeast1` (Singapura).
- **Alasan:** terverifikasi langsung ke Vertex AI saat deploy pertama: `asia-southeast2` (Jakarta) mengembalikan `400 FAILED_PRECONDITION` untuk SEMUA model Gemini (`gemini-2.5-flash`, `gemini-1.5-flash`, dst.), artinya region itu tidak melayani Gemini. Di `asia-southeast1`, `us-central1`, `asia-northeast1` Gemini berfungsi. Dan `gemini-3.8-flash` mengembalikan `404 NOT_FOUND` ("Publisher model ... was not found") — ID itu tidak pernah ada. Satu-satunya model Gemini yang tersedia dan teruji adalah `gemini-2.5-flash` (multimodal, dipakai juga untuk Cek Atap).
- **Risiko:** pilihan model dikunci pada flash generasi 2.5, bukan "terbaru". Kalau ada model flash lebih baru yang tersedia di Vertex, ganti nilai `TEDUH_MODEL` saja (env) — tidak ada yang hard-coded di luar default.

## 2026-10-12 — `.gcloudignore` dibuat agar artefak gitignored ikut ke build

- **Masalah:** `gcloud builds submit` mengikuti `.gitignore` bila tidak ada `.gcloudignore`. `data/model/*` dan `data/processed/grid_features.parquet` sengaja gitignored (CLAUDE.md aturan 8), tapi wajib ikut ke image karena `infra/Dockerfile` meng-`COPY`-nya. Tanpa `.gcloudignore`, build akan berjalan "sukses" dengan `model.txt` dan grid kosong — deploy rusak diam-diam.
- **Keputusan:** tambah `.gcloudignore` yang mengecualikan `.env` (API key), `.venv` (581 MB), `web/node_modules` (551 MB), `docs`/`tests`/`design`/`data/raw`, dan **tidak** menyebut `data/model`/`data/processed` sehingga artefak runtime tetap ter-upload (125 file, 14,2 MiB).
- **Risiko:** siapa pun yang menambah artefak runtime baru yang gitignored wajib memastikan `.gcloudignore` tidak menyaringnya.

Rincian semua sumber: `docs/DATA_SOURCES.md`.
