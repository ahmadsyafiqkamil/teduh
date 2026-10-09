# TEDUH — Paket Prompt untuk Claude Design

Cara pakai:

1. Buat proyek baru di Claude Design. **Unggah `docs/CONCEPT.md`** sebagai konteks, lalu tempel **Blok A (Konteks)** dan **Blok B (Arah Visual)** di pesan pertama.
2. Jalankan prompt layar **satu per satu**, mulai dari wireframe. Jangan langsung semua sekaligus.
3. Setelah satu layar cocok, lanjut ke layar berikutnya dengan kalimat "pakai sistem visual yang sama".
4. Rapikan detail kecil (jarak, warna) dengan edit langsung di kanvas, bukan lewat prompt.
5. Kalau sudah final, serahkan ke Claude Code (lihat bagian terakhir).

---

## Blok A — Konteks (tempel di pesan pertama)

```
Saya sedang merancang TEDUH, aplikasi web untuk kompetisi AI Builder Cup 2026 (tema Sustainability & Social Impact). Detail lengkap ada di CONCEPT.md yang saya unggah.

APA ITU TEDUH
AI agent (Gemini) yang membantu pemerintah kota memutuskan di kelurahan mana dan dengan intervensi apa (tanam pohon, cool roof, green roof) panas perkotaan (Urban Heat Island) harus ditangani lebih dulu, dengan prioritas warga paling rentan (lansia, balita, permukiman padat). Hasil akhirnya draf policy brief yang setiap angkanya bisa ditelusuri ke sumber data atau literatur. Pilot: DKI Jakarta, tingkat kelurahan.

PENGGUNA
1. Utama: perencana di Bappeda / Dinas Cipta Karya / Dinas Lingkungan Hidup. Usia 30–50, terbiasa Excel dan peta sederhana, bukan ahli GIS atau AI. Bekerja di laptop 14–15 inci.
2. Kedua: warga biasa yang memakai fitur "Cek Atap" dari ponsel untuk mendapat saran mendinginkan rumah.
3. Juri hackathon yang menonton demo 3 menit. Desain harus langsung terbaca dalam beberapa detik.

PRINSIP YANG HARUS TERLIHAT DI DESAIN
- Setiap angka punya asal-usul. Angka di UI bisa diarahkan kursornya untuk melihat sumber (data satelit, model, literatur, atau asumsi). Brief menampilkan lencana "✓ Semua angka terverifikasi".
- Jujur soal ketidakpastian. Hasil simulasi diberi label "Indikatif" dan selalu ditemani rentang dari literatur. Ada catatan bahwa yang diukur adalah suhu permukaan, bukan suhu udara.
- Keadilan panas. Kelompok rentan selalu disebut dan divisualkan, bukan hanya rata-rata suhu.
- Agen bekerja secara transparan. Saat menjawab, chat menampilkan langkah-langkahnya (mis. "Membaca data kelurahan → Menjalankan simulasi → Menulis brief").

BAHASA
Semua teks UI dalam Bahasa Indonesia yang jelas dan formal-ramah (gaya dokumen pemerintah modern). Ada toggle ID/EN di header.

BATASAN TEKNIS (untuk handoff ke Claude Code)
Next.js (App Router) + TypeScript + Tailwind CSS + komponen bergaya shadcn/ui + MapLibre GL JS untuk peta. Ikon Lucide. Gunakan komponen yang bisa dibangun ulang dengan stack ini.

DATA DI MOCKUP
Pakai nama kelurahan Jakarta yang nyata, tetapi semua angka adalah DATA CONTOH. Tampilkan label kecil "Data contoh" di pojok peta dan panel supaya tidak tertukar dengan data asli.
```

---

## Blok B — Arah Visual

