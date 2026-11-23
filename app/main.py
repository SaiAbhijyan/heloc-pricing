from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import parsers, store
from app.models import EligibilityRequest, loan_dict
from app.pricing import run_pricing
from app.serialize import format_result_payload

STATIC = Path(__file__).resolve().parent.parent / "static"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    store.init_db()
    if store.missing_config():
        from app.seed import load_all

        load_all()
    yield


app = FastAPI(title="HELOC Pricing Engine", version="1.0.0", lifespan=_lifespan)


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#1e4d8c"/>'
        '<text x="16" y="22" text-anchor="middle" fill="#fff" font-size="14" font-family="sans-serif">H</text>'
        "</svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/products")
def list_products():
    rows = store.load_rate_sheet()
    if not rows:
        raise HTTPException(409, "rate sheet not loaded")
    return {"product_ids": sorted({r["product_id"] for r in rows})}


@app.get("/")
async def index():
    from fastapi.responses import FileResponse

    return FileResponse(STATIC / "index.html")


@app.get("/admin")
async def admin_page():
    from fastapi.responses import FileResponse

    return FileResponse(STATIC / "admin.html")


def _page(name: str):
    from fastapi.responses import FileResponse

    return FileResponse(STATIC / name)


@app.get("/ratesheet")
async def ratesheet_page():
    return _page("ratesheet.html")


@app.get("/grids")
async def grids_page():
    return _page("grids.html")


@app.get("/margins")
async def margins_page():
    return _page("margins.html")


@app.get("/explorer")
async def explorer_page():
    from fastapi.responses import FileResponse

    return FileResponse(STATIC / "explorer.html")


@app.get("/api/scenarios")
def list_scenarios():
    path = EXAMPLES / "SYNTHETIC_scenarios.json"
    if not path.exists():
        return {"scenarios": []}
    return json.loads(path.read_text())


def _missing_response():
    miss = store.missing_config()
    if miss:
        raise HTTPException(
            status_code=409,
            detail=f"Missing configuration: {', '.join(miss)}. Upload via admin.",
        )


@app.post("/api/eligibility")
def eligibility(body: EligibilityRequest):
    _missing_response()
    payload = run_pricing(
        loan_dict(body.loan),
        body.borrower.model_dump(),
        body.property.model_dump(),
        store.load_rate_sheet(),
        store.load_grid_a(),
        store.load_grid_b(),
        store.load_margins(),
    )
    return format_result_payload(payload)


PARSERS = {
    "rate-sheet": parsers.parse_rate_sheet,
    "grid-a": parsers.parse_grid_a,
    "grid-b": parsers.parse_grid_b,
    "margins": parsers.parse_margins,
}

SAVERS = {
    "rate-sheet": store.save_rate_sheet,
    "grid-a": store.save_grid_a,
    "grid-b": store.save_grid_b,
    "margins": store.save_margins,
}


@app.get("/api/admin/{component}")
def admin_get(component: str):
    key = component
    if key not in PARSERS:
        raise HTTPException(404, "unknown component")
    return store.admin_get(key)


@app.post("/api/admin/{component}")
async def admin_upload(
    component: str,
    file: UploadFile = File(...),
    preview: bool = Query(False),
):
    key = component
    if key not in PARSERS:
        raise HTTPException(404, "unknown component")
    data = await file.read()
    result = PARSERS[key](data, file.filename or "upload.csv")
    if not result.ok:
        return JSONResponse(
            status_code=400, content={"ok": False, "errors": result.errors}
        )
    if preview:
        return {"ok": True, "rows": _preview_rows(key, result.rows), "errors": []}
    SAVERS[key](result.rows, file.filename or "upload")
    return {"ok": True, "meta": store.get_meta(key)}


def _preview_rows(key: str, rows):
    if key in ("grid-a", "grid-b"):
        return rows
    return [
        {k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()}
        if isinstance(r, dict)
        else r
        for r in (rows if isinstance(rows, list) else [rows])
    ]


class RateSheetBody(BaseModel):
    rows: list[dict]


class MarginsBody(BaseModel):
    rows: list[dict]


class GridABody(BaseModel):
    cltv_labels: list[str]
    rows: list[dict]


class GridBBody(BaseModel):
    cltv_labels: list[str]
    rows: list[dict]


@app.put("/api/admin/rate-sheet")
def put_rate_sheet(body: RateSheetBody):
    result = parsers.rows_from_json_rate_sheet(body.rows)
    if not result.ok:
        raise HTTPException(400, detail=result.errors)
    store.save_rate_sheet(result.rows, "browser-edit")
    return {"ok": True}


@app.put("/api/admin/margins")
def put_margins(body: MarginsBody):
    result = parsers.rows_from_json_margins(body.rows)
    if not result.ok:
        raise HTTPException(400, detail=result.errors)
    store.save_margins(result.rows, "browser-edit")
    return {"ok": True}


