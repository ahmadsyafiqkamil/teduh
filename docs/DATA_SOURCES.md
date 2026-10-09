# TEDUH — Sumber Data

Unduh semua data tanpa login (batas, WorldPop, WorldCover, DEM, Pergub) ke `data/raw/` + `data/boundaries/`:
`uv run --no-project --python 3.12 --with geopandas --with pyogrio --with rasterio python pipeline/fetch_public.py` (~1,5 GB diunduh, ~220 MB disimpan).

Katalog dataset untuk M1 (pipeline) dan halaman "Tentang & Sumber Data". Diriset 8 Okt 2026, diperbarui 9 Okt 2026. Kolom **Peran**: `fitur` = masuk `grid_features.parquet`, `batas` = unit kebijakan, `validasi` = pembanding saja, `config` = konstanta di `config/*.yaml`.

## Artefak olahan (sudah ada, M1 selesai)

| Artefak | Isi | Dibuat oleh |
|---|---|---|
| `data/processed/grid_features.parquet` | **75.636 sel** 100 m di DKI daratan, 264/264 kelurahan. 7 MB, **tidak di-commit** (regenerable). | `pipeline/build_grid.py` |
| `data/processed/kelurahan_metrics.parquet` | 264 kelurahan: HVI + komponen H/E/S/A, LST rata-rata & tertimbang penduduk, warga rentan terpapar. 81 KB, **di-commit**. | `pipeline/aggregate_kelurahan.py` |
| `data/processed/bmkg_ghcn_crosscheck.csv` | 7 station-month pembanding BMKG ↔ GHCN. | `pipeline/crosscheck_bmkg.py` |
| `tests/fixtures/*_sample.parquet` | 173 sel, 3 kelurahan rentang kanopi 0,000–0,495 dan HVI 0,002–0,931. | `pipeline/make_fixtures.py` |
| `config/{hvi,scenario,costs}.yaml` | Konstanta berlabel sumber. | manual + `verify_costs.py` |
| `data/evidence/interventions.json` | 10 entri bukti, 4 terverifikasi. | manual, lihat §F2 |

**Validasi silang paling kuat:** total penduduk grid **11.070.515** jiwa vs **Dukcapil Sem-I 2025 11.010.514** → selisih **0,54%**. Model satelit dan registri sipil bertemu, jadi spatial join dan file batas terkonfirmasi benar.

Keputusan dan temuan selama pengolahan: `docs/DECISIONS.md`.

## A. Earth Engine (dipakai hanya di `pipeline/`)

