"""SQLite persistence (stdlib sqlite3)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "heloc.db"
DB_PATH = Path(os.environ.get("HELOC_DB", str(_DEFAULT_DB)))


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                component TEXT PRIMARY KEY,
                uploaded_at TEXT,
                filename TEXT
            );
            CREATE TABLE IF NOT EXISTS rate_sheet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                investor TEXT,
                lock_period_days INTEGER,
                base_rate TEXT,
                base_price TEXT
            );
            CREATE TABLE IF NOT EXISTS margins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_amount_min TEXT,
                loan_amount_max TEXT,
                margin_dollar TEXT,
                margin_percent TEXT
            );
            CREATE TABLE IF NOT EXISTS grid_a_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cltv_labels TEXT
            );
            CREATE TABLE IF NOT EXISTS grid_a_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fico_min TEXT,
                fico_max TEXT,
                cells TEXT
            );
            CREATE TABLE IF NOT EXISTS grid_b_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cltv_labels TEXT
            );
            CREATE TABLE IF NOT EXISTS grid_b_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attribute TEXT,
                band TEXT,
                band_lower TEXT,
                band_upper TEXT,
                cells TEXT
            );
            """
        )


def _set_meta(component: str, filename: str) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO meta(component, uploaded_at, filename) VALUES (?, ?, ?)
            ON CONFLICT(component) DO UPDATE SET uploaded_at=excluded.uploaded_at, filename=excluded.filename
            """,
            (component, datetime.now(timezone.utc).isoformat(), filename),
        )


def save_rate_sheet(rows: list[dict], filename: str = "upload") -> None:
    with _conn() as c:
        c.execute("DELETE FROM rate_sheet")
        for r in rows:
            c.execute(
                "INSERT INTO rate_sheet(product_id,investor,lock_period_days,base_rate,base_price) VALUES (?,?,?,?,?)",
                (
                    r["product_id"],
                    r["investor"],
                    r["lock_period_days"],
                    str(r["base_rate"]),
                    str(r["base_price"]),
                ),
            )
    _set_meta("rate_sheet", filename)


def load_rate_sheet() -> list[dict]:
    with _conn() as c:
        cur = c.execute("SELECT * FROM rate_sheet ORDER BY id")
        out = []
        for row in cur:
            out.append(
                {
                    "product_id": row["product_id"],
                    "investor": row["investor"],
                    "lock_period_days": row["lock_period_days"],
                    "base_rate": Decimal(row["base_rate"]),
                    "base_price": Decimal(row["base_price"]),
                }
            )
        return out


def save_margins(rows: list[dict], filename: str = "upload") -> None:
    with _conn() as c:
        c.execute("DELETE FROM margins")
        for r in rows:
            c.execute(
                "INSERT INTO margins(loan_amount_min,loan_amount_max,margin_dollar,margin_percent) VALUES (?,?,?,?)",
                (
                    str(r["loan_amount_min"]),
                    "" if r["loan_amount_max"] is None else str(r["loan_amount_max"]),
                    str(r["margin_dollar"]),
                    str(r["margin_percent"]),
                ),
            )
    _set_meta("margins", filename)


def load_margins() -> list[dict]:
    with _conn() as c:
        cur = c.execute("SELECT * FROM margins ORDER BY id")
        out = []
        for row in cur:
            hi = row["loan_amount_max"]
            out.append(
                {
                    "loan_amount_min": Decimal(row["loan_amount_min"]),
                    "loan_amount_max": Decimal(hi) if hi else None,
                    "margin_dollar": Decimal(row["margin_dollar"]),
                    "margin_percent": Decimal(row["margin_percent"]),
                }
            )
        return out


def save_grid_a(data: dict, filename: str = "upload") -> None:
    labels = data["cltv_labels"]
    with _conn() as c:
        c.execute("DELETE FROM grid_a_rows")
        c.execute(
            "INSERT INTO grid_a_meta(id, cltv_labels) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET cltv_labels=excluded.cltv_labels",
            (json.dumps(labels),),
        )
        for r in data["rows"]:
            c.execute(
                "INSERT INTO grid_a_rows(fico_min,fico_max,cells) VALUES (?,?,?)",
                (
                    str(r["fico_min"]),
                    "" if r["fico_max"] is None else str(r["fico_max"]),
                    json.dumps(r["cells"]),
                ),
            )
    _set_meta("grid_a", filename)


def load_grid_a() -> dict | None:
    with _conn() as c:
        meta = c.execute("SELECT cltv_labels FROM grid_a_meta WHERE id=1").fetchone()
        if not meta:
            return None
        labels = json.loads(meta["cltv_labels"])
        from app.bands import parse_band_label

        bands = [parse_band_label(lb) for lb in labels]
        rows = []
        for row in c.execute("SELECT * FROM grid_a_rows ORDER BY id"):
            fx = row["fico_max"]
            rows.append(
                {
                    "fico_min": Decimal(row["fico_min"]),
                    "fico_max": Decimal(fx) if fx else None,
                    "cells": json.loads(row["cells"]),
                }
            )
        return {"cltv_labels": labels, "cltv_bands": bands, "rows": rows}


def save_grid_b(data: dict, filename: str = "upload") -> None:
    labels = data["cltv_labels"]
    with _conn() as c:
        c.execute("DELETE FROM grid_b_rows")
        c.execute(
            "INSERT INTO grid_b_meta(id, cltv_labels) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET cltv_labels=excluded.cltv_labels",
            (json.dumps(labels),),
        )
        for r in data["rows"]:
            c.execute(
                "INSERT INTO grid_b_rows(attribute,band,band_lower,band_upper,cells) VALUES (?,?,?,?,?)",
                (
                    r["attribute"],
                    r["band"],
                    "" if r["band_lower"] is None else str(r["band_lower"]),
                    "" if r["band_upper"] is None else str(r["band_upper"]),
                    json.dumps(r["cells"]),
                ),
            )
    _set_meta("grid_b", filename)


def load_grid_b() -> dict | None:
    with _conn() as c:
        meta = c.execute("SELECT cltv_labels FROM grid_b_meta WHERE id=1").fetchone()
        if not meta:
            return None
        labels = json.loads(meta["cltv_labels"])
        from app.bands import parse_band_label

        bands = [parse_band_label(lb) for lb in labels]
        rows = []
        for row in c.execute("SELECT * FROM grid_b_rows ORDER BY id"):
            bl, bu = row["band_lower"], row["band_upper"]
            rows.append(
                {
                    "attribute": row["attribute"],
                    "band": row["band"],
                    "band_lower": Decimal(bl) if bl else None,
                    "band_upper": Decimal(bu) if bu else None,
                    "cells": json.loads(row["cells"]),
                }
            )
        return {"cltv_labels": labels, "cltv_bands": bands, "rows": rows}


def missing_config() -> list[str]:
    missing = []
    if not load_rate_sheet():
        missing.append("rate sheet")
    if load_grid_a() is None:
        missing.append("grid A")
    if load_grid_b() is None:
        missing.append("grid B")
    if not load_margins():
        missing.append("margins")
    return missing


def get_meta(component: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT uploaded_at, filename FROM meta WHERE component=?", (component,)
        ).fetchone()
        if row:
            return {"uploaded_at": row["uploaded_at"], "filename": row["filename"]}
        return None


def admin_get(component: str) -> dict[str, Any]:
    meta = get_meta(component)
    if component == "rate-sheet":
        return {"meta": meta, "rows": load_rate_sheet()}
    if component == "margins":
        return {"meta": meta, "rows": load_margins()}
    if component == "grid-a":
        g = load_grid_a()
        return {"meta": meta, "data": g}
    if component == "grid-b":
        g = load_grid_b()
        return {"meta": meta, "data": g}
    raise KeyError(component)


def decimal_rows_json(rows: list[dict]) -> list[dict]:
    """Convert Decimals for JSON responses."""

    def conv(v):
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    return conv(rows)