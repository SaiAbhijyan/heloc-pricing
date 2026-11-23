#!/usr/bin/env python3
"""Write SYNTHETIC example CSV/XLSX (deterministic seed 42)."""
from __future__ import annotations

import csv
import json
import random
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
random.seed(42)

CLTV = ["0-60", "60.01-70", "70.01-75", "75.01-80", "80.01-85", "85.01-90"]
FICO_ROWS = [
    (620, 639),
    (640, 659),
    (660, 679),
    (680, 699),
    (700, 719),
    (720, 739),
    (740, 759),
    (760, 779),
    (780, 799),
    (800, None),
]

PRODUCTS = [
    "HELOC-10YR-DRAW-20YR-REPAY",
    "HELOC-PIGGYBACK",
    "HELOC-FIXED-RATE-LOCK",
    "HELOC-INVESTOR",
]
INVESTORS = ["BayView", "PennyMac", "Citadel", "Angel Oak"]
LOCKS = [15, 30, 45, 60]


def rate_sheet_rows():
    rows = []
    rate = Decimal("7.25")
    for p in PRODUCTS:
        for inv in INVESTORS:
            for i, lock in enumerate(LOCKS):
                adj = Decimal(i) * Decimal("0.18") + Decimal(hash((p, inv)) % 7) / Decimal("100")
                br = (rate + adj + Decimal(lock) / Decimal("400")).quantize(Decimal("0.001"))
                bp = (Decimal("100") + Decimal(hash((inv, lock, p)) % 30) / Decimal("100") - Decimal(lock) / Decimal("200")).quantize(Decimal("0.001"))
                rows.append((p, inv, lock, br, bp))
    return rows


def grid_a_rows():
    rows = []
    for fmin, fmax in FICO_ROWS:
        cells = []
        for j, _ in enumerate(CLTV):
            if fmin < 640 and j >= 4:
                cells.append("NA")
            elif fmin < 660 and j == 5:
                cells.append("NA")
            else:
                hit = -Decimal((fmax or 820) - fmin + j) / Decimal("80")
                cells.append(str(hit.quantize(Decimal("0.001"))))
        rows.append((fmin, "" if fmax is None else fmax, cells))
    return rows


def grid_b_rows():
    rows = []
    occ = [("occupancy", "primary"), ("occupancy", "second_home"), ("occupancy", "investment")]
    ptype = [
        ("property_type", "single_family"),
        ("property_type", "pud"),
        ("property_type", "condo"),
        ("property_type", "2_4_unit"),
        ("property_type", "manufactured"),
    ]
    fico_b = [
        f"{lo}-{hi}" if hi is not None else f"{lo}+"
        for lo, hi in FICO_ROWS
    ]
    amt_b = ["25000-99999", "100000-249999", "250000-499999", "500000-1000000"]
    dti_b = ["0-36", "36.01-43", "43.01-50"]
    for attr, band in occ + ptype:
        cells = []
        for j, col in enumerate(CLTV):
            if band == "manufactured":
                cells.append("NA")
            elif band == "investment" and "condo" in str(band):
                cells.append("NA")
            elif band == "investment" and j >= 4:
                cells.append(str(Decimal("-0.75")))
            elif band == "condo" and j >= 3:
                cells.append(str(Decimal("-0.5")))
            else:
                cells.append(str(Decimal("-0.125") * (j + 1)))
        rows.append((attr, band, cells))
    for band in fico_b:
        cells = [str(Decimal("-0.05") * (j + 1)) for j in range(len(CLTV))]
        rows.append(("fico", band, cells))
    for band in amt_b:
        cells = [str(Decimal("-0.02") * j) for j in range(len(CLTV))]
        rows.append(("loan_amount", band, cells))
    for band in dti_b:
        cells = []
        for j in range(len(CLTV)):
            extra = Decimal("-0.35") if band.startswith("43") and j >= 3 else Decimal("-0.1") * j
            cells.append(str(extra))
        rows.append(("dti", band, cells))
    return rows


