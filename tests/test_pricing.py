from decimal import Decimal

import pytest

from app.pricing import (
    cell_adjustment,
    find_margin_row,
    grid_a_llpa,
    grid_b_llpa,
    margin_points,
    run_pricing,
)
from app.parsers import parse_grid_a


@pytest.fixture
def grids(seeded):
    ga = seeded.load_grid_a()
    gb = seeded.load_grid_b()
    return ga, gb


def test_blank_cell_ineligible(grids):
    ga, _ = grids
    # force a blank by using row with NA at high cltv - use low fico high cltv
    _, _, reasons = grid_a_llpa(625, Decimal("88"), ga)
    assert reasons


def test_na_cell_reason(grids):
    ga, _ = grids
    _, _, reasons = grid_a_llpa(625, Decimal("87"), ga)
    assert any("grid A" in r for r in reasons)


def test_grid_b_missing_manufactured(grids):
    _, gb = grids
    borrower = {"fico": 740, "dti": 35}
    prop = {"occupancy": "primary", "property_type": "manufactured"}
    _, _, reasons = grid_b_llpa(borrower, prop, Decimal(100000), Decimal(50), gb)
    assert reasons


def test_margin_out_of_range(seeded):
    margins = seeded.load_margins()
    row, err = find_margin_row(Decimal(5000), margins)
    assert row is None and err


def test_margin_points():
    row = {"margin_dollar": Decimal("795"), "margin_percent": Decimal("0.125")}
    pts = margin_points(row, Decimal(150000))
    assert pts.quantize(Decimal("0.001")) == Decimal("0.655")


def test_final_price_worked(seeded, grids):
    ga, gb = grids
    rate = {
        "product_id": "P",
        "investor": "I",
        "lock_period_days": 30,
        "base_rate": Decimal("7.5"),
        "base_price": Decimal("100"),
    }
    margins = seeded.load_margins()
    from app.pricing import price_one_rate_row

    borrower = {"fico": 760, "dti": 32}
    prop = {"value": 650000, "occupancy": "primary", "property_type": "single_family"}
    cltv = Decimal("72.30769230769230769230769231")
    r = price_one_rate_row(rate, borrower, prop, Decimal(150000), cltv, ga, gb, margins)
    assert r["eligible"]
    assert r["final_price"] is not None


def test_lock_filter(seeded):
    payload = run_pricing(
        {"heloc_amount": 150000, "first_lien_balance": 320000, "lock_period_days": 45},
        {"fico": 760, "dti": 32},
        {"value": 650000, "occupancy": "primary", "property_type": "single_family"},
        seeded.load_rate_sheet(),
        seeded.load_grid_a(),
        seeded.load_grid_b(),
        seeded.load_margins(),
    )
    locks = {r["lock_period_days"] for r in payload["results"]}
    assert locks == {45}