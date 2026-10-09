"""Strip EXIF from roof photos before they enter the repo (CONCEPT §8.5, CLAUDE.md rule 8).

Phone photos carry GPS coordinates, timestamps and device serials. A roof photo with GPS is a
home address, so the metadata has to go before the file is stored or sent to Gemini. CONCEPT
§8.5 allows location only down to kelurahan, recorded separately in labels.csv by hand, never
read back off the image.

Rewrites in place by decoding the pixels and re-encoding into a container with no metadata,
which is why it cannot "miss" a tag the way targeted tag-deletion would. Orientation is baked
into the pixels first: dropping an orientation tag without rotating would silently hand the
vision model sideways photos.

Run: uv run --no-project --python 3.12 --with pillow python pipeline/strip_exif.py
Output: every image under data/roof_test/photos/ rewritten without metadata
"""

from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "data" / "roof_test" / "photos"

SUFFIXES = {".jpg", ".jpeg", ".png"}

# Gemini does not need more than this, and it keeps the directory small.
MAX_EDGE_PX = 2048

JPEG_QUALITY = 90


def strip(path: Path) -> tuple[int, int]:
    """Rewrite one image without metadata. Returns (bytes_before, bytes_after)."""
    before = path.stat().st_size
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)  # bake rotation into pixels, then lose the tag
        img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        if path.suffix.lower() == ".png":
            clean.save(path, "PNG", optimize=True)
        else:
            clean.convert("RGB").save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return before, path.stat().st_size


def main() -> None:
    if not PHOTOS.exists():
        PHOTOS.mkdir(parents=True, exist_ok=True)
        print(f"dibuat {PHOTOS.relative_to(ROOT)} (kosong). Taruh foto di sini lalu jalankan ulang.")
        return

    images = sorted(p for p in PHOTOS.iterdir() if p.suffix.lower() in SUFFIXES)
    if not images:
        print(f"tidak ada gambar di {PHOTOS.relative_to(ROOT)}; tidak ada yang dikerjakan")
        return

    for path in images:
        before, after = strip(path)
        print(f"  {path.name:40s} {before / 1024:7.0f} KB -> {after / 1024:7.0f} KB")
    print(f"dibersihkan {len(images)} gambar di {PHOTOS.relative_to(ROOT)}")
    check(images)


def check(images: list[Path]) -> None:
    """No EXIF left at all, so no GPS can have survived."""
    for path in images:
        with Image.open(path) as img:
            exif = dict(img.getexif())
            assert not exif, f"{path.name}: EXIF masih ada ({len(exif)} tag)"
            assert not img.info.get("exif"), f"{path.name}: blob EXIF masih menempel"
    print("check ok")


if __name__ == "__main__":
    main()
