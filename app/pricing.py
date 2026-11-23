"""Pure pricing and eligibility (Decimal, no I/O)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.bands import in_band
from app.parsers import NA_VALUES

GRID_B_ATTR_ORDER = ("occupancy", "property_type", "fico", "loan_amount", "dti")
_NA_UPPER = {x.upper() for x in NA_VALUES if x}


def calc_cltv(first_lien: Decimal, heloc: Decimal, value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("property value must be > 0")
    return (first_lien + heloc) / value * Decimal(100)


def round_cltv_for_lookup(cltv: Decimal) -> Decimal:
    return cltv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fico_band_labels(rows: list[dict[str, Any]]) -> str:
    parts = []
    for row in rows:
        lo, hi = row["fico_min"], row["fico_max"]
        parts.append(f"{lo}-{hi}" if hi is not None else f"{lo}+")
    if len(parts) <= 4:
        return ", ".join(parts)
    return f"{parts[0]}, {parts[1]} ... {parts[-1]}"


def _cltv_outside_reason(
    cltv: Decimal, labels: list[str], bands: list[tuple[Decimal, Decimal | None]], grid: str
) -> str:
    pct = f"{cltv.quantize(Decimal('0.01'))}%"
    if bands:
        last_lo, last_hi = bands[-1]
        last_label = labels[-1]
        if last_hi is not None and cltv > last_hi:
            return f"CLTV {pct} is above the highest CLTV band ({last_label})"
        if cltv < bands[0][0]:
            return f"CLTV {pct} is below the lowest CLTV band ({labels[0]})"
    return f"CLTV {pct} is outside {grid} CLTV bands"


def find_cltv_column(
    cltv: Decimal, labels: list[str], bands: list[tuple[Decimal, Decimal | None]]
) -> tuple[int | None, str | None]:
    for i, (lo, hi) in enumerate(bands):
        if in_band(cltv, lo, hi):
            return i, labels[i]
    return None, None


def find_fico_row_grid_a(
    fico: int, rows: list[dict[str, Any]]
) -> tuple[dict | None, str | None]:
    fico_d = Decimal(fico)
    for row in rows:
        lo, hi = row["fico_min"], row["fico_max"]
        if in_band(fico_d, lo, hi):
            return row, None
    return None, (
        f"Grid A: FICO {fico} is outside all FICO bands ({_fico_band_labels(rows)})"
    )


def cell_adjustment(
    raw: str, grid: str, row_label: str, col_label: str
) -> tuple[Decimal | None, str | None]:
    if raw.strip().upper() in _NA_UPPER or not raw.strip():
        return None, f"{grid}: {row_label} x CLTV {col_label} is NA (not allowed)"
    try:
        return Decimal(raw.strip()), None
    except Exception:
        return None, f"{grid}: {row_label} x CLTV {col_label}: invalid cell {raw!r}"


def grid_a_llpa(
    fico: int,
    cltv: Decimal,
    grid: dict[str, Any],
) -> tuple[list[dict], Decimal, list[str]]:
    reasons: list[str] = []
    row, err = find_fico_row_grid_a(fico, grid["rows"])
    if err:
        return [], Decimal(0), [err]
    idx, col_label = find_cltv_column(cltv, grid["cltv_labels"], grid["cltv_bands"])
    if idx is None:
        return [], Decimal(0), [
            _cltv_outside_reason(cltv, grid["cltv_labels"], grid["cltv_bands"], "grid A")
        ]
    assert row is not None
    fico_hi = row["fico_max"] if row["fico_max"] is not None else "+"
    row_label = f"FICO {row['fico_min']}-{fico_hi}"
    raw = row["cells"].get(col_label, "")
    val, c_err = cell_adjustment(raw, "Grid A", row_label, col_label)
    if c_err:
        return [], Decimal(0), [c_err]
    assert val is not None
    llpa = {
        "source": "grid_a",
        "row": row_label,
        "column": col_label,
        "value": val,
    }
    return [llpa], val, reasons


def match_grid_b_row(
    attr: str,
    borrower: dict[str, Any],
    prop: dict[str, Any],
    heloc: Decimal,
    row: dict[str, Any],
) -> bool:
    if attr in ("occupancy", "property_type"):
        return row["band"].strip().lower() == str(prop[attr]).strip().lower()
    if attr == "fico":
        return in_band(Decimal(borrower["fico"]), row["band_lower"], row["band_upper"])
    if attr == "loan_amount":
        return in_band(heloc, row["band_lower"], row["band_upper"])
    if attr == "dti":
        return in_band(Decimal(str(borrower["dti"])), row["band_lower"], row["band_upper"])
    return False


def _grid_b_no_row(attr: str, prop: dict, borrower: dict, heloc: Decimal) -> str:
    if attr in ("occupancy", "property_type"):
        return f"Grid B: {attr} '{prop[attr]}' has no row"
    if attr == "fico":
        return f"Grid B: FICO {borrower['fico']} is outside all FICO bands"
    if attr == "loan_amount":
        return f"Grid B: loan amount {heloc} is outside all loan_amount bands"
    return f"Grid B: DTI {borrower['dti']} is outside all DTI bands"


def grid_b_llpa(
    borrower: dict[str, Any],
    prop: dict[str, Any],
    heloc: Decimal,
    cltv: Decimal,
    grid: dict[str, Any],
) -> tuple[list[dict], Decimal, list[str]]:
    reasons: list[str] = []
    idx, col_label = find_cltv_column(cltv, grid["cltv_labels"], grid["cltv_bands"])
    cltv_ok = idx is not None
    if not cltv_ok:
        reasons.append(
            _cltv_outside_reason(cltv, grid["cltv_labels"], grid["cltv_bands"], "grid B")
        )
    rows_by_attr: dict[str, list[dict]] = {}
    for row in grid["rows"]:
        rows_by_attr.setdefault(row["attribute"], []).append(row)
    llpas: list[dict] = []
    total = Decimal(0)
    attr_failed = False
    for attr in GRID_B_ATTR_ORDER:
        candidates = rows_by_attr.get(attr, [])
        matched = [r for r in candidates if match_grid_b_row(attr, borrower, prop, heloc, r)]
        if len(matched) == 0:
            reasons.append(_grid_b_no_row(attr, prop, borrower, heloc))
            attr_failed = True
            continue
        if len(matched) > 1:
            key = borrower["fico"] if attr == "fico" else prop.get(attr, heloc)
            reasons.append(f"Grid B: {len(matched)} rows match {attr} {key} (overlap)")
            attr_failed = True
            continue
        if not cltv_ok:
            attr_failed = True
            continue
        m = matched[0]
        raw = m["cells"].get(col_label, "")
        band_label = f"{attr}={m['band']}"
        val, c_err = cell_adjustment(raw, "Grid B", band_label, col_label)
        if c_err:
            reasons.append(c_err)
            attr_failed = True
            continue
        assert val is not None
        llpas.append(
            {
                "source": "grid_b",
                "row": band_label,
                "column": col_label,
                "value": val,
            }
        )
        total += val
    if reasons or attr_failed:
        return [], Decimal(0), reasons
    return llpas, total, reasons


def _margin_span(margin_rows: list[dict[str, Any]]) -> tuple[Decimal, Decimal | None]:
    lo = min(r["loan_amount_min"] for r in margin_rows)
    hi = max(
        (r["loan_amount_max"] for r in margin_rows if r["loan_amount_max"] is not None),
        default=None,
    )
    return lo, hi


def find_margin_row(
    heloc: Decimal, margin_rows: list[dict[str, Any]]
) -> tuple[dict | None, str | None]:
    for row in margin_rows:
        lo, hi = row["loan_amount_min"], row["loan_amount_max"]
        if in_band(heloc, lo, hi):
            return row, None
    if not margin_rows:
        return None, f"Loan amount ${heloc:,.0f} is outside the margins table"
    lo, hi = _margin_span(margin_rows)
    hi_s = f"{hi:,.0f}" if hi is not None else "+"
    return None, (
        f"Loan amount ${heloc:,.0f} is outside the margins table ({lo:,.0f}-{hi_s})"
    )


def margin_points(row: dict[str, Any], heloc: Decimal) -> Decimal:
    dollar = row["margin_dollar"]
    pct = row["margin_percent"]
    if heloc <= 0:
        return pct
    return pct + dollar / heloc * Decimal(100)


def price_one_rate_row(
    rate_row: dict[str, Any],
    borrower: dict[str, Any],
    prop: dict[str, Any],
    heloc: Decimal,
    cltv: Decimal,
    grid_a: dict,
    grid_b: dict,
    margins: list[dict],
) -> dict[str, Any]:
    reasons: list[str] = []
    llpas: list[dict] = []
    llpa_total = Decimal(0)

    ga, ga_val, ga_reasons = grid_a_llpa(borrower["fico"], cltv, grid_a)
    reasons.extend(ga_reasons)
    if not ga_reasons:
        llpas.extend(ga)
        llpa_total += ga_val

    gb, gb_val, gb_reasons = grid_b_llpa(borrower, prop, heloc, cltv, grid_b)
    reasons.extend(gb_reasons)
    if not gb_reasons:
        llpas.extend(gb)
        llpa_total += gb_val

    m_row, m_err = find_margin_row(heloc, margins)
    if m_err:
        reasons.append(m_err)

    if reasons:
        return _ineligible(rate_row, reasons)

    assert m_row is not None
    pts = margin_points(m_row, heloc)
    base_price = rate_row["base_price"]
    final_price = base_price + llpa_total - pts
    return {
        "product_id": rate_row["product_id"],
        "investor": rate_row["investor"],
        "lock_period_days": rate_row["lock_period_days"],
        "eligible": True,
        "base_rate": rate_row["base_rate"],
        "base_price": base_price,
        "llpas": llpas,
        "llpa_total": llpa_total,
        "margin": {
            "row": f"{m_row['loan_amount_min']}-{m_row['loan_amount_max'] or '+'}",
            "dollar": m_row["margin_dollar"],
            "percent": m_row["margin_percent"],
            "points": pts,
        },
        "final_rate": rate_row["base_rate"],
        "final_price": final_price,
        "reasons": [],
    }


def _ineligible(rate_row: dict, reasons: list[str]) -> dict:
    return {
        "product_id": rate_row["product_id"],
        "investor": rate_row["investor"],
        "lock_period_days": rate_row["lock_period_days"],
        "eligible": False,
        "base_rate": rate_row["base_rate"],
        "base_price": rate_row["base_price"],
        "llpas": [],
        "llpa_total": Decimal(0),
        "margin": None,
        "final_rate": rate_row["base_rate"],
        "final_price": None,
        "reasons": reasons,
    }


def run_pricing(
    loan: dict[str, Any],
    borrower: dict[str, Any],
    prop: dict[str, Any],
    rate_sheet: list[dict],
    grid_a: dict,
    grid_b: dict,
    margins: list[dict],
) -> dict[str, Any]:
    heloc = Decimal(str(loan["heloc_amount"]))
    first = Decimal(str(loan["first_lien_balance"]))
    value = Decimal(str(prop["value"]))
    cltv = round_cltv_for_lookup(calc_cltv(first, heloc, value))
    lock_filter = loan.get("lock_period_days")
    product_filter = loan.get("product_id")
    results: list[dict] = []
    for row in rate_sheet:
        if product_filter and row["product_id"] != product_filter:
            continue
        if lock_filter is not None and row["lock_period_days"] != lock_filter:
            continue
        results.append(
            price_one_rate_row(row, borrower, prop, heloc, cltv, grid_a, grid_b, margins)
        )
    results.sort(
        key=lambda r: (
            r["product_id"],
            r["lock_period_days"],
            -(r["final_price"] if r["final_price"] is not None else Decimal("-Infinity")),
        )
    )
    return {
        "inputs": {
            "loan": loan,
            "borrower": borrower,
            "property": prop,
            "cltv": cltv,
        },
        "results": results,
    }