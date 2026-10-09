# Handoff: TEDUH — Layar Utama (Desktop)

## Overview
TEDUH adalah aplikasi web untuk pemerintah kota (Bappeda/Dinas) guna memprioritaskan penanganan Urban Heat Island berbasis data dan keadilan sosial. Layar utama menggabungkan **peta choropleth kelurahan**, **chat agen AI (Gemini)** yang menampilkan langkah kerjanya, **dok simulasi skenario**, dan **drawer Profil Kelurahan**. Setiap angka bisa dilacak ke sumbernya lewat **chip sumber (ⓘ)**.

Pengguna: perencana usia 30–50, terbiasa Excel, bukan GIS. Harus terbaca dalam hitungan detik.

## About the Design Files
File di bundle ini adalah **referensi desain dalam HTML** — prototipe yang menunjukkan tampilan dan perilaku yang dimaksud, **bukan kode produksi**. Tugasnya adalah **membangun ulang** desain ini di codebase target. Stack yang direkomendasikan (belum ada codebase): **Next.js (App Router) + TypeScript + Tailwind CSS + MapLibre GL JS**, backend agen via route handler yang memanggil Gemini dengan tool calling.

Buka `TEDUH Layar Utama.dc.html` di browser (butuh `support.js` di folder yang sama) untuk melihat dan mencoba interaksinya. Logika data ada di blok `<script data-dc-script>` di akhir file.

## Fidelity
**High-fidelity.** Warna, tipografi, spasi, dan interaksi final. Bangun ulang sedekat mungkin piksel-per-piksel. Pengecualian: **peta adalah placeholder** (Voronoi SVG dari GeoJSON tiruan) — ganti dengan MapLibre + GeoJSON batas kelurahan DKI asli, pertahankan palet, outline, dan penanda.

`TEDUH Wireframe.dc.html` dan `Teduh.dc.html` adalah eksplorasi lo-fi sebelumnya (variasi A/B/C); hanya untuk konteks. Variasi A yang dipilih.

---

## Layout global
- Kanvas desain 1440×900. Target minimal 1280 px lebar.
- Kolom vertikal: **Header 60 px** → **Body** (flex:1).
- Body = CSS grid `grid-template-columns: 65fr 35fr`.
  - Kiri: **Peta** (flex:1) di atas **Dok Skenario** (tinggi auto, ±130 px).
  - Kanan: **Panel Agen** (`<aside>`), border-left 1px `#E3DED4`.
- Drawer Profil Kelurahan menimpa sisi kanan area **peta** (bukan panel agen): absolute, top/right/bottom 0, lebar 420 px.
- Latar app `#F7F4EE`; permukaan panel/kartu `#FFFFFF`.

## Screens / Views

### 1. Header (60 px, bg #FFFFFF, border-bottom 1px #E3DED4, padding 0 20px, gap 24px)
- **Logo**: kotak 32×32 radius 8 bg `#1F5C4A`, ikon Lucide `tree-deciduous` 18 px putih. Di sebelahnya: "TEDUH" 16/700 letter-spacing .14em; sub "DKI Jakarta · kelurahan" 11.5 px `#5E6662`.
- **Pemilih lapisan** (segmented, `role="group"`): wadah border 1px #E3DED4 radius 10 padding 3 bg #FBFAF7, gap 2. Tombol 34 px tinggi, padding 0 12, radius 8, 13.5 px. Swatch 10×10 radius 3 sebelum label.
  - Opsi: Suhu Permukaan (`#E0533D`), Kerentanan (HVI) (`#6B4FA0`), Vegetasi (`#5E9A6E`), Penduduk Rentan (`#6F6A60`).
  - Aktif: bg #FFF, border 1px #1F5C4A, teks #1F5C4A 600. Tidak aktif: transparan, teks #1C2321 500. Hover: bg #F2EFE8. `aria-pressed`.
- Spacer flex:1.
- **Pencarian**: 236×38, border 1px #E3DED4 radius 10, ikon `search` 16, placeholder "Cari kelurahan…". Focus-within: border #1F5C4A.
- **Toggle bahasa ID/EN**: wadah border radius 10 padding 3; tombol 30 px tinggi, min-width 38, 12.5/700. Aktif bg #1F5C4A teks putih; tidak aktif transparan teks #5E6662.
- **"Tentang & Sumber Data"**: tombol 38 px, border #E3DED4 radius 10, 13.5/600, ikon `book-open` stroke #1F5C4A. Hover bg #F7F4EE border #CFC8BB.

