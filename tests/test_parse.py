import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parse import amounts, find_date, find_time, fix_digits, parse, parse_item  # noqa: E402

RECEIPT = [
    "CARREFOUR MARKET",
    "Av. Habib Bourguiba, Sousse",
    "14/03/2026  18:42",
    "2 x LAIT DEMI ECREME 1L   3,100",
    "PAIN BAGUETTE             0,200",
    "SOUS-TOTAL                3,300",
    "TVA 19%                   0,527",
    "TOTAL TTC                 3,300 DT",
    "ESPECES                   5,000",
]


def test_amounts_comma_and_dot():
    assert amounts("TOTAL 12,50") == [12.5]
    assert amounts("TOTAL 12.50") == [12.5]
    assert amounts("NET A PAYER 1 234,500") == [1234.5]


def test_fix_digits_only_numeric_tokens():
    assert fix_digits("T0TAL 6,2O") == "T0TAL 6,20"
    assert fix_digits("SOUS-TOTAL") == "SOUS-TOTAL"


def test_dates_and_time():
    assert find_date("le 14/03/2026") == "2026-03-14"
    assert find_date("2026-03-14") == "2026-03-14"
    assert find_date("31/02/2026") is None
    assert find_time("14/03/2026 18h42") == "18:42"


def test_item_with_quantity():
    assert parse_item("2 x LAIT DEMI ECREME 1L   3,100") == {"name": "LAIT DEMI ECREME 1L", "qty": 2, "price": 3.1}


def test_total_lines_are_not_items():
    assert parse_item("TOTAL TTC 3,300") is None
    assert parse_item("TVA 19% 0,527") is None


def test_full_receipt():
    r = parse(RECEIPT)
    assert r["merchant"] == "CARREFOUR MARKET"
    assert r["date"] == "2026-03-14"
    assert r["time"] == "18:42"
    assert r["currency"] == "TND"
    assert r["total"] == 3.3
    assert r["subtotal"] == 3.3
    assert r["tax"] == 0.527
    assert [i["name"] for i in r["items"]] == ["LAIT DEMI ECREME 1L", "PAIN BAGUETTE"]


def test_low_confidence_lines_are_reported():
    r = parse(["SHOP", "T0TAL 6,2O"], confidences=[0.99, 0.41])
    assert r["low_confidence_lines"] == ["T0TAL 6,2O"]
    assert r["total"] == 6.2