```
ARAH VISUAL
Nama "Teduh" berarti tempat yang terlindung dari terik. Suasananya tenang, terpercaya, dan berwibawa seperti dokumen perencanaan pemerintah yang modern. Hindari gaya startup neon, glassmorphism, gradien ungu, dan dashboard gelap ala militer.

WARNA MEREK (UI)
- Hijau kanopi  #1F5C4A  → warna utama, tombol utama, link aktif
- Hijau daun    #8BB59A  → aksen lembut, status positif
- Kertas        #F7F4EE  → latar belakang halaman
- Putih         #FFFFFF  → kartu dan panel
- Tinta         #1C2321  → teks utama
- Batu          #5E6662  → teks sekunder (kontras 5,4:1 di atas Kertas)
- Garis         #E3DED4  → border 1px
Warna panas TIDAK dipakai untuk elemen UI. Warna panas khusus untuk data.

WARNA DATA (peta dan grafik)
- Suhu permukaan (LST), sekuensial 7 kelas:
  #FFF5D6 #FEE08B #FDB863 #F4845F #E0533D #B5213A #6E0F2B
- Indeks Kerentanan Panas (HVI), sekuensial ungu 5 kelas:
  #F2EEF7 #CBBFE0 #9B86C4 #6B4FA0 #3F1F6B
- Perubahan suhu (ΔLST) hasil simulasi, biru (makin turun makin pekat):
  #E6F2F8 #A9D0E6 #5FA3CB #2B78A8 #1D5F8A
- Selalu sertakan legenda dengan satuan (°C) dan pastikan bisa dibaca penderita buta warna (beda kecerahan jelas antar kelas).

TIPOGRAFI
- Plus Jakarta Sans untuk seluruh UI (judul 600–700, isi 400–500).
- Angka memakai tabular figures supaya kolom angka rata.
- Ukuran dasar 15px desktop, 16px mobile. Judul halaman 24–28px.

BENTUK DAN KOMPONEN
- Radius 10–12px, border 1px warna Garis, bayangan sangat tipis.
- Ruang lega, grid 8px.
- Komponen khusus:
  • Chip sumber: angka + ikon kecil ⓘ, hover menampilkan "Sumber: Landsat 8/9, musim kemarau 2023–2025" atau "Sumber: Miniandi et al. 2025" atau "ASUMSI".
  • Pill "Indikatif": outline abu-abu, ikon info.
  • Lencana verifikasi: "✓ 23 angka terverifikasi" berwarna hijau kanopi.
  • Langkah agen: daftar kecil berikon (centang, spinner) di atas jawaban chat.
  • Kartu hasil di chat: judul, 2–4 angka utama, tombol "Sorot di peta".

AKSESIBILITAS
Kontras teks minimal WCAG AA. Target sentuh minimal 44px di mobile. Fokus keyboard terlihat.
```

---

## Prompt 1 — Wireframe dashboard (mulai di sini)

```
Buat 3 variasi WIREFRAME (abu-abu, tanpa warna merek) untuk layar utama TEDUH, desktop 1440×900.

Isi wajib:
- Header: logo TEDUH, pemilih lapisan peta [Suhu Permukaan] [Kerentanan (HVI)] [Vegetasi] [Penduduk Rentan], pencarian kelurahan, toggle ID/EN, tombol "Tentang & Sumber Data".
- Peta Jakarta (area terbesar) dengan choropleth per kelurahan, legenda, label "Data contoh".
- Panel chat agen dengan riwayat percakapan, kartu hasil, dan kolom input (ada tombol lampiran foto).
- Dok skenario: slider "Tambah kanopi pohon", "Cool roof", "Green roof", input "Anggaran (Rp)", tombol "Simulasikan".

Variasi:
A. Peta kiri ~65%, chat kanan ~35%, dok skenario di bawah peta.
B. Peta penuh layar, chat sebagai panel mengambang di kanan, dok skenario sebagai bilah bawah yang bisa diciutkan.
C. Tiga kolom: daftar kelurahan prioritas (kiri), peta (tengah), chat (kanan).

Jelaskan singkat kelebihan dan kekurangan tiap variasi untuk perencana dinas yang bukan ahli GIS.
```

---

## Prompt 2 — Dashboard hi-fi