### 2. Peta (bg #EFEBE3)
- Choropleth kelurahan, stroke putih 0.9 px. Laut `#DFE6E4`, label "Teluk Jakarta" italic 13 px #5E6662. Batas DKI stroke #8A918D 1.2.
- **Palet per lapisan** (kelas rendah → tinggi):
  - LST: `#FFF5D6 #FEE08B #FDB863 #F4845F #E0533D #B5213A #6E0F2B` (batas 31 / 32,5 / 33,5 / 34,5 / 35,5 / 36,5 °C)
  - HVI: `#F2EEF7 #CBBFE0 #9B86C4 #6B4FA0 #3F1F6B` (kelas tiap 0,2)
  - Vegetasi: `#F1F5EC #CFE0C3 #9DC39A #5E9A6E #2C6A4C` (tiap 10%) — *perlu konfirmasi klien*
  - Penduduk rentan: `#F1EFEA #D5D0C6 #A9A396 #6F6A60 #3A3833` (tiap 1.000 jiwa/km²) — *perlu konfirmasi klien*
- **Sorotan 5 kelurahan prioritas** (dari jawaban agen): outline putih 6 px di bawah outline `#1F5C4A` 3.4 px; penanda lingkaran r 11 bg #1F5C4A stroke putih 2, angka 1–5 putih 11.5/700 di centroid. Label nama #1 dengan halo putih 3.5 px.
- **Hover kelurahan**: outline #1C2321 1.6 px + tooltip gelap di atas tengah peta (bg #1C2321, radius 8, 13 px): nama (600) · sub (#C9CFCC, mis. "Prioritas #1" atau "Jakarta Timur") · nilai lapisan (tabular, 600).
- **Kelurahan terpilih** (drawer terbuka): outline putus-putus #1C2321 2.4 px, dash 5 3. Peta digeser (pan) agar tidak tertutup drawer.
- **Overlay**:
  - Kiri-atas: kartu "JAKARTA TIMUR" (11.5/700 uppercase .08em #5E6662) + judul lapisan 14/600, mis. "Kerentanan panas per kelurahan".
  - Kanan-atas: badge "Data contoh" (border 1px **dashed** #5E6662 radius 6, 11.5/600) dan kontrol zoom 36×36 (+/−).
  - Kanan-bawah: **Legenda** 312 px, radius 12, padding 12/14: judul 13/600, sub 11.5 #5E6662, ramp 14 px tinggi, tick tabular 11 px; jika sorotan aktif: baris "5 kelurahan prioritas dari jawaban agen" dengan swatch outline hijau.
  - Atribusi "© OpenFreeMap · © kontributor OpenStreetMap" 10.5 px.
  - Saat drawer terbuka, overlay kanan bergeser `right: 436px`.
- Teks legenda per lapisan:
  - LST: "Suhu permukaan tanah (LST), °C" / "Median musim kemarau 2023–2025 · Landsat 8/9 · bukan suhu udara"
  - HVI: "Indeks Kerentanan Panas (HVI), 0–1" / "Bahaya × keterpaparan, kepekaan (balita & lansia), dan kurangnya pohon"
  - Vegetasi: "Tutupan vegetasi, % luas kelurahan" / "ESA WorldCover 10 m · pohon, semak, rumput"
  - Penduduk: "Balita & lansia, jiwa per km²" / "WorldPop 2020, 100 m · usia <5 dan ≥65 tahun"

### 3. Drawer Profil Kelurahan (420 px, bg #FFF, border-left #E3DED4, shadow `-10px 0 28px rgba(28,35,33,.08)`, `role="dialog"`)
**Header tetap** (padding 14/20, border-bottom):
- Kicker "PROFIL KELURAHAN" + badge "Data contoh" + tombol tutup 36×36 (`x`).
- Nama 24/700 letter-spacing −.015em; lokasi 13.5 #5E6662 ("Kec. Jatinegara · Kota Jakarta Timur").
- Pil "Peringkat HVI **3 dari 267**" (bg #F2EEF7, teks #3F1F6B, tinggi 30, radius penuh) + pil outline "Prioritas #1 Jakarta Timur" (border 1.5 #1F5C4A, teks #1F5C4A 600).
- Tombol utama penuh "Tanya agen tentang wilayah ini" (42 px, bg #1F5C4A, teks putih 14/600, ikon `message-circle`; hover #184A3C) → mengisi input chat.

**Isi scroll** (padding 18/20, gap 22):
1. **Grid 2×2 kartu angka** (border #E3DED4 radius 10 padding 10/12): label 12 #5E6662 · nilai 22/700 · sub 11.5.
   - LST rata-rata 37,4 °C · "suhu permukaan"
   - Selisih dari rata-rata kota **+3,1 °C** (warna #B5213A) · "rata-rata kota 34,3 °C"
   - Indeks kerentanan (HVI) 0,93 (warna #3F1F6B) · "skala 0–1, makin tinggi makin rentan"
   - Warga rentan 5.450 jiwa · "2.140 balita + 3.310 lansia"
2. **Komponen kerentanan panas** — rumus "HVI = Bahaya × (0,4 Keterpaparan + 0,3 Kepekaan + 0,3 Kurangnya kapasitas adaptif)". 4 bar (tinggi 8, track #F2EEF7, isi #6B4FA0, radius 4): Bahaya (panas permukaan), Keterpaparan (kepadatan penduduk), Kepekaan (balita & lansia), Kurangnya kapasitas adaptif. Nilai 0–1 di kanan dengan chip sumber.
3. **"Apa yang membuat wilayah ini panas?"** — sub "Kontribusi tiap faktor terhadap selisih suhu, menurut model (SHAP)".
   - Paragraf bahasa awam (bg #F7F4EE, border, radius 10, 14 px lh 1.55).
   - Grafik bar divergen: grid `136px | 1fr | 64px`; sumbu nol di 20% lebar; positif ke kanan `#E0533D`, negatif ke kiri `#2B78A8`, "Faktor lain (gabungan)" `#CFC8BB` + label #5E6662. Contoh: Fraksi bangunan tinggi +1,2 · Tutupan pohon rendah +0,8 · Albedo atap rendah +0,5 · Kepadatan jalan +0,4 · Dekat badan air −0,3 · Faktor lain +0,5.
   - Baris total "Total selisih +3,1 °C" dengan legenda memanaskan/mendinginkan. **Jumlah kontribusi harus = selisih LST** (validasi di backend).
4. **Tutupan lahan** — bar bertumpuk 22 px (Bangunan #6F6A60, Pohon #5E9A6E, Air #5FA3CB, Lainnya #D5D0C6) + legenda grid 2 kolom dengan %.
5. Catatan kaki ⓘ: "Suhu permukaan dari Landsat 8/9, musim kemarau 2023–2025. Bukan suhu udara."

### 4. Dok Skenario (bg #FFF, border-top, padding 14/20/16, gap 12)
- Baris judul: "Simulasi skenario" 15/600 · pil "Target: 5 kelurahan prioritas" · status "Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan." · badge "Data contoh" kanan.
- Grid `repeat(3, 1fr) 196px 132px`, gap 20, align end:
  - Slider "Tambah kanopi pohon" 0–20 step 1, tampil "+N pp", bantuan "Poin persen lahan terbuka"
  - Slider "Cool roof" 0–100 step 5, "N%", "Porsi atap dicat pemantul panas"
  - Slider "Green roof" 0–50 step 5, "N%", "Porsi atap beton datar"
  - Nilai: 13.5/600 tabular; #1F5C4A bila >0, #5E6662 bila 0. `accent-color: #1F5C4A`.
  - Input "Anggaran (Rp)" 40 px, prefix "Rp", format ribuan id-ID saat mengetik (hanya digit).
  - Tombol "Simulasikan" (ikon `play`) 40 px radius 10: **disabled** (bg #E3DED4, teks #5E6662, not-allowed) sampai salah satu slider > 0; aktif bg #1F5C4A teks putih.

### 5. Panel Agen (aside)
- **Header 52 px**: "Agen TEDUH" 15/600 + sub "Setiap angka berasal dari data atau model, bukan karangan" 12 #5E6662; tombol ikon "Percakapan baru" (`pencil`).
- **Thread** (scroll, padding 12/20, gap 8, auto-scroll ke bawah):
  - Pesan pengguna: rata kanan, max 88%, bg #F7F4EE, border, radius `12 12 4 12`, 14 px lh 1.5.
  - **Blok langkah kerja agen**: bg #FBFAF7, border radius 10. Header ikon logo kecil + "3 langkah selesai · 3,8 detik" 12/600. Tiap langkah: centang `check` #1F5C4A + label 13 px + nama tool monospace 11 px di kanan:
    - Mencari wilayah "Jakarta Timur" — `find_area`
    - Menghitung indeks kerentanan — `rank_priority_areas`
    - Menganalisis faktor pendorong — `explain_drivers`
    - Saat streaming: langkah berjalan pakai spinner, selesai jadi centang.
  - Jawaban prosa 14 px lh 1.55. Angka dalam prosa = **chip sumber inline** (600, garis bawah titik-titik).
  - **Kartu hasil tabel** "5 kelurahan paling rentan panas" + badge "Data contoh": kolom `24px | 1fr | 50px | 76px | 66px` = # (lingkaran 20 px #1F5C4A) · Kelurahan · HVI · LST rata-rata · Warga rentan; header 11.5 #5E6662. Baris hover bg #F7F4EE dan **menyorot kelurahan di peta**; klik membuka drawer. Footer: "LST = suhu permukaan, bukan suhu udara." + tombol toggle "Tersorot di peta"/"Sorot di peta" (ikon `map-pin`; aktif bg #EAF2EC border #1F5C4A).
  - **Saran pertanyaan lanjutan**: pil 30 px radius penuh, ikon `arrow-right` #1F5C4A; hover border #1F5C4A bg #F5F9F6. Klik → mengisi input.
- **Composer** (border-top, padding 12/16/14): kotak border radius 12, textarea 14 px placeholder "Tanyakan tentang panas di wilayah Anda…"; tombol "Foto atap" (ikon `camera`) dan Kirim 36×36 bg #1F5C4A (ikon `send`). Focus-within: border #1F5C4A.

### Data contoh (5 prioritas Jakarta Timur)
| # | Kelurahan | HVI | LST °C | Balita | Lansia | Peringkat DKI |
|---|---|---|---|---|---|---|
| 1 | Kampung Melayu | 0,93 | 37,4 | 2.140 | 3.310 | 3 |
| 2 | Bidara Cina | 0,91 | 37,1 | 1.610 | 2.510 | 4 |
| 3 | Cipinang Besar Utara | 0,89 | 36,9 | 1.490 | 2.380 | 6 |
| 4 | Rawa Bunga | 0,87 | 36,6 | 1.020 | 1.590 | 8 |
| 5 | Cawang | 0,86 | 36,4 | 930 | 1.440 | 9 |
Rata-rata LST DKI = 34,3 °C. Total kelurahan = 267.

---

## Komponen kunci: SourceChip (chip sumber)
Lihat `SourceChip.dc.html`. Wajib dipakai untuk **setiap angka** di UI.
- Props: `value: string`, `unit?: string` (tanpa spasi untuk "%", NBSP untuk lainnya), `kind: 'data'|'model'|'literatur'|'asumsi'|'input'`, `source: string`, `placement: 'top'|'bottom'`, `align: 'center'|'start'|'end'`.
- Tampilan: inline-flex, tabular-nums, garis bawah 1px **dotted** #5E6662 (**dashed** untuk `asumsi`/`input`), ikon `info` 11 px #5E6662, `cursor: help`, `tabIndex=0`.
- Tooltip saat hover **dan focus** (`role="tooltip"`): lebar 252, bg #1C2321, teks putih 12.5 lh 1.45, radius 8, shadow `0 8px 24px rgba(28,35,33,.18)`, jarak 8 px. Kicker 10.5/700 uppercase .08em warna #8BB59A (asumsi: #E3DED4):
  - data → "Sumber · Data satelit"
  - model → "Sumber · Model & perhitungan TEDUH"
  - literatur → "Sumber · Literatur"
  - asumsi → "ASUMSI · dapat diedit"
  - input → "Sumber · Masukan pengguna"
- Implementasi: gunakan Radix Tooltip / Floating UI dengan collision handling.

## Interactions & Behavior
- Ganti lapisan → ubah fill, legenda, judul peta, format nilai tooltip hover.
- Hover kelurahan di peta / baris tabel → outline + tooltip. Klik → buka drawer + pan peta.
- Tutup drawer → peta kembali ke posisi, overlay kembali ke `right:16px`.
- "Sorot di peta" toggle → tampil/sembunyi outline & penanda prioritas.
- Pertanyaan lanjutan / "Tanya agen…" / Simulasikan → isi composer dengan prompt (tidak langsung kirim pada prototipe; di produksi bisa langsung kirim).
- Toggle ID/EN → seluruh string UI. **Belum lengkap di prototipe**: hanya header, label lapisan, judul panel. Siapkan i18n (mis. `next-intl`) untuk semua teks termasuk konten agen.
- Format angka: `id-ID` (koma desimal, titik ribuan), semua angka `font-variant-numeric: tabular-nums`. Tanda minus pakai "−" (U+2212).
- Transisi yang disarankan: drawer slide-in 200 ms ease-out; pan peta 300 ms (MapLibre `easeTo`).
- Focus: `outline 2px solid #1F5C4A; outline-offset 2px` di semua elemen interaktif.

## State Management
- `layer: 'lst'|'hvi'|'veg'|'pop'` (default `hvi`)
- `lang: 'id'|'en'`
- `selectedKelurahanId: string|null` (drawer)
- `hoverKelurahanId`, `hoverRowIndex`
- `highlightPriority: boolean` + `priorityIds: string[]` (dari hasil tool agen)
- `scenario: { tree: number, coolRoof: number, greenRoof: number, budget: number|null }`
- `chat: { messages[], steps[] (tool, label, status, durationMs), draft }`
- Data: GeoJSON kelurahan + atribut (lst, hvi, komponen HVI, veg, pop, balita, lansia, shap[], landcover[]) per kelurahan, masing-masing dengan metadata sumber untuk SourceChip.
- Agen: stream respons + event tool call (`find_area`, `rank_priority_areas`, `explain_drivers`, `simulate_scenario`) ke UI; kartu hasil dirender dari output tool terstruktur, **bukan** dari teks LLM, agar angka terverifikasi.

## Design Tokens
**Warna merek**
- Hijau kanopi (utama) `#1F5C4A`, hover/pressed `#184A3C`, tint `#EAF2EC`, tint hover `#F5F9F6`
- Hijau daun `#8BB59A` (kicker tooltip)
- Kertas (latar app) `#F7F4EE`; permukaan halus `#FBFAF7`; hover `#F2EFE8`
- Tinta (teks) `#1C2321`; teks sekunder `#5E6662`; teks di latar gelap `#C9CFCC`
- Border `#E3DED4`; border kuat `#CFC8BB`; border baris `#F0ECE4`; outline kanvas `#D6D0C4`
- Sumbu/garis netral `#8A918D`
- Data: panas `#E0533D`, panas kuat `#B5213A`, dingin `#2B78A8`, HVI `#6B4FA0` / tint `#F2EEF7` / gelap `#3F1F6B`, air `#5FA3CB`

**Tipografi** — Plus Jakarta Sans (400/500/600/700), angka selalu tabular.
- 24/700 nama kelurahan · 22/700 angka kartu · 16/700 logo · 15/600 judul seksi · 14 badan · 13.5 kontrol · 13 sekunder · 12–12.5 bantuan · 11–11.5 kicker/label (uppercase .08em) · 10.5 atribusi
- Line-height: badan 1.5–1.55, keterangan 1.4–1.45, judul 1.2

**Spasi** — 2, 4, 6, 8, 10, 12, 14, 16, 20, 22, 24 px. Padding panel 20 px.

**Radius** — 2–3 (swatch/bar), 6 (badge), 8 (tombol kecil, tooltip), 10 (tombol, input, kartu kecil), 12 (kartu, composer, legenda), 999 (pil).

**Shadow**
- Kartu: `0 1px 2px rgba(28,35,33,.06)`
- Drawer: `-10px 0 28px rgba(28,35,33,.08)`
- Tooltip: `0 8px 24px rgba(28,35,33,.18)`

**Pola "Data contoh"** — badge border 1px dashed #5E6662 radius 6. Tampilkan di setiap modul selama data belum final; label "Indikatif" untuk hasil simulasi.

## Assets
- Ikon: **Lucide** (`lucide-react`): tree-deciduous, search, book-open, plus, minus, x, message-circle, check, map-pin, arrow-right, pencil, camera, send, play, info.
- Font: Google Fonts Plus Jakarta Sans.
- Peta dasar: OpenFreeMap / OSM (atribusi wajib).
- Sumber data (untuk teks chip): Landsat 8/9 Collection 2 (LST), WorldPop 2020 100 m, ESA WorldCover v200, Google Open Buildings Temporal v1, model LightGBM v1 + SHAP (R² CV spasial 0,78).
- Tidak ada gambar raster.

## Files
- `TEDUH Layar Utama.dc.html` — desain hi-fi utama (referensi utama).
- `SourceChip.dc.html` — komponen chip sumber.
- `support.js` — runtime agar file .dc.html bisa dibuka di browser (bukan untuk produksi).
- `TEDUH Wireframe.dc.html`, `Teduh.dc.html` — eksplorasi lo-fi (konteks saja).
- `CONCEPT.md` — konsep produk (jika ada).
