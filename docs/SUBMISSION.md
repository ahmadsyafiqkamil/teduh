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
| R² spatial block CV | `data/model/model_card.json` | 0,755 rata-rata 5 lipatan (terendah 0,723) |
| RMSE | `model_card.json` | 1,24 °C (MAE 0,94 °C) |
| Akurasi pemilihan tool | `golden_20261009T153001Z.json` | 65% (13/20) — **di bawah target 90%, jangan dikutip sebagai capaian** |
| Latensi p50 chat | `golden_20261009T153001Z.json` | 9,4 s — **di atas target 8 s, jangan dikutip sebagai capaian** |
| Akurasi `roof_form` | `roof_20261009T151310Z.json` | belum terukur (0 foto berlabel dari 30) |
| Akurasi `material` | `roof_20261009T151310Z.json` | belum terukur (0 foto berlabel dari 30) |
| Validasi penduduk | DECISIONS 2026-10-09 | selisih 0,54% vs Dukcapil |
| Baseline regresi linear | `model_card.json` | R² 0,686 — LightGBM unggul 0,069 |
| Bukti literatur terverifikasi | `interventions.json` | 4 dari 10 entri `verified: true` |

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