```
Ambil variasi [A/B/C] dan buat versi high-fidelity memakai Arah Visual di Blok B.

Tampilkan keadaan saat pengguna sudah bertanya:
"Kelurahan mana di Jakarta Timur yang paling perlu diprioritaskan untuk penanganan panas?"

- Peta: lapisan HVI aktif, 5 kelurahan teratas disorot dengan outline tebal hijau kanopi dan nomor urut 1–5. Contoh nama: Kampung Melayu, Bidara Cina, Cipinang Besar Utara, Rawa Bunga, Cawang.
- Chat: langkah agen ("✓ Mencari wilayah", "✓ Menghitung indeks kerentanan", "✓ Menganalisis faktor pendorong"), lalu jawaban singkat dan kartu hasil berisi tabel 5 kelurahan (peringkat, HVI, LST rata-rata, jumlah warga rentan) dengan chip sumber pada setiap angka.
- Saran pertanyaan lanjutan di bawah jawaban, misalnya "Simulasikan cool roof di 2 teratas" dan "Apa penyebab panas di Kampung Melayu?".
- Dok skenario dalam keadaan diam.

Semua angka adalah data contoh.
```

---

## Prompt 3 — Profil kelurahan

```
Desain drawer "Profil Kelurahan" yang muncul dari kanan peta saat pengguna mengklik Kampung Melayu. Lebar ~420px.

Isi berurutan:
1. Nama kelurahan, kecamatan, kota. Peringkat HVI "3 dari 267". Tombol "Tanya agen tentang wilayah ini".
2. Empat kartu angka: LST rata-rata (°C), selisih dari rata-rata kota (+°C), HVI (0–1), warga rentan (jiwa, balita + lansia).
3. Komponen HVI sebagai 4 bar horizontal: Bahaya, Keterpaparan, Kepekaan, Kurangnya kapasitas adaptif.
4. "Apa yang membuat wilayah ini panas?": grafik kontribusi faktor (gaya SHAP) dengan 4–5 faktor, misalnya Fraksi bangunan +1,2 °C, Tutupan pohon rendah +0,8 °C, Albedo rendah +0,5 °C, Dekat air −0,3 °C. Jelaskan dalam satu kalimat bahasa awam.
5. Tutupan lahan: bar bertumpuk (bangunan, pohon, air, lainnya).
6. Catatan kaki kecil: "Suhu permukaan dari Landsat 8/9, musim kemarau 2023–2025. Bukan suhu udara."

Semua angka punya chip sumber. Label "Data contoh".
```

---

## Prompt 4 — Simulasi skenario

```
Desain keadaan setelah pengguna menjalankan skenario:
"Cool roof 50% dan tambah kanopi pohon 10% di Kampung Melayu dan Bidara Cina."

1. Peta mode split "Sebelum | Sesudah" dengan pembatas yang bisa digeser. Sisi "Sesudah" memakai skala biru ΔLST.
2. Kartu hasil di chat:
   - Judul "Perkiraan dampak skenario" + pill "Indikatif".
   - Angka utama: rata-rata ΔLST per kelurahan (mis. −0,9 °C dan −0,7 °C), ΔLST tertimbang penduduk, jumlah warga rentan yang terdampak.
   - Baris "Pembanding literatur": rentang dari studi (mis. "Studi Kuala Lumpur: +25% NDVI → −1,4 s.d. 0,1 °C") dengan chip sumber.
   - Luas intervensi (m²) dan perkiraan biaya dengan label "ASUMSI harga satuan, bisa diubah".
   - Peringatan kuning bila ada ekstrapolasi: "Sebagian sel berada di luar rentang data latih. Tafsirkan dengan hati-hati."
3. Dok skenario menampilkan slider pada posisi yang dipakai.
```

---

## Prompt 5 — Portofolio anggaran

