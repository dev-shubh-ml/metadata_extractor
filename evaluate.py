"""
Evaluate extraction accuracy against ground-truth CSV using per-field Recall.

Recall (per field) = True Matches / (True Matches + Misses)

Usage:
  python evaluate.py              # evaluates on data/train/ vs data/train.csv
  python evaluate.py test         # evaluates on data/test/ vs data/test.csv
"""

import re
import sys
import csv
from pathlib import Path

from predict import run_predictions, FIELDS

DATA_DIR = Path(__file__).parent / "data"


def load_ground_truth(csv_path: Path) -> dict[str, dict]:
    """Load CSV into a dict keyed by File Name (stripped)."""
    gt = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row["File Name"].strip()
            gt[key] = {k: v.strip() for k, v in row.items()}
    return gt


def normalize(value) -> str:
    """Lowercase, strip, and collapse internal whitespace for comparison."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


def evaluate(folder_name: str = "train") -> dict:
    csv_path = DATA_DIR / f"{folder_name}.csv"
    ground_truth = load_ground_truth(csv_path)
    predictions = run_predictions(folder_name)

    scores = {f: {"true": 0, "false": 0} for f in FIELDS}

    print("\n--- Detailed Comparison ---")
    for pred in predictions:
        stem = pred.get("File Name", "")
        if stem not in ground_truth:
            print(f"  [SKIP] '{stem}' not found in {csv_path.name}")
            continue

        gt_row = ground_truth[stem]
        for field in FIELDS:
            pred_val = normalize(pred.get(field))
            gt_val = normalize(gt_row.get(field, ""))

            if pred_val and pred_val == gt_val:
                scores[field]["true"] += 1
            else:
                scores[field]["false"] += 1
                print(f"  MISS  [{field}]")
                print(f"        Expected : '{gt_val}'")
                print(f"        Got      : '{pred_val}'")

    print("\n--- Per-Field Recall ---")
    total_true = total_false = 0
    for field, s in scores.items():
        t, f = s["true"], s["false"]
        recall = t / (t + f) if (t + f) > 0 else 0.0
        total_true += t
        total_false += f
        bar = "█" * int(recall * 20) + "░" * (20 - int(recall * 20))
        print(f"  {field:<32} {bar}  {recall:.0%}  ({t}/{t + f})")

    overall = total_true / (total_true + total_false) if (total_true + total_false) > 0 else 0.0
    print(f"\n  {'Overall Recall':<32}  {overall:.0%}  ({total_true}/{total_true + total_false})")

    return scores


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "train"
    evaluate(folder)
