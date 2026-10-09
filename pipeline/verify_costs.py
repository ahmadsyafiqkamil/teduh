"""Check every Kepgub-sourced figure in config/costs.yaml against the source PDF.

config/costs.yaml was filled from an OCR of Kepgub DKI 811/2025, and that OCR has visible
corruption on some rows (803.60ial, 2.214.00l, 7.885.13laa) -- its own frontmatter says to
verify figures against the PDF before using them. Checking once by hand would rot, so this
re-checks on demand: for each entry carrying kepgub_item and kepgub_page, it opens that page
of the PDF and asserts both the item code and the rupiah amount actually appear there.

The PDF has a text layer, and the OCR's `Hlm` column maps 1:1 to its page numbers, which is
what makes this cheap. Entries sourced "ASUMSI" are listed but not checked -- there is nothing
to check them against, which is the whole point of the label.

Run: uv run --no-project --python 3.12 --with pypdf --with pyyaml python pipeline/verify_costs.py
Output: none, exits non-zero if any sourced figure disagrees with the PDF
"""

from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
COSTS = ROOT / "config" / "costs.yaml"
PDF = ROOT / "data" / "raw" / "sbm" / "2025KEPGUB0031811.pdf"

ASSUMPTION = "ASUMSI"

# Assumptions we have accepted and written down. Anything new showing up here is a drift the
# author has to acknowledge, not something the check should wave through.
EXPECTED_ASSUMPTIONS = {
    "tree_planting.canopy_m2_per_tree",
    "cool_roof.cost_idr_per_m2",
    "green_roof.cost_idr_per_m2",
}


def _format_idr(value: float) -> str:
    """Indonesian thousands separator, the way the Kepgub tables print it: 2.702.703."""
    return f"{int(round(value)):,}".replace(",", ".")


def _walk(node: dict, trail: tuple[str, ...] = ()) -> list[tuple[str, dict]]:
    """Collect every priced leaf, keyed by its dotted path."""
    found: list[tuple[str, dict]] = []
    for key, child in node.items():
        if not isinstance(child, dict):
            continue
        if "value" in child and "source" in child:
            found.append((".".join(trail + (key,)), child))
        else:
            found.extend(_walk(child, trail + (key,)))
    return found


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(
            f"{PDF.relative_to(ROOT)} tidak ada. Salin PDF Kepgub 811/2025 ke sana "
            "(data/raw/ tidak di-commit, jadi harus disalin manual di tiap mesin)."
        )
    entries = _walk(yaml.safe_load(COSTS.read_text()))
    reader = PdfReader(str(PDF))

    sourced = [(path, e) for path, e in entries if e.get("kepgub_page")]
    assumed = [(path, e) for path, e in entries if e["source"] == ASSUMPTION]
    cited = [(path, e) for path, e in entries
             if not e.get("kepgub_page") and e["source"] != ASSUMPTION]

    pages: dict[int, str] = {}
    for path, entry in sourced:
        page = int(entry["kepgub_page"])
        if page not in pages:
            pages[page] = reader.pages[page - 1].extract_text() or ""
        text = pages[page]
        item = str(entry["kepgub_item"])
        amount = _format_idr(entry["value"])

        assert item in text, f"{path}: item {item} tidak ada di hlm {page} PDF"
        assert amount in text, f"{path}: nilai {amount} tidak ada di hlm {page} PDF"
        print(f"  OK     {path:46s} {amount:>14s}  item {item:9s} hlm {page}")

    for path, entry in cited:
        print(f"  cited  {path:46s} {'':>14s}  {entry['source']}")
    for path, entry in assumed:
        print(f"  ASUMSI {path:46s} {_format_idr(entry['value']):>14s}  tidak bisa diverifikasi")

    check(sourced, assumed)


def check(sourced: list, assumed: list) -> None:
    """A sourced price must exist, and the assumption list must stay the one we wrote down."""
    assert sourced, "tidak ada satu pun harga bersumber Kepgub; cek config/costs.yaml"

    actual = {path for path, _ in assumed}
    undeclared = actual - EXPECTED_ASSUMPTIONS
    assert not undeclared, (
        f"ASUMSI baru tanpa dicatat: {sorted(undeclared)}. Kalau disengaja, tambahkan ke "
        "EXPECTED_ASSUMPTIONS dan catat alasannya di docs/DECISIONS.md."
    )
    resolved = EXPECTED_ASSUMPTIONS - actual
    if resolved:
        print(f"  catatan: {sorted(resolved)} tidak lagi ASUMSI -- perbarui DATA_SOURCES.md §D")

    print(f"{len(sourced)} harga terverifikasi ke PDF, {len(assumed)} masih asumsi")
    print("check ok")


if __name__ == "__main__":
    main()
