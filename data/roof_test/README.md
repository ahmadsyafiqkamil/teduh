# Set uji Cek Atap

Target CONCEPT §13: **30 foto berlabel manual**, akurasi `roof_form` ≥ 85%, `material` ≥ 70%.

**Status: 0 dari 30 foto tim.** Target akurasi itu **belum boleh diklaim** di proposal, video, atau brief sampai 30 foto asli ada dan terlabeli.

## Kenapa tim harus memotret sendiri

Tidak ada dataset terbuka foto atap rumah Indonesia **dari sudut pandang warga**. Yang ada adalah citra udara — mis. [RoofNet](https://arxiv.org/abs/2505.19358) (51,5 ribu sampel, 14 material) — dan itu tidak mewakili apa yang difoto warga dari halaman atau jendela. Model yang dinilai dengan citra udara akan terlihat bagus lalu gagal di lapangan.

## Alur kerja

1. Potret atap. **Jangan** ada wajah, nomor rumah, plat nomor, atau nama jalan dalam frame.
2. Taruh di `photos/` (di-gitignore — foto tidak pernah di-commit, CLAUDE.md aturan 8).
3. Hapus metadata:
   ```bash
   uv run --no-project --python 3.12 --with pillow python pipeline/strip_exif.py
   ```
   Foto ponsel memuat koordinat GPS. **Foto atap ber-GPS adalah alamat rumah.** Skrip itu membongkar piksel dan menulis ulang tanpa wadah metadata, jadi tidak bisa "kelewat" satu tag.
4. Labeli satu baris per foto di `labels.csv`. Isi `kelurahan` paling detail setingkat kelurahan saja (CONCEPT §8.5), dan hanya bila pemilik foto setuju.

## Nilai enum

Harus sama persis dengan `response_schema` di CONCEPT §8.5 — kalau tidak, evaluasinya membandingkan label dengan sesuatu yang tidak pernah bisa dihasilkan model:

| Kolom | Nilai |
|---|---|
| `roof_form` | `flat` · `pitched` · `mixed` · `unknown` |
| `material` | `clay_tile` · `concrete_tile` · `metal_sheet` · `concrete_slab` · `asbestos_cement` · `other` · `unknown` |
| `color_tone` | `light` · `medium` · `dark` |
| `condition` | `good` · `worn` · `damaged` · `unknown` |
| `shade_from_trees` | `none` · `partial` · `heavy` |

## Placeholder berlisensi terbuka

Baris ber-`is_placeholder: true` adalah foto berlisensi terbuka (CC0/CC-BY) yang dipakai **hanya untuk smoke test** bahwa `analyze_roof_photo` jalan dan `response_schema`-nya ditaati. Wajib mengisi `license`, `attribution`, dan `source_url`.

**Placeholder dikecualikan dari setiap angka akurasi.** Jangan diikutkan ke hitungan §13: foto berlisensi terbuka cenderung rumah Eropa/Amerika Utara, bukan atap genteng dan seng Jakarta, jadi akurasi yang terukur darinya menyesatkan ke arah optimis.

## Keamanan asbes

Foto atap asbes tetap berguna dan **harus** ada dalam set uji, karena aturan CONCEPT §8.5 untuk `asbestos_cement` adalah yang paling penting benar: jangan diamplas, dipotong, atau dibor. Tapi jangan ganggu material atapnya hanya untuk memotret.
