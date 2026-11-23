from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

EX = Path(__file__).resolve().parent.parent / "examples"


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