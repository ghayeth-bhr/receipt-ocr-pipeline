"""Field-level accuracy of predicted JSON files against ground-truth JSON files with the same stem."""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

FIELDS = ["merchant", "date", "time", "currency", "subtotal", "tax", "total"]


def norm(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 3)
    return " ".join(str(v).lower().split())


def item_prf(pred: list, gt: list) -> tuple[int, int, int]:
    """Items match on (normalised name, price). Returns tp, n_pred, n_gt."""
    key = lambda it: (norm(it.get("name")), norm(it.get("price")))  # noqa: E731
    gt_left = [key(i) for i in gt]
    tp = 0
    for k in (key(i) for i in pred):
        if k in gt_left:
            gt_left.remove(k)
            tp += 1
    return tp, len(pred), len(gt)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--range", default=None, help="start:end slice of the sorted ground-truth files, e.g. 0:100")
    a = ap.parse_args()

    correct, seen = defaultdict(int), defaultdict(int)
    tp = n_pred = n_gt = 0
    files = sorted(glob.glob(os.path.join(a.gt, "*.json")))
    if a.range:
        start, end = (int(x) if x else None for x in a.range.split(":"))
        files = files[start:end]
    for g in files:
        p = os.path.join(a.pred, os.path.basename(g))
        gt = json.load(open(g, encoding="utf-8"))
        pred = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        for f in FIELDS:
            if f in gt and gt[f] is not None:
                seen[f] += 1
                correct[f] += norm(pred.get(f)) == norm(gt[f])
        if gt.get("merchant"):   # secondary score: OCR spacing / punctuation errors ignored
            loose = lambda v: re.sub(r"[^a-z0-9]", "", str(v or "").lower())  # noqa: E731
            seen["merchant_loose"] += 1
            correct["merchant_loose"] += loose(pred.get("merchant")) == loose(gt["merchant"])
        if "items" in gt:
            t, np_, ng = item_prf(pred.get("items", []), gt["items"])
            tp, n_pred, n_gt = tp + t, n_pred + np_, n_gt + ng

    print(f"{len(files)} receipts")
    print("| Field | Accuracy | n |\n|---|---|---|")
    for f in FIELDS + ["merchant_loose"]:
        if seen[f]:
            print(f"| {f} | {correct[f] / seen[f]:.3f} | {seen[f]} |")
    if n_gt:
        prec = tp / n_pred if n_pred else 0.0
        rec = tp / n_gt
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        print(f"| items (P / R / F1) | {prec:.3f} / {rec:.3f} / {f1:.3f} | {n_gt} |")


if __name__ == "__main__":
    main()
