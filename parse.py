"""Rule-based receipt parsing: lines of text -> structured fields. No model needed, fully unit-tested."""
from __future__ import annotations

import re
from datetime import datetime

TOTAL_KEYS = ("total ttc", "net a payer", "net à payer", "total", "amount due", "montant")
SUBTOTAL_KEYS = ("sous-total", "sous total", "subtotal", "sub total", "total ht")
TAX_KEYS = ("tva", "vat", "tax", "taxe")
SKIP_ITEM_KEYS = TOTAL_KEYS + SUBTOTAL_KEYS + TAX_KEYS + (
    "cash", "especes", "espèces", "carte", "card", "rendu", "change", "merci", "thank")
CURRENCIES = {"tnd": "TND", "dt": "TND", "eur": "EUR", "€": "EUR", "usd": "USD", "$": "USD", "mad": "MAD"}

# 12,50 | 12.50 | 1 234,500 | 3.100 (TND uses 3 decimals)
AMOUNT = r"(?<![\d.,])(\d{1,3}(?:[  ]\d{3})*|\d+)([.,]\d{1,3})(?![\d])"
DATE_PATTERNS = [
    (r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", "dmy"),
    (r"\b(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\b", "ymd"),
    (r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\b", "dmy2"),
]
TIME = r"\b([01]?\d|2[0-3])[:h]([0-5]\d)(?::[0-5]\d)?\b"
OCR_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"})


def fix_digits(token: str) -> str:
    """Repair OCR letter/digit confusions only inside tokens that already look numeric."""
    def repl(m):
        t = m.group(0)
        return t.translate(OCR_DIGIT_FIX) if sum(c.isdigit() for c in t) >= len(t) / 2 else t
    return re.sub(r"[0-9OolISB.,]{2,}", repl, token)


def to_float(int_part: str, dec_part: str) -> float:
    return float(re.sub(r"[  ]", "", int_part) + "." + dec_part[1:])


def amounts(line: str) -> list[float]:
    return [to_float(a, b) for a, b in re.findall(AMOUNT, fix_digits(line))]


def find_date(text: str) -> str | None:
    for pat, kind in DATE_PATTERNS:
        for m in re.finditer(pat, text):
            g = [int(x) for x in m.groups()]
            try:
                if kind == "dmy":
                    d = datetime(g[2], g[1], g[0])
                elif kind == "ymd":
                    d = datetime(g[0], g[1], g[2])
                else:
                    d = datetime(2000 + g[2], g[1], g[0])
            except ValueError:
                continue
            return d.strftime("%Y-%m-%d")
    return None


def find_time(text: str) -> str | None:
    m = re.search(TIME, text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def find_currency(text: str) -> str | None:
    low = text.lower()
    for k, v in CURRENCIES.items():
        if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", low):
            return v
    return None


LETTER_FIX = {"0": "o", "1": "l", "5": "s", "8": "b"}


def fix_letters(text: str) -> str:
    """Inside words, map OCR digit confusions back to letters (T0TAL -> TOTAL); numbers are untouched."""
    return re.sub(r"(?<=[a-z])[0158]|[0158](?=[a-z])", lambda m: LETTER_FIX[m.group(0)], text)


def _has_key(line: str, keys) -> bool:
    low = fix_letters(line.lower())
    return any(re.search(rf"\b{re.escape(k)}\b", low) for k in keys)


def keyed_amount(lines: list[str], keys, exclude=()) -> float | None:
    """Last amount on the last line containing one of the keys (totals are usually at the bottom)."""
    for line in reversed(lines):
        if _has_key(line, keys) and not (exclude and _has_key(line, exclude)):
            a = amounts(line)
            if a:
                return a[-1]
    return None


def parse_item(line: str) -> dict | None:
    """'2 x LAIT 1L 3,100' / 'LAIT 1L 2 x 1,550 3,100' / 'PAIN 0,200' -> {name, qty, price}."""
    if _has_key(line, SKIP_ITEM_KEYS) or find_date(line):
        return None
    clean = fix_digits(line)
    found = list(re.finditer(AMOUNT, clean))
    if not found:
        return None
    price = to_float(*found[-1].groups())
    name_part = clean[: found[0].start()].strip(" .:-*")
    qty = 1
    m = re.match(r"^(\d+)\s*[xX*]\s*(.+)$", name_part) or re.match(r"^(.+?)\s+(\d+)\s*[xX*]\s*$", name_part)
    if m:
        a, b = m.groups()
        qty, name_part = (int(a), b) if a.isdigit() else (int(b), a)
    name = re.sub(r"\s{2,}", " ", name_part).strip(" .:-*")
    if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", name)) < 2:
        return None
    return {"name": name, "qty": qty, "price": price}


def parse(lines: list[str], confidences: list[float] | None = None, min_conf: float = 0.6) -> dict:
    confidences = confidences or [1.0] * len(lines)
    text = "\n".join(lines)
    total = keyed_amount(lines, TOTAL_KEYS, exclude=SUBTOTAL_KEYS)
    header = [l for l in lines[:5] if not amounts(l) and not find_date(l) and len(l.strip()) > 2]
    items = [it for it in (parse_item(l) for l in lines) if it]
    if total is not None:
        items = [it for it in items if it["price"] != total or it["name"].lower() not in TOTAL_KEYS]
    return {
        "merchant": header[0].strip() if header else None,
        "date": find_date(text),
        "time": find_time(text),
        "currency": find_currency(text),
        "items": items,
        "subtotal": keyed_amount(lines, SUBTOTAL_KEYS),
        "tax": keyed_amount(lines, TAX_KEYS),
        "total": total,
        "low_confidence_lines": [l for l, c in zip(lines, confidences) if c < min_conf],
    }
