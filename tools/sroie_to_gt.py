"""Convert the SROIE 2019 test labels (company, date, total) into the ground-truth JSON format of evaluate.py.

Input: a metadata.jsonl with lines {"file_name": ..., "ground_truth": "{\"gt_parse\": {...}}"}
(e.g. the Hugging Face mirror podbilabs/sroie-donut, test split). SROIE has no line items.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parse import find_date  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", default="data/gt")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    n = 0
    for line in open(a.meta, encoding="utf-8"):
        row = json.loads(line)
        g = json.loads(row["ground_truth"])["gt_parse"]
        total = g.get("total")
        try:
            total = float(re.sub(r"[^\d.]", "", total)) if total else None
        except ValueError:
            total = None
        gt = {
            "merchant": g.get("company"),
            # dates are normalised to ISO; a label the date rules cannot read is kept raw (and will count as a miss)
            "date": find_date(g["date"]) or g["date"] if g.get("date") else None,
            "total": total,
        }
        stem = os.path.splitext(row["file_name"])[0]
        with open(os.path.join(a.out, stem + ".json"), "w", encoding="utf-8") as fh:
            json.dump(gt, fh, ensure_ascii=False)
        n += 1
    print(f"{n} ground-truth files -> {a.out}")


if __name__ == "__main__":
    main()
