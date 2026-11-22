"""Rule-based receipt parsing: lines of text -> structured fields. No model needed, fully unit-tested."""
from __future__ import annotations

import re
from datetime import datetime

TOTAL_KEYS = ("total ttc", "net a payer", "net à payer", "total", "amount due", "montant")
# strongest evidence first: the amount actually paid (after rounding)
TOTAL_PRIORITY = (
    ("payable", "amount due", "total due", "net a payer", "net à payer", "total ttc", "grand total",
     "nett total", "net total", "total rounded", "rounded total", "total to pay"),
    ("total", "montant"),
)
# lines that contain "total" but are not the receipt total
NOT_TOTAL = (r"includ\w*\s*\d+(?:\.\d+)?\s*%", r"\btotal\s*(?:gst|tax|tva|vat)\b",
             r"\b(?:qty|quantity|item|items|tender|discount|saving|savings|point|points|count|excl\w*)\b")
SUBTOTAL_KEYS = ("sous-total", "sous total", "subtotal", "sub total", "total ht")
TAX_KEYS = ("tva", "vat", "tax", "taxe")
SKIP_ITEM_KEYS = TOTAL_KEYS + SUBTOTAL_KEYS + TAX_KEYS + (
    "cash", "especes", "espèces", "carte", "card", "rendu", "change", "merci", "thank")
CURRENCIES = {"tnd": "TND", "dt": "TND", "eur": "EUR", "€": "EUR", "usd": "USD", "$": "USD", "mad": "MAD"}

# 12,50 | 12.50 | 1 234,500 | 3.100 (TND uses 3 decimals)
AMOUNT = r"(?<![\d.,])(\d{1,3}(?:[  ]\d{3})*|\d+)([.,]\d{1,3})(?![\d])(?!\s*%)"
# a year may be glued to the time that follows it on receipts: "15/01/201911:05:16" -> 2019 + 11:05
_END = r"(?=$|\D|\d{1,2}[:h])"
DATE_PATTERNS = [
    (r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-]((?:19|20)\d{2})" + _END, "dmy"),
    (r"(?<!\d)((?:19|20)\d{2})[/.-](\d{1,2})[/.-](\d{1,2})" + _END, "ymd"),
    (r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})" + _END, "dmy2"),
]
TIME = r"(?<![\d:])([01]?\d|2[0-3])[:h]([0-5]\d)(?::[0-5]\d)?(?!\d)"
OCR_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"})


def fix_digits(token: str) -> str:
    """Repair OCR letter/digit confusions only inside tokens that already look numeric."""
    def repl(m):
        t = m.group(0)
        return t.translate(OCR_DIGIT_FIX) if sum(c.isdigit() for c in t) >= len(t) / 2 else t
    return re.sub(r"[0-9OolISB.,]{2,}", repl, token)


def to_float(int_part: str, dec_part: str) -> float:
    return float(re.sub(r"[  ]", "", int_part) + "." + dec_part[1:])


CURRENCY_PREFIX = r"(?:(?<=[\s:(])|^)(?:RM|\$|S)\s?(?=\d+[.,]\d{2}(?!\d))"   # "RM8.20", "$8.20", OCR "S8.20"


def amounts(line: str) -> list[float]:
    return [to_float(a, b) for a, b in re.findall(AMOUNT, fix_digits(re.sub(CURRENCY_PREFIX, "", line)))]


MONTHS = {"jan": 1, "feb": 2, "fev": 2, "fév": 2, "mar": 3, "apr": 4, "avr": 4, "may": 5, "mai": 5,
          "jun": 6, "jui": 6, "jul": 7, "aug": 8, "aou": 8, "aoû": 8, "sep": 9, "oct": 10, "nov": 11,
          "dec": 12, "déc": 12}
MONTH_DATE = r"(?<!\d)(\d{1,2})[ /.-]*([A-Za-zéû]{3})[A-Za-zéû]*[ /.-]*((?:19|20)\d{2}|\d{2})" + _END


def _month_name_date(text: str) -> str | None:
    """'22 MAR 18', '27/MAR/2018', '7 mars 2026' -> ISO date."""
    for m in re.finditer(MONTH_DATE, text):
        d, mon, y = m.groups()
        month = MONTHS.get(mon.lower())
        if month is None:
            continue
        if mon.lower() == "jui":   # 'juin' and 'juillet' share a prefix
            month = 7 if "juil" in text[m.start():m.end()].lower() else 6
        year = int(y) + (2000 if len(y) == 2 else 0)
        try:
            return datetime(year, month, int(d)).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def find_date(text: str) -> str | None:
    named = _month_name_date(text)
    if named:
        return named
    for pat, kind in DATE_PATTERNS:
        for m in re.finditer(pat, text):
            g = [int(x) for x in m.groups()]
            try:
                if kind == "dmy":   # day-first; fall back to US month-first only when day-first is impossible
                    d = datetime(g[2], g[1], g[0]) if g[1] <= 12 else datetime(g[2], g[0], g[1])
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


