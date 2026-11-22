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
    assert find_date("4/22/2018") == "2018-04-22"
    assert find_time("14/03/2026 18h42") == "18:42"


def test_month_name_dates():
    assert find_date("DATE: 22 MAR 18") == "2018-03-22"
    assert find_date("27/MAR/2018 10:15") == "2018-03-27"
    assert find_date("le 7 mars 2026") == "2026-03-07"
    assert find_date("3 juillet 2026") == "2026-07-03"
    assert find_date("TOTAL 12 MARKS") is None


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


def test_date_glued_to_time():
    assert find_date("Date :15/01/201911:05:16AM") == "2019-01-15"
    assert find_date("03/03/1810:18 001-1541798") == "2018-03-03"
    assert find_date("STORED 22 Mar 1802:15 PM") == "2018-03-22"


def test_total_prefers_payable_and_skips_tax_lines():
    lines = ["Total Amt Incl. GST @ 6%: 6.36", "Rounding Adjustment: -0.01",
             "Total Amt Payable: 6.35", "Paid Amount: 10.00", "TOTAL INCLUDES 6% GST 0.36"]
    assert parse(lines)["total"] == 6.35


def test_total_ignores_zero_and_quantity_lines():
    assert parse(["Total Qty: 3", "VISA CARD TOTAL: 170.00 0.00"])["total"] == 170.0
    assert parse(["TOTAL INCLUDES 6% GST 2.20", "Total Rounded 38.90"])["total"] == 38.9


def test_merchant_skips_noise_and_keeps_legal_form():
    lines = ["tan chay yee", "***COPY***", "ACME TRADING SDN BHD NO 2, JALAN BAYU 4", "ROC NO: 538358-H"]
    assert parse(lines)["merchant"] == "ACME TRADING SDN BHD"
    assert parse(["y", "99 SPEED MART S/B (519537-X)", "LOT 2811"])["merchant"] == "99 SPEED MART S/B"


def test_total_confirmed_by_payment_line_and_currency_prefix():
    lines = ["Total (RM): 436.20", "CASH: 436.20", "GST Summary Total 24.69"]
    assert parse(lines)["total"] == 436.2
    assert parse(["Nett Total: S6.60", "CASH $6.60"])["total"] == 6.6
    assert parse(["TOTALAMOUNT 4.20"])["total"] == 4.2
    assert parse(["Amount INCLUSIVE Due 30.25 0.00"])["total"] == 30.25
