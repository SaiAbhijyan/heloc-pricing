"""CSV/XLSX -> validated row dicts (pure I/O at edges)."""
from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import load_workbook

from app.bands import BandParseError, check_band_list_overlaps, parse_band_label

NA_VALUES = {"", "NA", "N/A", "na", "n/a"}
RATE_SHEET_COLS = (
    "product_id",
    "investor",
    "lock_period_days",
    "base_rate",
    "base_price",
)
MARGIN_COLS = ("loan_amount_min", "loan_amount_max", "margin_dollar", "margin_percent")
GRID_B_ATTRS = frozenset({"occupancy", "property_type", "fico", "loan_amount", "dti"})
NUMERIC_GRID_B = frozenset({"fico", "loan_amount", "dti"})


class ParseResult:
    def __init__(self, rows: list[dict[str, Any]], errors: list[str]):
        self.rows = rows
        self.errors = errors

    @property
    def ok(self) -> bool:
        return not self.errors


def _dec(s: str, row: int, col: str) -> tuple[Decimal | None, str | None]:
    s = str(s).strip()
    if not s:
        return None, f"row {row}, column {col}: missing value"
    try:
        return Decimal(s), None
    except InvalidOperation:
        return None, f"row {row}, column {col}: not numeric ({s!r})"


def _read_rows_bytes(data: bytes, filename: str) -> tuple[list[list[str]], list[str]]:
    errors: list[str] = []
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            return [], [f"XLSX read failed: {e}"]
        ws = wb.active
        rows = [["" if c is None else str(c) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
        return rows, errors
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["CSV must be UTF-8"]
    reader = csv.reader(io.StringIO(text))
    return [list(r) for r in reader], errors


def _header_map(header: list[str]) -> dict[str, int]:
    return {h.strip().lower(): i for i, h in enumerate(header)}


def parse_rate_sheet(data: bytes, filename: str) -> ParseResult:
    raw, errors = _read_rows_bytes(data, filename)
    if errors:
        return ParseResult([], errors)
    if not raw:
        return ParseResult([], ["empty file"])
    hdr = _header_map(raw[0])
    for col in RATE_SHEET_COLS:
        if col not in hdr:
            errors.append(f"missing column {col}")
    if errors:
        return ParseResult([], errors)
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(raw[1:], start=2):
        if not any(c.strip() for c in line):
            continue

        def cell(name: str) -> str:
            idx = hdr[name]
            return line[idx].strip() if idx < len(line) else ""

        br, e = _dec(cell("base_rate"), i, "base_rate")
        if e:
            errors.append(e)
        bp, e = _dec(cell("base_price"), i, "base_price")
        if e:
            errors.append(e)
        lp, e = _dec(cell("lock_period_days"), i, "lock_period_days")
        if e:
            errors.append(e)
        if errors:
            continue
        rows.append(
            {
                "product_id": cell("product_id"),
                "investor": cell("investor"),
                "lock_period_days": int(lp),
                "base_rate": br,
                "base_price": bp,
            }
        )
    return ParseResult(rows, errors)


def _parse_cltv_headers(headers: list[str]) -> tuple[list[str], list[tuple[Decimal, Decimal | None]], list[str]]:
    labels: list[str] = []
    parsed: list[tuple[Decimal, Decimal | None]] = []
    errors: list[str] = []
    for h in headers:
        h = h.strip()
        if not h:
            errors.append("empty CLTV header")
            continue
        try:
            parsed.append(parse_band_label(h))
            labels.append(h)
        except BandParseError:
            errors.append(f"invalid CLTV band header: {h!r}")
    errors.extend(check_band_list_overlaps(parsed, "CLTV headers"))
    return labels, parsed, errors


def _grid_a_result(cltv_labels, cltv_bands, rows, errors):
    if errors:
        return ParseResult([], errors)
    return ParseResult(
        {"cltv_labels": cltv_labels, "cltv_bands": cltv_bands, "rows": rows},
        [],
    )


def parse_grid_a(data: bytes, filename: str) -> ParseResult:
    raw, errors = _read_rows_bytes(data, filename)
    if errors or not raw:
        return ParseResult([], errors or ["empty file"])
    header = [c.strip().lower() for c in raw[0]]
    if len(header) < 3 or header[0] != "fico_min" or header[1] != "fico_max":
        return ParseResult([], ["grid A needs columns fico_min, fico_max, then CLTV bands"])
    cltv_labels, cltv_bands, herr = _parse_cltv_headers(raw[0][2:])
    errors.extend(herr)
    fico_bands: list[tuple[Decimal, Decimal | None]] = []
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(raw[1:], start=2):
        if not any(c.strip() for c in line):
            continue
        fm_s = line[0].strip() if line else ""
        fx_s = line[1].strip() if len(line) > 1 else ""
        fm, e1 = _dec(fm_s, i, "fico_min")
        if e1:
            errors.append(e1)
        hi: Decimal | None
        if not fx_s:
            hi = None
        elif fx_s.endswith("+"):
            hi = None
        else:
            hi, e2 = _dec(fx_s, i, "fico_max")
            if e2:
                errors.append(e2)
        if e1 or fm is None:
            continue
        fico_bands.append((fm, hi))
        cells: dict[str, str] = {}
        for j, label in enumerate(cltv_labels):
            col_i = j + 2
            val = line[col_i].strip() if col_i < len(line) else ""
            cells[label] = val
        rows.append({"fico_min": fm, "fico_max": hi, "cells": cells})
    errors.extend(check_band_list_overlaps(fico_bands, "grid A FICO bands"))
    return _grid_a_result(cltv_labels, cltv_bands, rows, errors)


def parse_grid_b(data: bytes, filename: str) -> ParseResult:
    raw, errors = _read_rows_bytes(data, filename)
    if errors or not raw:
        return ParseResult([], errors or ["empty file"])
    header = [c.strip().lower() for c in raw[0]]
    if len(header) < 3 or header[0] != "attribute" or header[1] != "band":
        return ParseResult([], ["grid B needs attribute, band, then CLTV bands"])
    cltv_labels, cltv_bands, herr = _parse_cltv_headers(raw[0][2:])
    errors.extend(herr)
    by_attr: dict[str, list[tuple[Decimal, Decimal | None, str]]] = {
        a: [] for a in GRID_B_ATTRS
    }
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(raw[1:], start=2):
        if not any(c.strip() for c in line):
            continue
        attr = (line[0].strip() if line else "").lower()
        band = line[1].strip() if len(line) > 1 else ""
        if attr not in GRID_B_ATTRS:
            errors.append(f"row {i}, column attribute: invalid {attr!r}")
            continue
        if not band:
            errors.append(f"row {i}, column band: missing")
            continue
        band_key = band
        lo: Decimal | None = None
        hi: Decimal | None = None
        if attr in NUMERIC_GRID_B:
            try:
                lo, hi = parse_band_label(band)
                by_attr[attr].append((lo, hi, band))
            except BandParseError:
                errors.append(f"row {i}, column band: invalid {band!r}")
                continue
        cells: dict[str, str] = {}
        for j, label in enumerate(cltv_labels):
            col_i = j + 2
            val = line[col_i].strip() if col_i < len(line) else ""
            cells[label] = val
        rows.append(
            {
                "attribute": attr,
                "band": band_key,
                "band_lower": lo,
                "band_upper": hi,
                "cells": cells,
            }
        )
    for attr, blist in by_attr.items():
        if blist:
            errors.extend(check_band_list_overlaps([(x[0], x[1]) for x in blist], f"grid B {attr} bands"))
    if errors:
        return ParseResult([], errors)
    return ParseResult(
        {"cltv_labels": cltv_labels, "cltv_bands": cltv_bands, "rows": rows},
        [],
    )


def parse_margins(data: bytes, filename: str) -> ParseResult:
    raw, errors = _read_rows_bytes(data, filename)
    if errors or not raw:
        return ParseResult([], errors or ["empty file"])
    hdr = _header_map(raw[0])
    for col in MARGIN_COLS:
        if col not in hdr:
            errors.append(f"missing column {col}")
    if errors:
        return ParseResult([], errors)
    bands: list[tuple[Decimal, Decimal | None]] = []
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(raw[1:], start=2):
        if not any(c.strip() for c in line):
            continue

        def cell(name: str) -> str:
            idx = hdr[name]
            return line[idx].strip() if idx < len(line) else ""

        lo, e1 = _dec(cell("loan_amount_min"), i, "loan_amount_min")
        max_s = cell("loan_amount_max")
        hi: Decimal | None
        if not max_s:
            hi = None
        else:
            hi, e2 = _dec(max_s, i, "loan_amount_max")
            if e2:
                errors.append(e2)
        md, e3 = _dec(cell("margin_dollar"), i, "margin_dollar")
        mp, e4 = _dec(cell("margin_percent"), i, "margin_percent")
        for e in (e1, e3, e4):
            if e:
                errors.append(e)
        if e1 or e3 or e4 or md is None or mp is None or lo is None:
            continue
        if hi is not None and lo > hi:
            errors.append(f"row {i}: loan_amount_min > loan_amount_max")
        bands.append((lo, hi))
        rows.append(
            {
                "loan_amount_min": lo,
                "loan_amount_max": hi,
                "margin_dollar": md,
                "margin_percent": mp,
            }
        )
    errors.extend(check_band_list_overlaps(bands, "margins loan amount bands"))
    return ParseResult(rows, errors)


def rows_from_json_rate_sheet(items: list[dict]) -> ParseResult:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for i, it in enumerate(items, start=1):
        try:
            rows.append(
                {
                    "product_id": str(it["product_id"]).strip(),
                    "investor": str(it["investor"]).strip(),
                    "lock_period_days": int(it["lock_period_days"]),
                    "base_rate": Decimal(str(it["base_rate"])),
                    "base_price": Decimal(str(it["base_price"])),
                }
            )
        except (KeyError, InvalidOperation, ValueError) as e:
            errors.append(f"row {i}: {e}")
    return ParseResult(rows, errors)


def rows_from_json_margins(items: list[dict]) -> ParseResult:
    errors: list[str] = []
    bands: list[tuple[Decimal, Decimal | None]] = []
    rows: list[dict[str, Any]] = []
    for i, it in enumerate(items, start=1):
        try:
            lo = Decimal(str(it["loan_amount_min"]))
            max_v = it.get("loan_amount_max")
            hi = None if max_v in (None, "") else Decimal(str(max_v))
            md = Decimal(str(it["margin_dollar"]))
            mp = Decimal(str(it["margin_percent"]))
            if hi is not None and lo > hi:
                errors.append(f"row {i}: min > max")
            bands.append((lo, hi))
            rows.append(
                {
                    "loan_amount_min": lo,
                    "loan_amount_max": hi,
                    "margin_dollar": md,
                    "margin_percent": mp,
                }
            )
        except (KeyError, InvalidOperation) as e:
            errors.append(f"row {i}: {e}")
    errors.extend(check_band_list_overlaps(bands, "margins"))
    return ParseResult(rows, errors)