STRONG_TOTAL = r"\bamount\b.*\bdue\b|\btotal\b.*\bdue\b"
WEAK_TOTAL = r"\btotal|\bmontant\b"   # prefix match: OCR often merges words ("TOTALAMOUNT")
PAYMENT = r"\b(?:cash|visa|master\w*|card|paid|credit|debit|carte|esp[eè]ces)\b"


def find_total(lines: list[str]) -> float | None:
    """Score every candidate total line and keep the best:
    strong keys (payable / amount due / grand total ...) > amount confirmed by a payment line
    (CASH / VISA ... with the same value) > lower position on the receipt."""
    payments = {a for line in lines if re.search(PAYMENT, fix_letters(line.lower())) for a in amounts(line)}
    best, best_score = None, -1.0
    for i, line in enumerate(lines):
        low = fix_letters(line.lower())
        if _has_key(line, SUBTOTAL_KEYS) or any(re.search(p, low) for p in NOT_TOTAL):
            continue
        if _has_key(line, TOTAL_PRIORITY[0]) or re.search(STRONG_TOTAL, low):
            level = 2
        elif re.search(WEAK_TOTAL, low):
            level = 1
        else:
            continue
        nonzero = [a for a in amounts(line) if a > 0]
        if not nonzero:
            continue
        amount = nonzero[-1]
        score = level * 10 + (5 if amount in payments else 0) + i / max(len(lines), 1)
        if score > best_score:
            best, best_score = amount, score
    return best


COMPANY_MARKERS = (r"\bsdn\b", r"\bbhd\b", r"\bs/b\b", r"\benterprise", r"\btrading\b", r"\brestaurant",
                   r"\bmart\b", r"\bstore", r"\bshop\b", r"\bmarket", r"\bsarl\b", r"\bsuarl\b", r"\bltd\b",
                   r"\bcompany\b", r"\bperniagaan\b", r"\bkedai\b", r"\bhotel\b", r"\bcaf[eé]\b",
                   r"\bbakery\b", r"\bpharmac", r"\bstation\b", r"\bcent(?:re|er)\b", r"\bhardware\b")
NOT_MERCHANT = r"\b(?:copy|invoice|receipt|re[cç]u|facture|tel|fax|gst|roc|reg|date|cashier|welcome|bienvenue)\b"


def find_merchant(lines: list[str], top: int = 8) -> str | None:
    """Company line among the header lines: prefer one with a company marker (SDN BHD, MART, ...),
    else the first mostly-uppercase text line. A trailing registration number in brackets is dropped."""
    cands = []
    for line in lines[:top]:
        t = line.strip()
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", t)
        if len(letters) < 4 or re.search(NOT_MERCHANT, t.lower()) or amounts(t) or find_date(t):
            continue
        cands.append(t)
    pick = next((c for c in cands if any(re.search(m, c.lower()) for m in COMPANY_MARKERS)), None)
    if pick is None:
        pick = next((c for c in cands
                     if sum(ch.isupper() for ch in c) >= 0.6 * len(re.sub(r"[^A-Za-zÀ-ÿ]", "", c))), None)
    if pick is None:
        return None
    m = re.search(r"\b(?:sdn\.?\s*bhd\.?|bhd\.?|s/b)", pick, flags=re.I)
    if m:                                         # merged header lines: keep up to the legal form
        pick = pick[: m.end()]
    pick = re.sub(r"\s*\([^)]*\)\s*$", "", pick)  # trailing "(519537-X)"
    return re.sub(r"\s{2,}", " ", pick).strip(" .,-*")


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
    total = find_total(lines)
    items = [it for it in (parse_item(l) for l in lines) if it]
    if total is not None:
        items = [it for it in items if it["price"] != total or it["name"].lower() not in TOTAL_KEYS]
    return {
        "merchant": find_merchant(lines),
        "date": find_date(text),
        "time": find_time(text),
        "currency": find_currency(text),
        "items": items,
        "subtotal": keyed_amount(lines, SUBTOTAL_KEYS),
        "tax": keyed_amount(lines, TAX_KEYS),
        "total": total,
        "low_confidence_lines": [l for l, c in zip(lines, confidences) if c < min_conf],
    }