```
Desain layar atau panel "Susun Portofolio" untuk pertanyaan:
"Anggaran kami Rp 2 miliar untuk Jakarta Timur. Susun paket intervensi terbaik."

1. Form ringkas: wilayah, anggaran, slider "Porsi minimal untuk wilayah paling rentan" (default 60%), centang jenis intervensi yang diizinkan.
2. Ringkasan: total biaya vs anggaran (progress bar), total penurunan panas tertimbang warga rentan, porsi anggaran ke kuintil HVI teratas (dengan tanda centang jika syarat terpenuhi).
3. Tabel paket terpilih: kelurahan, intervensi, level, luas, biaya, ΔLST, warga rentan terdampak. Bisa diurutkan.
4. Grafik batang kecil: distribusi anggaran per kuintil HVI (Q1–Q5) untuk menunjukkan keberpihakan.
5. Tombol utama "Buat Policy Brief" dan tombol sekunder "Unduh CSV".
Tandai harga satuan sebagai ASUMSI.
```

---

## Prompt 6 — Policy brief

```
Desain pratinjau Policy Brief sebagai halaman A4 (tampil di modal besar atau halaman sendiri), gaya dokumen kajian pemerintah yang rapi.

Struktur:
- Kop: "Kajian Singkat Mitigasi Panas Perkotaan — Jakarta Timur", tanggal, "Disusun dengan bantuan TEDUH".
- Lencana "✓ 23 angka terverifikasi" di bagian atas.
- Bagian: Ringkasan Eksekutif · Kondisi Panas Wilayah (dengan peta kecil) · Kelompok Rentan · Opsi Intervensi & Perkiraan Dampak (tabel) · Rekomendasi Portofolio & Anggaran · Keterkaitan dengan RDTR/RPJMD/RTH 30% · Keterbatasan · Sumber.
- Angka di badan teks diberi superskrip yang merujuk ke catatan kaki sumber.
- Toolbar di atas pratinjau: "Unduh PDF", "Salin ringkasan", "Ekspor ke Google Docs", "Revisi dengan agen".
Tampilkan halaman 1 secara penuh dan potongan halaman 2.
```

---

## Prompt 7 — Cek Atap (mobile)

```
Desain alur "Cek Atap" untuk ponsel 390×844, 4 layar, memakai sistem visual yang sama.

1. Pembuka: judul "Seberapa panas atap rumahmu?", penjelasan satu kalimat, ilustrasi sederhana atap dan matahari, kotak persetujuan privasi ("Foto tidak disimpan lebih dari 30 hari. Lokasi hanya sampai tingkat kelurahan, opsional."), tombol "Mulai".
2. Ambil foto: panduan sudut (contoh benar/salah dalam thumbnail), tombol kamera besar, opsi "Pilih dari galeri".
3. Menganalisis: pratinjau foto, langkah "Mengenali bentuk atap… Mengenali material… Menyusun saran…".
4. Hasil:
   - Kartu "Yang kami lihat": bentuk atap (miring), material (genteng tanah liat), warna (gelap), naungan pohon (sedikit), tingkat keyakinan.
   - Kartu rekomendasi utama: "Cat pemantul panas (cool roof)" dengan alasan singkat dan kisaran manfaat dari literatur + chip sumber.
   - Kartu alternatif: "Green curtain di jendela barat".
   - Varian layar 4 dengan PERINGATAN KESELAMATAN jika material terdeteksi asbes semen: kotak merah-oranye "Jangan diamplas, dipotong, atau dibor. Hubungi tenaga profesional."
   - Tombol "Bagikan ke WhatsApp" dan "Coba foto lain".
```

---

## Prompt 8 — Tentang, Sumber Data, dan keadaan khusus

```
Desain tiga hal pendukung dengan sistem visual yang sama:

1. Halaman "Tentang & Sumber Data":
   - Penjelasan singkat TEDUH dan cara kerjanya (diagram 4 langkah: Data satelit → Model panas → Agen AI → Brief kebijakan).
   - Tabel sumber data dengan atribusi: Landsat 8/9 (USGS), Sentinel-2 (Copernicus), ESA WorldCover, Google Open Buildings, WorldPop, Copernicus DEM.
   - "Kartu Model": periode data, metrik akurasi (R², RMSE dari validasi spasial), batasan utama.
   - Bagian "Keterbatasan" yang jujur.

2. Keadaan khusus di dashboard:
   - Agen sedang bekerja (langkah dengan spinner).
   - Data tidak tersedia untuk sebuah kelurahan.
   - Error koneksi dengan tombol coba lagi.
   - Keadaan awal (belum ada pertanyaan) dengan 3–4 contoh pertanyaan yang bisa diklik.

3. Versi mobile dashboard: peta di atas, chat sebagai bottom sheet yang bisa ditarik.
```

