"""
Generate predictions for all files in a given data folder.

Usage:
  python predict.py              # runs on data/test/, saves predictions_test.csv
  python predict.py train        # runs on data/train/, saves predictions_train.csv
"""

import sys
import csv
import json
import time
from pathlib import Path

from extract import extract_from_file

FIELDS = [
    "Aggrement Value",
    "Aggrement Start Date",
    "Aggrement End Date",
    "Renewal Notice (Days)",
    "Party One",
    "Party Two",
]

DATA_DIR = Path(__file__).parent / "data"


def _file_stem(path: Path) -> str:
    """Return filename without extension, handling the .pdf.docx double extension."""
    name = path.name
    if name.lower().endswith(".pdf.docx"):
        return name[:-9]
    return path.stem


def run_predictions(folder_name: str = "test") -> list[dict]:
    folder = DATA_DIR / folder_name
    results = []

    files = sorted(p for p in folder.iterdir() if not p.name.startswith("."))

    for i, file_path in enumerate(files):
        stem = _file_stem(file_path)
        print(f"Processing: {stem} ...", end=" ", flush=True)

        # Free tier is 5 RPM; wait 13s between calls to stay safely under the limit
        if i > 0:
            time.sleep(13)

        try:
            metadata = extract_from_file(file_path)
            metadata["File Name"] = stem
            results.append(metadata)
            print("done")
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"File Name": stem, **{f: None for f in FIELDS}})

    return results


def save_csv(results: list[dict], output_path: Path) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["File Name"] + FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved → {output_path}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "test"
    results = run_predictions(folder)
    save_csv(results, Path(f"predictions_{folder}.csv"))
    print(json.dumps(results, indent=2))
