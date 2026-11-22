# Receipt / Label OCR Pipeline

A small, readable pipeline for **structured receipt and document reading**:

```
image ──► preprocess ──► text detection ──► text recognition ──► line reconstruction ──► parsing ──► JSON
          (OpenCV)        (PaddleOCR det)     (PaddleOCR rec)      (layout.py)            (parse.py)
```

```json
{
  "merchant": "CARREFOUR MARKET",
  "date": "2026-03-14",
  "time": "18:42",
  "currency": "TND",
  "items": [{"name": "LAIT DEMI ECREME 1L", "qty": 2, "price": 3.1}],
  "subtotal": null,
  "tax": 0.95,
  "total": 6.2,
  "low_confidence_lines": ["T0TAL 6,2O"]
}
```

## Design

- **Detection and recognition are separate stages** (PaddleOCR det + rec), so each can be
  evaluated and swapped independently. A Tesseract backend is provided as a fallback.
- **Line reconstruction** groups word boxes into reading-order lines using vertical
  overlap, because receipts are column-aligned (`ITEM ........ PRICE`).
- **Parsing is rule-based and testable without any model**: dates, times, amounts,
  totals, tax and item lines are extracted with normalised regexes (comma or dot decimals,
  OCR confusions such as `O`→`0`), with keyword lists in English and French.
- **Confidence is kept**: lines whose recognition confidence is below a threshold are
  reported in `low_confidence_lines` instead of being silently parsed.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# one image -> JSON on stdout
python pipeline.py data/samples/receipt_01.jpg

# a folder -> one JSON per image in out/
python pipeline.py data/samples --out out/

# Tesseract backend instead of PaddleOCR
python pipeline.py data/samples/receipt_01.jpg --backend tesseract

# field-level evaluation against ground truth JSON files with the same stem
python evaluate.py --pred out/ --gt data/gt/ [--range 100:]

# SROIE ground truth, and re-parsing saved OCR output after changing parse.py (no OCR re-run)
python tools/sroie_to_gt.py --meta metadata.jsonl --out data/gt
python tools/reparse.py --pred out/ --out out_reparsed/
```

PaddleOCR uses the fast PP-OCRv5 *mobile* models by default; `--size server` selects the larger ones.

The parser has unit tests that need no OCR model:

```bash
pytest -q
```

## Evaluation

`evaluate.py` reports exact-match accuracy per field (`merchant`, `date`, `total`, ...)
and item-level precision / recall when the ground truth has line items (e.g. CORD).

### Results on SROIE 2019 (test split, 347 scanned receipts)

**Setup:** PaddleOCR 3.7 with the PP-OCRv5 *mobile* detection + recognition models, CPU only
(Intel Core i7-12650HX, ~20 s per receipt including pre-processing). Labels from the SROIE test
set (company, date, total), converted with `tools/sroie_to_gt.py`; dates normalised to ISO,
totals as numbers. Merchant is an exact match after case and whitespace normalisation;
`merchant (loose)` also ignores spaces and punctuation, to separate OCR spacing errors
(`PERNIAGAANZHENG HUI`) from parsing errors.

To avoid tuning the rules on the numbers they are judged on, the receipts are split by file
name: the first 100 were used to study errors and improve `parse.py`, the other **247 were
held out** and only scored at the end. The OCR ran once; `tools/reparse.py` re-runs only the
parsing on the saved OCR lines.

| Field | First parser (held-out 247) | Improved parser (held-out 247) | Improved parser (all 347) |
|---|---|---|---|
| date | 0.563 | **0.874** | 0.867 |
| total | 0.656 | **0.713** | 0.703 |
| merchant (exact) | 0.190 | **0.433** | 0.415 |
| merchant (loose) | 0.239 | **0.656** | 0.646 |

What changed between the two parsers (all covered by unit tests):
- **Dates glued to times** (`15/01/201911:05:16AM`) and month-name dates (`22 MAR 18`) are read;
  only plausible years (19xx / 20xx) are accepted, which removed dates like `1810-03-03`.
- **Totals are scored, not just taken from the last "total" line:** strong keys (payable,
  amount due, grand total, rounded) win; a total confirmed by a payment line (CASH / VISA with
  the same amount) is preferred; tax and quantity lines (`TOTAL INCLUDES 6% GST`, `Total Qty`)
  are excluded; currency prefixes (`RM`, `$`, OCR `S8.20`) are stripped before parsing.
- **Merchant** is chosen among the header lines by company markers (SDN BHD, S/B, MART,
  ENTERPRISE, ...) instead of taking the first line, which was often noise (`***COPY***`).

**Remaining errors** are mostly OCR misreads that rules cannot fix (`NEIWORK` for `NETWORK`,
`TOT' 0o RM`), merged or split header lines, and totals printed without a keyword. Next steps:
the PP-OCRv5 *server* models (slower, more accurate), and a layout-aware or VLM extraction
stage compared against these rules on the same split.

## Project layout

```
preprocess.py   grayscale, denoise, deskew, contrast (OpenCV)
ocr.py          detection + recognition backends (PaddleOCR, Tesseract) -> word boxes + confidence
layout.py       group word boxes into reading-order lines
parse.py        rule-based field extraction -> dict
pipeline.py     CLI: image(s) -> JSON
evaluate.py     field-level accuracy against ground truth
tests/          parser unit tests
```

## References

Ideas inspired by (no code copied):
- [ReceiptManager/receipt-parser-legacy](https://github.com/ReceiptManager/receipt-parser-legacy) — keyword-driven receipt parsing.
- [knipknap/receiptparser](https://github.com/knipknap/receiptparser) — configurable regex parsing of totals and dates.
- [clovaai/cord](https://github.com/clovaai/cord) — receipt dataset for post-OCR parsing; [SROIE (ICDAR 2019)](https://rrc.cvc.uab.es/?ch=13).
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), [Tesseract](https://github.com/tesseract-ocr/tesseract).

## License

MIT © Ghayeth Ben Haj Rhouma
