"""Measure Cek Atap accuracy against the hand-labelled set (CONCEPT §13).

Refuses to report accuracy below MIN_PHOTOS on purpose. An accuracy figure computed from
five photos is not evidence, and once it is printed it tends to end up in a proposal. The
labels file currently has zero team photos, so this script exists to be run AFTER the set is
collected, not to produce a number now.

Photos are never committed (CLAUDE.md rule 8). Only labels.csv and the aggregate report are.

Run: uv run python -m tests.eval.eval_roof
Output: tests/eval/reports/roof_<timestamp>.json
"""

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from teduh_agent.tools.roof import analyze_roof_bytes

ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "data" / "roof_test" / "labels.csv"
PHOTO_DIR = ROOT / "data" / "roof_test" / "photos"
REPORT_DIR = ROOT / "tests" / "eval" / "reports"

# CONCEPT §13.
TARGETS = {"roof_form": 0.85, "material": 0.70}
MIN_PHOTOS = 30

GRADED_FIELDS = ("roof_form", "material")
SUFFIXES = (".jpg", ".jpeg", ".png")


def load_labels() -> list[dict]:
    """Hand labels, excluding the example row that ships with the CSV."""
    with LABELS_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row for row in rows
        if (row.get("is_placeholder") or "").strip().lower() != "true"
    ]


def _photo_for(photo_id: str) -> Path | None:
    for suffix in SUFFIXES:
        candidate = PHOTO_DIR / f"{photo_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def evaluate(labels: list[dict]) -> list[dict]:
    results: list[dict] = []

    for row in labels:
        photo_id = row["photo_id"]
        path = _photo_for(photo_id)
        if path is None:
            print(f"  LEWAT {photo_id}: berkas foto tidak ada di {PHOTO_DIR.name}/")
            continue

        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        try:
            predicted = analyze_roof_bytes(path.read_bytes(), mime_type)
        except Exception as error:  # noqa: BLE001 -- any genai/network failure
            print(f"  GAGAL {photo_id}: {error}")
            continue

        entry = {"photo_id": photo_id, "confidence": predicted.get("confidence")}
        for field in GRADED_FIELDS:
            entry[f"true_{field}"] = row[field]
            entry[f"pred_{field}"] = predicted.get(field)
            entry[f"ok_{field}"] = row[field] == predicted.get(field)
        results.append(entry)

        marks = " ".join("OK" if entry[f"ok_{f}"] else "X " for f in GRADED_FIELDS)
        print(f"  {marks} {photo_id}  keyakinan {entry['confidence']}")

    return results


def accuracy(results: list[dict], field: str) -> float:
    if not results:
        return 0.0
    return sum(1 for entry in results if entry[f"ok_{field}"]) / len(results)


def confusion(results: list[dict], field: str) -> dict[str, dict[str, int]]:
    """True label -> predicted label -> count. Shows WHICH materials get confused."""
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entry in results:
        matrix[entry[f"true_{field}"]][str(entry[f"pred_{field}"])] += 1
    return {true: dict(predictions) for true, predictions in matrix.items()}


def main() -> None:
    labels = load_labels()
    print(f"label       : {len(labels)} foto berlabel (minimal {MIN_PHOTOS} untuk melaporkan)")

    results = evaluate(labels)
    summary = {
        "n_labelled": len(labels),
        "n_evaluated": len(results),
        "min_photos": MIN_PHOTOS,
        "reportable": len(results) >= MIN_PHOTOS,
        "accuracy": {field: accuracy(results, field) for field in GRADED_FIELDS},
        "targets": TARGETS,
        "confusion": {field: confusion(results, field) for field in GRADED_FIELDS},
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = REPORT_DIR / f"roof_{stamp}.json"
    report.write_text(
        json.dumps(
            {"run_at": datetime.now(UTC).isoformat(), "summary": summary, "results": results},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"laporan     : {report.relative_to(ROOT)}")

    check(results)


def check(results: list[dict]) -> None:
    """Withhold the accuracy figure until the set is big enough to mean something."""
    if len(results) < MIN_PHOTOS:
        print(
            f"\nBELUM BISA DILAPORKAN: {len(results)} foto dievaluasi, butuh {MIN_PHOTOS}. "
            "Akurasi dari sampel kecil bukan bukti. JANGAN sebut akurasi Cek Atap di "
            "proposal, video, atau brief sampai set ini lengkap "
            "(lihat data/roof_test/README.md)."
        )
        return

    for field, target in TARGETS.items():
        value = accuracy(results, field)
        verdict = "memenuhi" if value >= target else "DI BAWAH"
        print(f"  {field:12s} {value:.1%}  target {target:.0%}  {verdict}")

    for field in GRADED_FIELDS:
        if accuracy(results, field) < TARGETS[field]:
            print(
                f"\nPERINGATAN: {field} di bawah target. Lihat matriks kebingungan di laporan "
                "untuk melihat kelas mana yang tertukar, lalu perjelas panduannya di "
                "VISION_PROMPT. Jangan menurunkan targetnya."
            )
    print("check ok")


if __name__ == "__main__":
    main()
