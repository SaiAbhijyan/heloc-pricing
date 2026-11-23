from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

PAR = Decimal("100")


def _q(v: Decimal, dp: int) -> Decimal:
    return v.quantize(Decimal(10) ** -dp, rounding=ROUND_HALF_UP)


def _num(v: Any, dp: int | None = None) -> Any:
    if isinstance(v, Decimal):
        if dp is None:
            return float(v)
        return float(_q(v, dp))
    if isinstance(v, dict):
        return {k: _num(x, dp) for k, x in v.items()}
    if isinstance(v, list):
        return [_num(x, dp) for x in v]
    return v


def _steps_for_result(r: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"label": "Base price", "value": _num(r["base_price"], 3)},
    ]
    for ll in r.get("llpas") or []:
        src = "Grid A" if ll["source"] == "grid_a" else "Grid B"
        steps.append(
            {
                "label": f"{src} {ll['row']} x CLTV {ll['column']}",
                "value": _num(ll["value"], 3),
            }
        )
    steps.append({"label": "LLPA total", "value": _num(r["llpa_total"], 3)})
    if r.get("margin"):
        m = r["margin"]
        steps.append(
            {
                "label": (
                    f"Margin ${float(_q(m['dollar'], 2)):.2f} + {float(_q(m['percent'], 3))}% "
                    f"= {float(_q(m['points'], 3))} pts (row {m['row']})"
                ),
                "value": _num(-m["points"], 3),
            }
        )
    if r.get("final_price") is not None:
        steps.append({"label": "Final price", "value": _num(r["final_price"], 3)})
    steps.append({"label": "Final rate", "value": _num(r["final_rate"], 3)})
    return steps


def pick_best_execution(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        r for r in rows if r.get("eligible") and r.get("final_price") is not None
    ]
    if not eligible:
        return None
    at_par = [r for r in eligible if r["final_price"] >= PAR]
    if at_par:
        return min(at_par, key=lambda r: (r["final_rate"], -r["final_price"]))
    return max(eligible, key=lambda r: r["final_price"])


def _best_row_ids(results: list[dict[str, Any]]) -> set[int]:
    by_product: dict[str, list[dict[str, Any]]] = {}
    for i, r in enumerate(results):
        if r.get("eligible"):
            by_product.setdefault(r["product_id"], []).append({**r, "_i": i})
    winners: set[int] = set()
    for pid, rows in by_product.items():
        pick = pick_best_execution(rows)
        if pick is not None:
            winners.add(pick["_i"])
    return winners


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in results if r.get("eligible")]
    ineligible = [r for r in results if not r.get("eligible")]
    best: dict[str, dict] = {}
    by_product: dict[str, list[dict[str, Any]]] = {}
    for r in eligible:
        by_product.setdefault(r["product_id"], []).append(r)
    for pid, rows in by_product.items():
        pick = pick_best_execution(rows)
        if pick is None:
            continue
        fp = pick["final_price"]
        best[pid] = {
            "product_id": pid,
            "investor": pick["investor"],
            "lock_period_days": pick["lock_period_days"],
            "rate": _num(pick["final_rate"], 3),
            "final_rate": _num(pick["final_rate"], 3),
            "price": _num(fp, 3),
            "final_price": _num(fp, 3),
        }
    return {
        "eligible_count": len(eligible),
        "ineligible_count": len(ineligible),
        "total_count": len(results),
        "best_by_product": sorted(best.values(), key=lambda x: x["product_id"]),
    }


def format_result_payload(payload: dict) -> dict:
    results_in = payload.get("results", [])
    summary = _summary(results_in)
    best_ids = _best_row_ids(results_in)
    out_results = []
    for i, r in enumerate(results_in):
        row = _num(dict(r))
        row["best"] = i in best_ids
        row["base_rate"] = _num(r["base_rate"], 3)
        row["base_price"] = _num(r["base_price"], 3)
        row["final_rate"] = _num(r["final_rate"], 3)
        row["llpa_total"] = _num(r["llpa_total"], 3)
        if r.get("final_price") is not None:
            row["final_price"] = _num(r["final_price"], 3)
        for ll in row.get("llpas", []):
            ll["value"] = _num(Decimal(str(ll["value"])), 3)
        if r.get("margin"):
            m = row["margin"]
            m["dollar"] = _num(r["margin"]["dollar"], 2)
            m["percent"] = _num(r["margin"]["percent"], 3)
            m["points"] = _num(r["margin"]["points"], 3)
        row["steps"] = _steps_for_result(r) if r.get("eligible") else []
        out_results.append(row)
    out = dict(payload)
    out["results"] = out_results
    out["summary"] = summary
    if "inputs" in out and "cltv" in out["inputs"]:
        out["inputs"] = dict(out["inputs"])
        out["inputs"]["cltv"] = _num(out["inputs"]["cltv"], 2)
    return _num(out)