def margin_rows():
    return [
        (25000, 99999, Decimal("495"), Decimal("0.15")),
        (100000, 249999, Decimal("795"), Decimal("0.125")),
        (250000, 499999, Decimal("995"), Decimal("0.1")),
        (500000, 1000000, Decimal("1495"), Decimal("0.085")),
    ]


def write_csv(path: Path, header: list, body: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def main():
    EX.mkdir(exist_ok=True)
    rs = rate_sheet_rows()
    write_csv(
        EX / "SYNTHETIC_rate_sheet.csv",
        list(
            [
                "product_id",
                "investor",
                "lock_period_days",
                "base_rate",
                "base_price",
            ]
        ),
        rs,
    )
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "product_id",
            "investor",
            "lock_period_days",
            "base_rate",
            "base_price",
        ]
    )
    for row in rs:
        ws.append(list(row))
    wb.save(EX / "SYNTHETIC_rate_sheet.xlsx")
    ga = grid_a_rows()
    write_csv(
        EX / "SYNTHETIC_grid_a.csv",
        ["fico_min", "fico_max", *CLTV],
        [(r[0], r[1], *r[2]) for r in ga],
    )
    gb = grid_b_rows()
    write_csv(
        EX / "SYNTHETIC_grid_b.csv",
        ["attribute", "band", *CLTV],
        [(r[0], r[1], *r[2]) for r in gb],
    )
    mg = margin_rows()
    write_csv(
        EX / "SYNTHETIC_margins.csv",
        ["loan_amount_min", "loan_amount_max", "margin_dollar", "margin_percent"],
        mg,
    )
    # EXAMPLE_ aliases for brief
    for name in ("EXAMPLE_rate_sheet.csv", "EXAMPLE_grid_a.csv", "EXAMPLE_grid_b.csv", "EXAMPLE_margins.csv"):
        src = EX / ("SYNTHETIC_" + name.replace("EXAMPLE_", ""))
        if src.exists():
            (EX / name).write_text(src.read_text())
    scenarios = [
        {
            "name": "clean_eligible",
            "loan": {"heloc_amount": 150000, "first_lien_balance": 320000, "lock_period_days": 45},
            "borrower": {"fico": 760, "dti": 32},
            "property": {"value": 650000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "high_cltv",
            "loan": {"heloc_amount": 200000, "first_lien_balance": 450000},
            "borrower": {"fico": 720, "dti": 38},
            "property": {"value": 700000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "low_fico",
            "loan": {"heloc_amount": 75000, "first_lien_balance": 180000},
            "borrower": {"fico": 625, "dti": 40},
            "property": {"value": 350000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "investment_condo",
            "loan": {"heloc_amount": 120000, "first_lien_balance": 0},
            "borrower": {"fico": 700, "dti": 42},
            "property": {"value": 400000, "occupancy": "investment", "property_type": "condo"},
        },
        {
            "name": "high_dti",
            "loan": {"heloc_amount": 90000, "first_lien_balance": 220000},
            "borrower": {"fico": 710, "dti": 48},
            "property": {"value": 480000, "occupancy": "primary", "property_type": "pud"},
        },
        {
            "name": "jumbo_line",
            "loan": {"heloc_amount": 550000, "first_lien_balance": 400000},
            "borrower": {"fico": 780, "dti": 28},
            "property": {"value": 1200000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "out_of_margin_range",
            "loan": {"heloc_amount": 15000, "first_lien_balance": 100000},
            "borrower": {"fico": 740, "dti": 35},
            "property": {"value": 280000, "occupancy": "primary", "property_type": "single_family"},
        },
    ]
    (EX / "SYNTHETIC_scenarios.json").write_text(json.dumps({"scenarios": scenarios}, indent=2))
    print("wrote synthetic files to", EX)


if __name__ == "__main__":
    main()