from decimal import Decimal
from pathlib import Path

from app import parsers

EX = Path(__file__).resolve().parent.parent / "examples"


def test_rate_sheet_ok():
    r = parsers.parse_rate_sheet((EX / "SYNTHETIC_rate_sheet.csv").read_bytes(), "f.csv")
    assert r.ok and len(r.rows) == 384


def test_margins_missing_column():
    r = parsers.parse_margins(b"a,b\n1,2", "f.csv")
    assert not r.ok


def test_overlap_grid_a():
    csv = "fico_min,fico_max,0-60\n0,100,0\n50,80,0\n"
    r = parsers.parse_grid_a(csv.encode(), "f.csv")
    assert not r.ok


def test_xlsx_rate_sheet():
    r = parsers.parse_rate_sheet((EX / "SYNTHETIC_rate_sheet.xlsx").read_bytes(), "f.xlsx")
    assert r.ok


def test_margin_required_fields():
    csv = "loan_amount_min,loan_amount_max,margin_dollar,margin_percent\n1,2,,\n"
    r = parsers.parse_margins(csv.encode(), "f.csv")
    assert not r.ok