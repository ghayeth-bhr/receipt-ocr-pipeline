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
python evaluate.py --pred out/ --gt data/gt/
```

The parser has unit tests that need no OCR model:

```bash
pytest -q
```

## Evaluation

`evaluate.py` reports exact-match accuracy per field (`merchant`, `date`, `total`, ...)
and item-level precision / recall. Public datasets that fit: **SROIE** (company, date,
address, total) and **CORD** (line items). Fill the table after running it:

| Field | Accuracy |
|---|---|
| date | |
| total | |
| merchant | |
| items (F1) | |

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
