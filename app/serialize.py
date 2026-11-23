from __future__ import annotations

from decimal import Decimal
from typing import Any


def _d(v: Any, dp: int | None = None) -> Any:
    if isinstance(v, Decimal):
        if dp is None:
            return float(v)
        q = Decimal(10) ** -dp
        return float(v.quantize(q))
    if isinstance(v, dict):
        return {k: _d(x, dp) for k, x in v.items()}
    if isinstance(v, list):
        return [_d(x, dp) for x in v]
    return v


def format_result_payload(payload: dict) -> dict:
    out = _d(payload)
    if "results" in out:
        for r in out["results"]:
            if r.get("final_price") is not None:
                r["final_price"] = _d(r["final_price"], 3)
            r["base_rate"] = _d(r["base_rate"], 3)
            r["base_price"] = _d(r["base_price"], 3)
            r["final_rate"] = _d(r["final_rate"], 3)
            r["llpa_total"] = _d(r["llpa_total"], 3)
            for ll in r.get("llpas", []):
                ll["value"] = _d(ll["value"], 3)
            if r.get("margin"):
                m = r["margin"]
                m["dollar"] = _d(m["dollar"], 2)
                m["percent"] = _d(m["percent"], 3)
                m["points"] = _d(m["points"], 3)
    if "inputs" in out and "cltv" in out["inputs"]:
        out["inputs"]["cltv"] = _d(out["inputs"]["cltv"], 2)
    return out