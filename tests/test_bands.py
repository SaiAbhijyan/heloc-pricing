from decimal import Decimal

import pytest

from app.bands import in_band, parse_band_label, check_band_list_overlaps
from app.pricing import calc_cltv


def test_cltv():
    c = calc_cltv(Decimal(320000), Decimal(150000), Decimal(650000))
    assert c.quantize(Decimal("0.01")) == Decimal("72.31")


def test_in_band_inclusive():
    lo, hi = parse_band_label("60.01-70")
    assert in_band(Decimal("60.01"), lo, hi)
    assert in_band(Decimal("70"), lo, hi)
    assert not in_band(Decimal("60"), lo, hi)
    assert not in_band(Decimal("70.01"), lo, hi)


def test_open_max():
    lo, hi = parse_band_label("90.01+")
    assert hi is None
    assert in_band(Decimal("95"), lo, hi)


def test_overlap_reject():
    errs = check_band_list_overlaps(
        [(Decimal(0), Decimal(60)), (Decimal(50), Decimal(80))], "x"
    )
    assert errs