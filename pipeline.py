"""CLI: receipt image(s) -> structured JSON (preprocess -> detect -> recognise -> lines -> parse)."""
import argparse
import glob
import json
import os

import cv2

from layout import group_lines
from ocr import get_backend
from parse import parse
from preprocess import preprocess


def read_receipt(path: str, backend) -> dict:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    words = backend(preprocess(img))
    lines = group_lines(words)
    result = parse([l.text for l in lines], [l.conf for l in lines])
    result["raw_lines"] = [l.text for l in lines]
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="image file or folder")
    ap.add_argument("--backend", choices=["paddle", "tesseract"], default="paddle")
    ap.add_argument("--lang", default=None, help="paddle: en / fr / ar ... ; tesseract: eng+fra ...")
    ap.add_argument("--out", default=None, help="output folder (one JSON per image)")
    a = ap.parse_args()

    backend = get_backend(a.backend, a.lang)
    files = ([a.input] if os.path.isfile(a.input) else
             sorted(glob.glob(os.path.join(a.input, "*.jpg")) + glob.glob(os.path.join(a.input, "*.png"))))
    for f in files:
        res = read_receipt(f, backend)
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            stem = os.path.splitext(os.path.basename(f))[0]
            with open(os.path.join(a.out, stem + ".json"), "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=2)
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.out:
        print(f"{len(files)} receipts -> {a.out}/")


if __name__ == "__main__":
    main()