| Variabel | EE ID | Resolusi | Periode | Lisensi | Peran | Catatan |
|---|---|---|---|---|---|---|
| LST, albedo | `LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2` | 30 m | Jun–Sep 2023–2025 | Publik (USGS) | fitur/target | Lihat CONCEPT §7.2 untuk skala & mask awan. |
| NDVI, NDBI, NDWI | `COPERNICUS/S2_SR_HARMONIZED` + `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | 10 m | sama dengan LST | Copernicus | fitur | |
| Tutupan lahan | `ESA/WorldCover/v200` | 10 m | 2021 | CC-BY 4.0 | fitur | |
| Bangunan (tinggi, kehadiran) | `GOOGLE/Research/open-buildings-temporal/v1` | 4 m | **2016–2023 saja** (ambil 2023) | CC-BY 4.0 / ODbL | fitur | `building_presence` tidak terkalibrasi; hanya untuk ambang (mis. > 0,5). |
| Penduduk total | `projects/sat-io/open-datasets/WORLDPOP/pop` | ~100 m | 2015–2030 (ambil 2025) | CC-BY 4.0 | fitur, HVI | WorldPop Global2 R2024B, constrained. Menggantikan `WorldPop/GP/100m/pop` (2020). |
| Penduduk per usia/jenis kelamin | `projects/sat-io/open-datasets/WORLDPOP/agesex` | ~100 m | 2015–2030 (ambil 2025) | CC-BY 4.0 | HVI | R2025A; kelompok 0–1, 1–4, lalu 5-tahunan s.d. 90+. `pop_u5` = 0–1 + 1–4; `pop_65p` = 65+. |
| Elevasi | `COPERNICUS/DEM/GLO30` | 30 m | — | Copernicus | fitur | |
| ~~NO₂~~ | ~~`COPERNICUS/S5P/OFFL/L3_NO2`~~ | ~~1 km~~ | — | — | **GAGAL — dibuang** | Band kembali **nol di seluruh raster** (min=max=mean=0). Tidak dipakai di `grid_features.parquet`. Lihat `docs/DECISIONS.md`. |

Katalog: [Open Buildings Temporal](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1) · [WorldPop 2015–2030 (community catalog)](https://gee-community-catalog.org/projects/worldpop/)

## B. Batas kelurahan

| Prioritas | Sumber | Isi | Lisensi | Catatan |
|---|---|---|---|---|
| 1 | [HDX COD-AB Indonesia](https://data.humdata.org/dataset/cod-ab-idn) | Admin 0–4 (81.912 desa/kelurahan), P-code BPS | CC BY-IGO | Geometri 2020, ditinjau Okt 2025. Filter DKI, buang Kab. Kepulauan Seribu, cek jumlah kelurahan daratan. |
| 2 | ArcGIS REST Pemprov DKI (Dinas Citata) | Batas kota/kecamatan/kelurahan, koordinasi 2021, basemap 1:1000 | Belum jelas | Pembanding geometri bila HDX bermasalah. |
| 3 | [BIG geoservices](https://geoservices.big.go.id/rbi/rest/services/Hosted/Wilayah_Administrasi_Kabupaten__Kota/FeatureServer/layers) | Batas administrasi RBI | Belum jelas | Cadangan. |
| — | Fallback (CONCEPT §12) | Kecamatan atau grid 1 km | — | Jika ketiganya gagal. |

## C. Penduduk resmi (validasi WorldPop)

- **Dukcapil DKI**, Semester I 2025: 11.010.514 jiwa. Agregat sampai RW lewat platform "Dariku Untukmu"/"PRODUK RW". ([Berita Jakarta](https://www.beritajakarta.id/en/read/61194/jakarta-population-recorded-at-1101-million))
- **Satu Data Jakarta** ([satudata.jakarta.go.id](https://satudata.jakarta.go.id)): dataset penduduk per kelompok usia & jenis kelamin.
- Pemakaian: bandingkan total WorldPop 2025 per kota administrasi dengan Dukcapil; catat selisihnya di `model_card.json`.

## D. Harga satuan (`config/costs.yaml`)

**Sumber yang terpakai: Keputusan Gubernur DKI No. 811 Tahun 2025 — Penyesuaian Standar Harga Satuan Tahun 2025.** Menyesuaikan Pergub 24/2024, mencabut Kepgub 874/2024.

- OCR: `data/raw/sbm/2025KEPGUB0031811.md` (2005 hlm, tabel markdown `Kode | Spesifikasi | Satuan | Harga satuan (Rp) | Hlm`)
- PDF: `data/raw/sbm/2025KEPGUB0031811.pdf` — punya text layer, dan kolom `Hlm` memetakan **1:1 ke nomor halaman PDF**.

> **Pergub 17/2025 (SHS 2026) tidak terpakai.** PDF yang bisa diunduh dari JDIH hanya batang tubuh 6 halaman — nol hit untuk `bibit/pohon/tanam/cat/pelapis/atap/reflekt`. Lampiran tabel harganya tidak ikut. Kalau lampirannya didapat nanti, ia lebih mutakhir (tahun anggaran 2026) dan sebaiknya menggantikan Kepgub 811/2025.

### Item yang terpakai (terverifikasi ke text layer PDF)

| Item | Kode | Harga (Rp) | Satuan | Hlm | Untuk |
|---|---|---|---|---|---|
| Tabebuya Pink, Ø>20 cm, tinggi 3–5 m | `696.19` | 2.702.703 | Batang Pohon | 1262 | `tree_planting` — pohon peneduh dewasa, satu-satunya di dokumen |
| Relokasi Pohon (Metode Rootball) | `660.91` | 1.950.000 | Batang Pohon | 1034 | **proxy** upah tanam; relokasi ≠ tanam baru, tapi satu-satunya operasi pohon berat yang bersumber |
| Perawat Taman dan Pohon (PJLP) | `728.19` | 5.396.761 | Orang/Bulan | 1518 | biaya operasional, bukan modal |
| Paving Block Classic 8 cm | `11.3` | 197.006 | M² | 6 | cool pavement (P1), bukan produk reflektif |

Format: `source: "Kepgub DKI 811/2025, item 696.19, hlm 1262"`, plus `kepgub_item` dan `kepgub_page` agar bisa diverifikasi otomatis.

### Yang TIDAK ADA di Kepgub 811/2025 — tetap `"ASUMSI"`

- **Cat cool roof / pelapis atap reflektif.** Nol item. Bagian 6 "Cat" hanya cat duco, epoxy 2K, cat lantai coating, zinkchromate.
- **Green roof / media tanam per m².** Nol item. Sekam dan pupuk kandang hanya muncul di dalam teks spesifikasi tanaman pot.
- **`canopy_m2_per_tree`** — jembatan dari harga per batang ke poin persen kanopi per sel. Asumsi terpisah, sengaja tidak dilebur ke angka bersumber.

Proxy yang **sengaja ditolak**: item `28.290` waterproofing batu alam/marmer (Rp 460.000/liter — bukan atap, bukan reflektif) dan `6.3` cat lantai coating.

### Verifikasi

```bash
uv run --no-project --python 3.12 --with pypdf --with pyyaml python pipeline/verify_costs.py
```

Untuk tiap entri ber-`kepgub_page`, skrip membuka halaman PDF itu dan meng-assert kode item **dan** nilai rupiahnya benar-benar muncul di sana. Perlu karena OCR-nya punya korupsi terlihat (`803.60ął`, `2.214.00ł`, `7.885.13łą`) dan frontmatter-nya sendiri menyuruh cek ke PDF. Entri `ASUMSI` dilewati, dan asumsi baru yang belum dicatat membuat check gagal.

## E. Suhu udara (validasi, opsional)

Unduh: `uv run --no-project --python 3.12 python pipeline/fetch_bmkg.py` → `data/raw/bmkg/stations_daily.csv` (3.270 baris, ~190 KB).

| Stasiun | WMO | ID GHCN | Lat/Lon | Jun–Sep tersedia |
|---|---|---|---|---|
| Kemayoran (Jakarta Observatory) | 96745 | `ID000096745` | −6,183 / 106,833 | 2023, 2024 |
| Tanjung Priok | 96741 | `IDM00096741` | −6,100 / 106,867 | 2023, 2024 |
| Soekarno-Hatta | 96749 | `IDM00096749` | −6,126 / 106,656 | 2023, 2024, 2025 (s.d. 24 Agu) |
| Budiarto (Curug) | 96739 | `IDM00096739` | −6,293 / 106,570 | 2023, 2024 |

- Sumber unduhan: **NOAA GHCN-Daily** ([access CSV](https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/)), yang mendistribusikan laporan sinoptik BMKG sendiri. Variabel: TMAX, TMIN, TAVG harian (°C).
### BMKG Data Online — batas yang sudah diverifikasi (8 Okt 2026, akun login)

| Batas | Nilai |
|---|---|
| Resolusi | **Bulanan saja.** Sub-bulanan harus lewat [PTSP BMKG](https://ptsp.bmkg.go.id/) (manual/berbayar). |
| Jendela waktu | **2 tahun terakhir.** Terverifikasi: `2024-10` ke atas diterima, `2024-06..09` ditolak (HTTP 422). |
| Stasiun | Maks. 2 per unduhan. DKI hanya punya 3: 96747 Halim, 96745 Kemayoran, 96741 Tanjung Priok. |
| Kuota | 24 bulan/siklus; habis = tunggu 30 hari. Permintaan yang gagal **tidak** memotong kuota. |
| Gate | Wajib isi Survey Kepuasan Masyarakat 1× per semester (Jan–Jun, Jul–Des) sebelum tombol unduh aktif. |
| Parameter | `temp_max`, `temp_min`, `temp_avg`, `hum_avg`, `wind_avg`, `wind_speed`, `wind_dir`, `wind_dir_car`, `sunshine`, `rainfall` |
| Endpoint | `POST /proses-data-bulanan` (Laravel + CSRF `_token`); login pakai reCAPTCHA sehingga tidak bisa diskrip. |

### Hasil unduhan dataonline (per 9 Okt 2026)

Parse: `uv run --no-project --python 3.12 --with openpyxl python pipeline/parse_bmkg_bulanan.py` → `data/raw/bmkg/stations_monthly.csv` (**32 baris**). File XLSX mentah di `data/raw/bmkg/bulanan/`.

| Stasiun | Periode | Hasil |
|---|---|---|
| 96745 Kemayoran | 2024-11 … 2026-02 | 16/16 bulan terisi |
| 96741 Tanjung Priok | 2024-11 … 2026-02 | 16/16 bulan terisi |
| 96747 Halim | 2025-06 … 2025-09 | **0/4 — kosong total**, dicoba 2× |

Kolom: `rainfall_mm`, `wind_max_ms`, `wind_avg_ms`, `rh_avg_pct`, `sunshine_h`, `tmax_c`, `tmin_c`, `tavg_c`, `wind_dir`, `wind_dir_car`. Sentinel BMKG (`8888` tidak terukur, `9999` tidak ada pengukuran, `-`) dibuang jadi sel kosong oleh parser.

Ekspor Jun–Sep 2025 dan 2024-11…2026-02 tumpang tindih 8 station-month. Keduanya disimpan sebagai rekaman mentah; parser men-*dedupe* ke satu baris per station-month dan melaporkan bila nilainya berbeda antar-ekspor (sejauh ini identik).

> ### ⚠️ `temp_max` dan `temp_min` adalah EKSTREM bulanan, bukan rata-rata harian
>
> Jangan pakai `tmax_c` dataonline sebagai "rata-rata suhu maksimum" — angkanya kelebihan **~3,6 °C**. Kolom itu berisi suhu hari terpanas pada bulan tersebut. `temp_avg` benar-benar rata-rata.
>
> Terukur terhadap GHCN: vs **rata-rata** bulanan GHCN selisihnya `tmax` +3,62 °C dan `tmin` −1,90 °C; vs **ekstrem** bulanan GHCN turun jadi +0,79 °C dan −0,17 °C, dan **persis sama** di bulan yang cakupan GHCN-nya penuh (Kemayoran 2024-11 35,2/35,2 · 2024-12 24,4/24,4 · 2025-01 23,8/23,8).

### Cek-silang dataonline ↔ GHCN (sudah terlaksana, 9 Okt 2026)

```bash
uv run --no-project --python 3.12 python pipeline/crosscheck_bmkg.py
```

→ `data/processed/bmkg_ghcn_crosscheck.csv`, 7 station-month beririsan (**Nov 2024 – Feb 2025**, Kemayoran + Priok). Selisih untuk `model_card.json`:

| Variabel | Statistik yang dibandingkan | Selisih rata-rata (BMKG − GHCN) | Terbesar |
|---|---|---|---|
| `tavg_c` | rata-rata bulanan | **−0,14 °C** | −0,26 °C |
| `tmax_c` | **ekstrem** maks bulanan | +0,79 °C | +1,60 °C |
| `tmin_c` | **ekstrem** min bulanan | −0,17 °C | −1,00 °C |

Sisa selisih pada ekstrem bukan ketidaksepakatan data: GHCN punya hari bolong, sehingga ekstrem terobservasinya bias ke dalam sementara BMKG melihat rekaman lengkap. **Tidak memakai kuota BMKG tambahan** — ekspor yang sudah ada sudah memuat jendela beririsan.

**Halim tidak bisa dipakai.** Alat "Ketersediaan Data" melaporkan Halim 2025-06…09 = 100% (temp dan RH), tetapi ekspor bulanannya mengembalikan `-` di semua sel pada dua permintaan terpisah. Jadi data hariannya ada di sisi BMKG tapi agregat bulanannya tidak dipublikasikan — bug di sisi mereka, bukan masalah cakupan. Halim juga 0% sepanjang 2024 (stasiun baru melapor ~Jan 2025). Kuota terpakai 8 dari 24, sisa 16.

**Dataonline dan GHCN saling melengkapi, bukan menggantikan.** Jun–Sep 2023 dan 2024 hanya ada di GHCN (harian). Mar 2025 ke atas hanya ada di dataonline (bulanan, plus RH/angin/penyinaran yang tidak dipunyai GHCN), karena GHCN berhenti 6 Mar 2025 untuk Kemayoran dan Priok. Nov 2024 – Feb 2025 ada di **keduanya** dan dipakai untuk cek-silang di atas. Lihat `docs/DECISIONS.md`.
- Halim (96747) tidak ada di GHCN, dan ekspor bulanan dataonline untuk Halim kosong — jadi **tidak terpakai di kedua sumber**. Soekarno-Hatta dan Budiarto dipakai sebagai pengganti terdekat di GHCN.
- Hanya 4 titik, jadi tidak dipakai untuk melatih model. Dipakai di bagian Keterbatasan untuk menunjukkan beda LST dan suhu udara.

## F. Foto uji Cek Atap (30 foto, CONCEPT §13)

**Status: 0 dari 30 foto tim.** Scaffold sudah siap di `data/roof_test/` — lihat `data/roof_test/README.md` untuk alur kerja dan nilai enum.

- Tidak ada dataset terbuka foto atap rumah Indonesia dari sudut pandang warga. **Tim memotret sendiri**: tanpa wajah, nomor rumah, plat nomor, atau nama jalan dalam frame.
- Hapus metadata: `uv run --no-project --python 3.12 --with pillow python pipeline/strip_exif.py`. Foto ponsel memuat GPS, dan **foto atap ber-GPS adalah alamat rumah**. Skrip itu membongkar piksel lalu menulis ulang tanpa wadah metadata, jadi tidak bisa kelewat satu tag; orientasi dibakar ke piksel lebih dulu agar foto tidak jadi miring bagi model vision.
- Label manual di `data/roof_test/labels.csv`, nilai enum **harus** sama dengan `response_schema` CONCEPT §8.5.
- **Placeholder berlisensi terbuka** (CC0/CC-BY) ditandai `is_placeholder: true` dan dipakai **hanya untuk smoke test**. Dikecualikan dari angka akurasi: foto berlisensi terbuka cenderung rumah Eropa/Amerika Utara, bukan genteng dan seng Jakarta, jadi akurasinya menyesatkan ke arah optimis.
- Target §13 (`roof_form` ≥ 85%, `material` ≥ 70%) **belum boleh diklaim** di proposal, video, atau brief sampai 30 foto asli terlabeli.
- Referensi kelas material (citra udara, bukan untuk uji): [RoofNet](https://arxiv.org/abs/2505.19358), 51,5 ribu sampel, 14 material.
- Foto tidak di-commit — `data/roof_test/photos/` di-gitignore (CLAUDE.md aturan 8). Hanya `labels.csv` yang masuk repo.

## F2. Basis bukti intervensi (`data/evidence/interventions.json`)

10 entri, **4 terverifikasi** ke naskah asli (9 Okt 2026). Hanya entri `verified: true` yang boleh dikutip agen atau proposal.

| Entri | Sumber | Metrik | Nilai |
|---|---|---|---|
| `ev_ndvi_kl_2025` | Miniandi et al. 2025, *Earth Systems and Environment* 9(2):1037–1060, [doi:10.1007/s41748-025-00584-4](https://doi.org/10.1007/s41748-025-00584-4) | **LST kawasan** | NDVI +25% → −1,4 … +0,1 °C |
| `ev_albedo_kl_2025` | sama | **LST kawasan** | albedo +25% → −1,2 … +0,1 °C |
| `ev_coolroof_id_surface` | [JARDS UII](https://journal.uii.ac.id/jards/article/view/36209) | **permukaan atap** | hingga −11,58 °C · fluks −95% · energi hingga −55% |
| `ev_greenroof_id_surface` | sama | **permukaan atap** | hingga −13,14 °C · fluks −91% · energi ~−60% |

> ### ⚠️ Jangan campur skala
>
> Angka −11,58 dan −13,14 °C adalah **suhu permukaan atap / dalam ruang pada bangunan satu lantai**, bukan pendinginan kelurahan. Menyajikannya sebagai efek kawasan akan **melebihkan kemampuan TEDUH sekitar 10×** — pembanding kawasan yang benar adalah −1,2 hingga −1,4 °C dari Miniandi et al. Karena itu setiap entri punya field `metric` eksplisit dan `interventions.json` memuat kamus definisi metrik.

Catatan lain: CONCEPT §7.7 menulis hemat energi cool roof "36–55%", tapi hanya batas atas 55% yang terkonfirmasi — **batas bawah 36% jangan dikutip**. Paper Miniandi juga melaporkan pendinginan **terbesar di area yang LST-nya sudah tinggi**, yang mendukung logika penargetan TEDUH secara independen.

6 entri sisanya `verified: false` dengan alasan tertulis masing-masing. Satu patut dicurigai: `ev_urban_greening_meta` mengklaim penurunan **suhu udara** 1,5–4,5 °C dari penghijauan, jauh di atas hasil peer-review skala kawasan (−1,4 °C untuk LST, dan efek udara biasanya lebih kecil dari efek permukaan). Kemungkinan itu nilai terbaik atau pengukuran di dalam taman yang disajikan sebagai rentang umum.

## G. Dokumen perencanaan (untuk bagian brief "Keterkaitan dengan Dokumen Perencanaan")

CONCEPT §8.4 mewajibkan satu bagian brief yang mengaitkan rekomendasi dengan dokumen perencanaan yang berlaku. Bagian ini sebelumnya tidak punya sumber sama sekali.

**Status: terkatalog, belum diunduh.** Yang dibutuhkan brief adalah sitasi (nomor peraturan, tahun, pasal) — bukan PDF-nya. Unduh hanya kalau nanti perlu kutipan pasal verbatim.

| Dokumen | Status | Peran |
|---|---|---|
| **Perda DKI No. 7 Tahun 2024** — Rencana Tata Ruang Wilayah (RTRW) | berlaku 21 Okt 2024, **paling mutakhir** | Kerangka tata ruang tingkat provinsi. Rujukan utama. [JDIH BPK](https://peraturan.bpk.go.id/Details/313265/perda-prov-dki-jakarta-no-7-tahun-2024) |
| **Pergub DKI No. 31 Tahun 2022** — Rencana Detail Tata Ruang (RDTR) Wilayah Perencanaan | berlaku | Zonasi tingkat detail; unit terdekat ke kelurahan. [JDIH Jakarta](https://jdih.jakarta.go.id/dokumen/detail/4933/peraturan-gubernur-nomor-31-tahun-2022-tentang-rencana-detail-tata-ruang-wilayah-perencanaan-provinsi-daerah-khusus-ibukota-jakarta) · [JDIH BPK](https://peraturan.bpk.go.id/Details/228166/pergub-prov-dki-jakarta-no-31-tahun-2022) |
| **UU No. 26 Tahun 2007** tentang Penataan Ruang, Pasal 29 | berlaku | **Dasar hukum target RTH 30%**: minimal 30% dari luas wilayah kota (20% publik + 10% privat). Ini yang membuat rekomendasi TEDUH punya pijakan wajib, bukan sekadar saran. |
| **RPJMD DKI 2025–2029** | belum dilacak | Dokumen anggaran/program; yang menentukan apakah intervensi bisa masuk mata anggaran. Perlu dilacak. |
| [Jakarta Satu — Smart RDTR](https://jakartasatu.jakarta.go.id/geoportal/layanan/smart-rdtr) | geoportal aktif | Zonasi RDTR dalam bentuk spasial. Berpotensi dipakai untuk memeriksa apakah suatu kelurahan punya zona RTH terencana. **Belum dievaluasi** lisensi dan aksesnya. |

> RTH >30% disebut sebagai salah satu dari lima arah pengembangan di RDTR 2022. Angka 30% itu **jangan ditulis agen sebagai hasil hitungan** — ia konstanta hukum, jadi sumbernya UU 26/2007 Pasal 29, bukan `grid_features`.

**Belum diperiksa:** berapa persen RTH Jakarta sekarang menurut data resmi. `grid_features.parquet` memberi `tree_frac` rata-rata 0,159 kota (tutupan pohon WorldCover), tapi definisi RTH dalam peraturan lebih luas dari tutupan kanopi (termasuk lapangan, pemakaman, jalur hijau), jadi **kedua angka itu tidak boleh disamakan**. Membandingkannya tanpa catatan akan membuat seolah Jakarta jauh lebih gundul dari klaim resmi.

## Atribusi untuk UI

USGS Landsat · Copernicus Sentinel-2, DEM GLO-30, Sentinel-5P · ESA WorldCover 2021 · Google Open Buildings 2.5D Temporal · WorldPop (Bondarenko et al. 2025) · OCHA/BPS COD-AB · BMKG (jika dipakai).
