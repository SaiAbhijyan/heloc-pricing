import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.serialize import pick_best_execution

EX = Path(__file__).resolve().parent.parent / "examples"
SCENARIOS = json.loads((EX / "SYNTHETIC_scenarios.json").read_text())["scenarios"]


@pytest.fixture
def client(seeded):
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_missing_config_409(fresh_db):
    c = TestClient(app)
    r = c.post(
        "/api/eligibility",
        json={
            "loan": {"heloc_amount": 100000, "first_lien_balance": 0},
            "borrower": {"fico": 700, "dti": 40},
            "property": {
                "value": 500000,
                "occupancy": "primary",
                "property_type": "single_family",
            },
        },
    )
    assert r.status_code == 409


def test_eligible_scenario(client):
    r = client.post(
        "/api/eligibility",
        json={
            "loan": {
                "heloc_amount": 150000,
                "first_lien_balance": 320000,
                "lock_period_days": 45,
            },
            "borrower": {"fico": 760, "dti": 32},
            "property": {
                "value": 650000,
                "occupancy": "primary",
                "property_type": "single_family",
            },
        },
    )
    assert r.status_code == 200
    res = r.json()["results"]
    assert res and any(x["eligible"] for x in res)


def test_ineligible_low_fico(client):
    r = client.post(
        "/api/eligibility",
        json={
            "loan": {"heloc_amount": 75000, "first_lien_balance": 180000},
            "borrower": {"fico": 615, "dti": 40},
            "property": {
                "value": 350000,
                "occupancy": "primary",
                "property_type": "single_family",
            },
        },
    )
    assert r.status_code == 200
    assert all(not x["eligible"] for x in r.json()["results"])


def test_upload_preview_and_save(client):
    data = (EX / "SYNTHETIC_margins.csv").read_bytes()
    r = client.post(
        "/api/admin/margins?preview=true",
        files={"file": ("m.csv", data, "text/csv")},
    )
    assert r.status_code == 200 and r.json()["ok"]


def test_validation_422(client):
    r = client.post(
        "/api/eligibility",
        json={
            "loan": {"heloc_amount": 100000, "first_lien_balance": 0},
            "borrower": {"fico": 200, "dti": 40},
            "property": {
                "value": 500000,
                "occupancy": "primary",
                "property_type": "single_family",
            },
        },
    )
    assert r.status_code == 422


def _scenario(name: str) -> dict:
    return next(s for s in SCENARIOS if s["name"] == name)


def _post_scenario(client, name: str):
    sc = _scenario(name)
    return client.post(
        "/api/eligibility",
        json={"loan": sc["loan"], "borrower": sc["borrower"], "property": sc["property"]},
    )


def test_synthetic_rate_ladder_row_count(client):
    rows = client.get("/api/admin/rate-sheet").json()["rows"]
    assert len(rows) == 384
    groups = {}
    for r in rows:
        k = (r["product_id"], r["investor"], r["lock_period_days"])
        groups.setdefault(k, []).append(r)
    for g in groups.values():
        assert len(g) == 6
        rates = sorted(x["base_rate"] for x in g)
        for i in range(1, len(rates)):
            assert abs(rates[i] - rates[i - 1] - 0.125) < 0.0001


def test_best_execution_rule(client):
    r = _post_scenario(client, "Clean eligible (primary SF)")
    body = r.json()
    assert r.status_code == 200
    eligible = [x for x in body["results"] if x["eligible"]]
    for pid in {x["product_id"] for x in eligible}:
        picks = [x for x in eligible if x["product_id"] == pid]
        expect = pick_best_execution(picks)
        assert expect is not None
        best_rows = [x for x in body["results"] if x.get("best")]
        match = next(x for x in best_rows if x["product_id"] == pid)
        assert match["investor"] == expect["investor"]
        assert match["final_rate"] == float(expect["final_rate"])
    summary = body["summary"]["best_by_product"]
    assert summary and all("rate" in b and "price" in b for b in summary)


def test_scenario_high_cltv_na(client):
    body = _post_scenario(client, "High CLTV (NA cells)").json()
    reasons = body["results"][0]["reasons"]
    assert any("Grid A" in x and "NA" in x for x in reasons)
    assert not any("above the highest CLTV band" in x for x in reasons)


def test_scenario_cltv_above_band(client):
    body = _post_scenario(client, "CLTV above max band").json()
    reasons = body["results"][0]["reasons"]
    assert any("above the highest CLTV band" in x for x in reasons)


def test_scenario_high_dti_na(client):
    body = _post_scenario(client, "High DTI (NA)").json()
    reasons = body["results"][0]["reasons"]
    assert any("Grid B" in x and "dti=" in x and "NA" in x for x in reasons)


def test_scenario_investment_condo(client):
    body = _post_scenario(client, "Investment condo").json()
    assert all(not x["eligible"] for x in body["results"])
    reasons = body["results"][0]["reasons"]
    assert any("occupancy=investment" in x and "NA" in x for x in reasons)


def test_scenario_investment_condo_low_cltv(client):
    body = _post_scenario(client, "Investment condo low CLTV").json()
    assert any(x["eligible"] for x in body["results"])


def test_loan_amount_reason_format(client):
    body = _post_scenario(client, "Out of margin range").json()
    text = " ".join(body["results"][0]["reasons"])
    assert "$15,000" in text


def test_response_summary_and_steps(client):
    r = client.post(
        "/api/eligibility",
        json={
            "loan": {
                "heloc_amount": 150000,
                "first_lien_balance": 320000,
                "lock_period_days": 45,
            },
            "borrower": {"fico": 760, "dti": 32},
            "property": {
                "value": 650000,
                "occupancy": "primary",
                "property_type": "single_family",
            },
        },
    )
    body = r.json()
    assert "summary" in body
    assert body["summary"]["eligible_count"] >= 1
    hit = next(x for x in body["results"] if x["eligible"])
    assert hit.get("steps") and hit["steps"][0]["label"] == "Base price"


def test_synthetic_investor_names(client):
    rows = client.get("/api/admin/rate-sheet").json()["rows"]
    text = " ".join(r["investor"] for r in rows)
    for bad in ("BayView", "PennyMac", "Citadel", "Angel Oak"):
        assert bad not in text
    assert "(synthetic)" in text


def test_favicon(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200


def test_put_margins_validation(client):
    r = client.put(
        "/api/admin/margins",
        json={
            "rows": [
                {
                    "loan_amount_min": "0",
                    "loan_amount_max": "100",
                    "margin_dollar": "1",
                    "margin_percent": "0.1",
                },
                {
                    "loan_amount_min": "50",
                    "loan_amount_max": "200",
                    "margin_dollar": "1",
                    "margin_percent": "0.1",
                },
            ]
        },
    )
    assert r.status_code == 400