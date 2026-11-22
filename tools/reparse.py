"""Re-run only the parsing step on saved pipeline outputs (their "raw_lines"), without running OCR again.
Useful to iterate on parse.py: OCR is the slow part, parsing takes milliseconds."""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parse import parse  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pred", required=True, help="folder of pipeline.py outputs")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.pred, "*.json")))
    for f in files:
        old = json.load(open(f, encoding="utf-8"))
        new = parse(old["raw_lines"])
        new["raw_lines"] = old["raw_lines"]
        with open(os.path.join(a.out, os.path.basename(f)), "w", encoding="utf-8") as fh:
            json.dump(new, fh, ensure_ascii=False, indent=2)
    print(f"re-parsed {len(files)} files -> {a.out}")


if __name__ == "__main__":
    main()
