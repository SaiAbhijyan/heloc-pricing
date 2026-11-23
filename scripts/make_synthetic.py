#!/usr/bin/env python3
"""Write SYNTHETIC example CSV/XLSX (deterministic seed 42)."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"

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
INVESTORS = [
    "Northwind Capital (synthetic)",
    "Bluefin Lending (synthetic)",
    "Cedar Trust (synthetic)",
    "Harbor Point Funding (synthetic)",
]
LOCKS = [15, 30, 45, 60]

PRODUCT_RATE_BUMP = {
    "HELOC-10YR-DRAW-20YR-REPAY": Decimal("0"),
    "HELOC-PIGGYBACK": Decimal("0.25"),
    "HELOC-FIXED-RATE-LOCK": Decimal("0.75"),
    "HELOC-INVESTOR": Decimal("1.1"),
}


LADDER_RUNGS = 6
RATE_STEP = Decimal("0.125")
PRICE_STEP = Decimal("0.4375")


def rate_sheet_rows():
    rows = []
    for pi, p in enumerate(PRODUCTS):
        for ii, inv in enumerate(INVESTORS):
            for lock in LOCKS:
                lock_pen = (Decimal(lock) - Decimal("15")) / Decimal("320")
                inv_off = Decimal(ii) * Decimal("0.12")
                prod_off = Decimal(pi) * Decimal("0.08")
                low_rate = (
                    Decimal("7.25")
                    + PRODUCT_RATE_BUMP[p]
                    + Decimal(ii) * Decimal("0.08")
                    + (Decimal(lock) - Decimal("15")) / Decimal("200")
                )
                low_price = Decimal("98.25") + inv_off - lock_pen + prod_off
                for k in range(LADDER_RUNGS):
                    br = (low_rate + k * RATE_STEP).quantize(Decimal("0.001"))
                    bp = (low_price + k * PRICE_STEP).quantize(Decimal("0.001"))
                    rows.append((p, inv, lock, br, bp))
    return rows


def grid_a_cell(fmin: int, fmax: int | None, j: int) -> str:
    if fmin < 660 and j >= 4:
        return "NA"
    if fmin < 640 and j >= 5:
        return "NA"
    if fmax is None and j == 0:
        return "0.000"
    if fmin < 640 and j == 4:
        return "-2.250"
    drop = Decimal(820 - (fmax or 820)) / Decimal(50)
    cltv_hit = Decimal(j) * Decimal("0.22")
    val = -(drop / Decimal("4") + cltv_hit)
    return str(val.quantize(Decimal("0.001")))


def grid_a_rows():
    rows = []
    for fmin, fmax in FICO_ROWS:
        cells = [grid_a_cell(fmin, fmax, j) for j in range(len(CLTV))]
        rows.append((fmin, "" if fmax is None else fmax, cells))
    return rows


def grid_b_rows():
    rows = []

    def occ_cell(band: str, j: int) -> str:
        if band == "primary":
            return "0.000"
        if band == "second_home":
            return str((Decimal("-0.250") - Decimal(j) * Decimal("0.1")).quantize(Decimal("0.001")))
        if j >= 3:
            return "NA"
        return str((Decimal("-0.750") - Decimal(j) * Decimal("0.2")).quantize(Decimal("0.001")))

    for band in ("primary", "second_home", "investment"):
        rows.append(("occupancy", band, [occ_cell(band, j) for j in range(len(CLTV))]))

    def ptype_cell(band: str, j: int) -> str:
        if band in ("single_family", "pud"):
            return "0.000"
        if band == "manufactured":
            return "NA"
        if band == "2_4_unit" and j >= 4:
            return "NA"
        if band == "condo":
            return str((Decimal("-0.125") - Decimal(j) * Decimal("0.075")).quantize(Decimal("0.001")))
        return str((Decimal("-0.375") - Decimal(j) * Decimal("0.15")).quantize(Decimal("0.001")))

    for band in ("single_family", "pud", "condo", "2_4_unit", "manufactured"):
        rows.append(("property_type", band, [ptype_cell(band, j) for j in range(len(CLTV))]))

    for fmin, fmax in FICO_ROWS:
        band = f"{fmin}-{fmax}" if fmax is not None else f"{fmin}+"
        if fmin >= 700:
            cells = ["0.000"] * len(CLTV)
        else:
            cells = [
                str((Decimal("-0.125") - Decimal((700 - fmin) / 40) * Decimal(j) * Decimal("0.05")).quantize(Decimal("0.001")))
                for j in range(len(CLTV))
            ]
        rows.append(("fico", band, cells))

    amt_bands = ["25000-99999", "100000-249999", "250000-499999", "500000-1000000"]
    for bi, band in enumerate(amt_bands):
        cells = []
        for j in range(len(CLTV)):
            if bi == 0:
                cells.append("-0.250")
            elif bi == 1:
                cells.append("0.000")
            elif bi == 2:
                cells.append("-0.125")
            elif j >= 4:
                cells.append("NA")
            else:
                cells.append("-0.375")
        rows.append(("loan_amount", band, cells))

    for bi, band in enumerate(("0-36", "36.01-43", "43.01-50")):
        cells = []
        for j in range(len(CLTV)):
            if bi == 0:
                cells.append("0.000")
            elif bi == 1:
                cells.append(
                    str((Decimal("-0.125") - Decimal(j) * Decimal("0.05")).quantize(Decimal("0.001")))
                )
            elif j >= 4:
                cells.append("NA")
            else:
                cells.append(
                    str((Decimal("-0.375") - Decimal(j) * Decimal("0.15")).quantize(Decimal("0.001")))
                )
        rows.append(("dti", band, cells))
    return rows


def margin_rows():
    return [
        (25000, 99999, Decimal("495"), Decimal("0.150")),
        (100000, 249999, Decimal("795"), Decimal("0.125")),
        (250000, 499999, Decimal("995"), Decimal("0.100")),
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
        ["product_id", "investor", "lock_period_days", "base_rate", "base_price"],
        rs,
    )
    wb = Workbook()
    ws = wb.active
    ws.append(["product_id", "investor", "lock_period_days", "base_rate", "base_price"])
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
    scenarios = [
        {
            "name": "Clean eligible (primary SF)",
            "loan": {"heloc_amount": 150000, "first_lien_balance": 320000, "lock_period_days": 45},
            "borrower": {"fico": 760, "dti": 32},
            "property": {"value": 650000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "High CLTV (NA cells)",
            "loan": {"heloc_amount": 100000, "first_lien_balance": 335000},
            "borrower": {"fico": 650, "dti": 38},
            "property": {"value": 500000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "CLTV above max band",
            "loan": {"heloc_amount": 60000, "first_lien_balance": 400000},
            "borrower": {"fico": 720, "dti": 38},
            "property": {"value": 500000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "Low FICO (outside bands)",
            "loan": {"heloc_amount": 75000, "first_lien_balance": 180000},
            "borrower": {"fico": 615, "dti": 40},
            "property": {"value": 350000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "Investment condo",
            "loan": {"heloc_amount": 80000, "first_lien_balance": 310000},
            "borrower": {"fico": 700, "dti": 42},
            "property": {"value": 500000, "occupancy": "investment", "property_type": "condo"},
        },
        {
            "name": "Investment condo low CLTV",
            "loan": {"heloc_amount": 440000, "first_lien_balance": 0},
            "borrower": {"fico": 700, "dti": 42},
            "property": {"value": 800000, "occupancy": "investment", "property_type": "condo"},
        },
        {
            "name": "High DTI (NA)",
            "loan": {"heloc_amount": 130000, "first_lien_balance": 280000},
            "borrower": {"fico": 710, "dti": 47},
            "property": {"value": 500000, "occupancy": "primary", "property_type": "pud"},
        },
        {
            "name": "Jumbo line (500k+ band)",
            "loan": {"heloc_amount": 550000, "first_lien_balance": 400000},
            "borrower": {"fico": 780, "dti": 28},
            "property": {"value": 1200000, "occupancy": "primary", "property_type": "single_family"},
        },
        {
            "name": "Out of margin range",
            "loan": {"heloc_amount": 15000, "first_lien_balance": 100000},
            "borrower": {"fico": 740, "dti": 35},
            "property": {"value": 280000, "occupancy": "primary", "property_type": "single_family"},
        },
    ]
    (EX / "SYNTHETIC_scenarios.json").write_text(json.dumps({"scenarios": scenarios}, indent=2))
    print("wrote synthetic files to", EX)


if __name__ == "__main__":
    main()