---

## Prompt 9 — Deck proposal (PDF untuk submission)

```
Buat deck proposal 16:9, 11 slide, memakai sistem visual yang sama. Deck ini akan diekspor ke PDF untuk submission AI Builder Cup 2026. Juri menilai: Technical Merit & Gen AI (40%), Problem Alignment & Impact (25%), Innovation & Creativity (25%), UX & Solution Design (10%).

1. Sampul: TEDUH — "Dari peta panas ke kebijakan yang berpihak pada warga rentan." Tema Sustainability & Social Impact. Nama tim.
2. Masalah: Jakarta hingga ~8 °C lebih panas saat kemarau; warga rentan paling terdampak. (Angka akan saya verifikasi, beri penanda [cek].)
3. Celah: peta UHI sudah akurat, tapi jarang sampai ke RDTR dan anggaran; alat terlalu teknis dan mahal.
4. Solusi: satu kalimat + tangkapan layar dashboard.
5. Cara kerja: alur Data satelit → Model ML → Agen Gemini → Brief, dengan 4 ikon.
6. Desain Gen AI: diagram agen ADK (koordinator + 4 sub-agen), tool deterministik, pengecek asal-usul angka, Gemini vision untuk Cek Atap.
7. Demo: 3 tangkapan layar (simulasi, portofolio, brief).
8. Dampak & keadilan: siapa yang diuntungkan, porsi anggaran ke wilayah paling rentan, kaitan SDG 3, 11, 13.
9. Kelayakan & skala: stack Google Cloud (Gemini, ADK, Cloud Run, Earth Engine, OR-Tools), data global sehingga bisa direplikasi ke kota lain.
10. Peta jalan: pilot bersama Pemkot, multi-kota, laporan warga, peringatan panas.
11. Tim & penutup: tautan demo dan video.

Gunakan placeholder bertanda jelas untuk tangkapan layar dan angka yang belum final.
```

---

## Prompt iterasi (pakai sesuai kebutuhan)

```
Saya suka [elemen] dari opsi B dan [elemen] dari opsi D. Buat 4 variasi yang menggabungkan keduanya.
```
```
Kurangi kepadatan informasi di kartu hasil. Perencana harus menangkap pesan utamanya dalam 5 detik.
```
```
Periksa kontras semua teks dan legenda peta terhadap WCAG AA, lalu perbaiki yang gagal.
```
```
Buat versi Bahasa Inggris dari layar ini untuk juri, tanpa mengubah tata letak.
```
```
Pastikan semua angka punya chip sumber dan semua hasil simulasi punya pill "Indikatif". Daftar yang terlewat lalu perbaiki.
```

---

## Handoff ke Claude Code

Setelah desain final, kirim ke Claude Code dari Claude Design, lalu sertakan instruksi ini:

```
Implementasikan desain ini di folder web/ sesuai CLAUDE.md dan docs/CONCEPT.md.
- Next.js App Router + TypeScript + Tailwind + komponen bergaya shadcn/ui + MapLibre GL JS.
- Simpan token warna dan tipografi dari desain di tailwind config / CSS variables (brand, data-lst, data-hvi, data-delta).
- Buat komponen terpisah: SourceChip, IndicativePill, VerifiedBadge, AgentSteps, ResultCard, ScenarioDock, KelurahanDrawer, BriefPreview, RoofCheckFlow.
- Data dari endpoint /api/* di CONCEPT §11.3. Selama backend belum siap, pakai mock JSON di web/mocks/ dengan label "Data contoh".
- Jangan hard-code angka di komponen.
```