def _grid_a_from_body(body: GridABody) -> parsers.ParseResult:
    errors: list[str] = []
    from app.bands import parse_band_label, check_band_list_overlaps

    try:
        bands = [parse_band_label(lb) for lb in body.cltv_labels]
    except Exception as e:
        return parsers.ParseResult([], [str(e)])
    errors.extend(check_band_list_overlaps(bands, "CLTV headers"))
    fico_bands = []
    rows = []
    for i, r in enumerate(body.rows, start=1):
        try:
            fm = Decimal(str(r["fico_min"]))
            fx = r.get("fico_max")
            hi = None if fx in (None, "") else Decimal(str(fx))
            fico_bands.append((fm, hi))
            cells = r.get("cells") or {}
            rows.append({"fico_min": fm, "fico_max": hi, "cells": cells})
        except Exception as e:
            errors.append(f"row {i}: {e}")
    errors.extend(check_band_list_overlaps(fico_bands, "grid A FICO"))
    if errors:
        return parsers.ParseResult([], errors)
    return parsers.ParseResult(
        {"cltv_labels": body.cltv_labels, "cltv_bands": bands, "rows": rows}, []
    )


@app.put("/api/admin/grid-a")
def put_grid_a(body: GridABody):
    result = _grid_a_from_body(body)
    if not result.ok:
        raise HTTPException(400, detail=result.errors)
    store.save_grid_a(result.rows, "browser-edit")
    return {"ok": True}


def _grid_b_from_body(body: GridBBody) -> parsers.ParseResult:
    from app.bands import parse_band_label, check_band_list_overlaps

    errors: list[str] = []
    try:
        bands = [parse_band_label(lb) for lb in body.cltv_labels]
    except Exception as e:
        return parsers.ParseResult([], [str(e)])
    errors.extend(check_band_list_overlaps(bands, "CLTV headers"))
    by_attr: dict[str, list] = {a: [] for a in parsers.GRID_B_ATTRS}
    rows = []
    for i, r in enumerate(body.rows, start=1):
        attr = str(r.get("attribute", "")).lower()
        if attr not in parsers.GRID_B_ATTRS:
            errors.append(f"row {i}: bad attribute")
            continue
        band = str(r.get("band", ""))
        lo = hi = None
        if attr in parsers.NUMERIC_GRID_B:
            try:
                lo, hi = parse_band_label(band)
                by_attr[attr].append((lo, hi))
            except Exception:
                errors.append(f"row {i}: bad band")
                continue
        rows.append(
            {
                "attribute": attr,
                "band": band,
                "band_lower": lo,
                "band_upper": hi,
                "cells": r.get("cells") or {},
            }
        )
    for attr, blist in by_attr.items():
        if blist:
            errors.extend(check_band_list_overlaps(blist, f"grid B {attr}"))
    if errors:
        return parsers.ParseResult([], errors)
    return parsers.ParseResult(
        {"cltv_labels": body.cltv_labels, "cltv_bands": bands, "rows": rows}, []
    )


@app.put("/api/admin/grid-b")
def put_grid_b(body: GridBBody):
    result = _grid_b_from_body(body)
    if not result.ok:
        raise HTTPException(400, detail=result.errors)
    store.save_grid_b(result.rows, "browser-edit")
    return {"ok": True}


@app.get("/api/admin/{component}/download")
def download_csv(component: str):
    key = component
    if key == "rate-sheet":
        rows = store.load_rate_sheet()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(parsers.RATE_SHEET_COLS)
        for r in rows:
            w.writerow(
                [
                    r["product_id"],
                    r["investor"],
                    r["lock_period_days"],
                    r["base_rate"],
                    r["base_price"],
                ]
            )
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    if key == "margins":
        rows = store.load_margins()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(parsers.MARGIN_COLS)
        for r in rows:
            w.writerow(
                [
                    r["loan_amount_min"],
                    r["loan_amount_max"] if r["loan_amount_max"] is not None else "",
                    r["margin_dollar"],
                    r["margin_percent"],
                ]
            )
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    if key == "grid-a":
        g = store.load_grid_a()
        if not g:
            raise HTTPException(404, "no data")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["fico_min", "fico_max", *g["cltv_labels"]])
        for r in g["rows"]:
            w.writerow(
                [
                    r["fico_min"],
                    r["fico_max"] if r["fico_max"] is not None else "",
                    *[r["cells"].get(lb, "") for lb in g["cltv_labels"]],
                ]
            )
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    if key == "grid-b":
        g = store.load_grid_b()
        if not g:
            raise HTTPException(404, "no data")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["attribute", "band", *g["cltv_labels"]])
        for r in g["rows"]:
            w.writerow(
                [
                    r["attribute"],
                    r["band"],
                    *[r["cells"].get(lb, "") for lb in g["cltv_labels"]],
                ]
            )
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    raise HTTPException(404, "unknown component")