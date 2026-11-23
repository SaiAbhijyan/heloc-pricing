from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoanIn(BaseModel):
    heloc_amount: float = Field(gt=0)
    first_lien_balance: float = Field(ge=0)
    lock_period_days: int | None = None
    product_id: str | None = None


class BorrowerIn(BaseModel):
    fico: int = Field(ge=300, le=850)
    dti: float = Field(ge=0, le=100)


class PropertyIn(BaseModel):
    value: float = Field(gt=0)
    occupancy: Literal["primary", "second_home", "investment"]
    property_type: str


class EligibilityRequest(BaseModel):
    loan: LoanIn
    borrower: BorrowerIn
    property: PropertyIn

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "loan": {
                        "heloc_amount": 150000,
                        "first_lien_balance": 320000,
                        "lock_period_days": 45,
                    },
                    "borrower": {"fico": 740, "dti": 38},
                    "property": {
                        "value": 650000,
                        "occupancy": "primary",
                        "property_type": "single_family",
                    },
                }
            ]
        }
    }


def loan_dict(loan: LoanIn) -> dict:
    d = {
        "heloc_amount": loan.heloc_amount,
        "first_lien_balance": loan.first_lien_balance,
    }
    if loan.lock_period_days is not None:
        d["lock_period_days"] = loan.lock_period_days
    if loan.product_id:
        d["product_id"] = loan.product_id
    return d


class TraceStep(BaseModel):
    step: int
    name: str
    inputs: dict = Field(default_factory=dict)
    matched: dict | list | str | None = None
    output: dict = Field(default_factory=dict)
    status: Literal["ok", "fail", "skip"]
    duration_ms: float


class PriceStep(BaseModel):
    label: str
    value: float | None = None


class LLPABreakdown(BaseModel):
    source: Literal["grid_a", "grid_b"]
    row: str
    column: str
    value: float


class MarginBreakdown(BaseModel):
    row: str
    dollar: float
    percent: float
    points: float


class RateRowResult(BaseModel):
    product_id: str
    investor: str
    lock_period_days: int
    eligible: bool
    base_rate: float
    base_price: float
    llpas: list[LLPABreakdown] = Field(default_factory=list)
    llpa_total: float
    margin: MarginBreakdown | None = None
    final_rate: float
    final_price: float | None = None
    reasons: list[str] = Field(default_factory=list)
    best: bool = False
    steps: list[PriceStep] = Field(default_factory=list)


class BestByProduct(BaseModel):
    product_id: str
    investor: str
    lock_period_days: int
    rate: float
    final_rate: float
    price: float
    final_price: float


class EligibilitySummary(BaseModel):
    eligible_count: int
    ineligible_count: int
    total_count: int
    best_by_product: list[BestByProduct] = Field(default_factory=list)


class EligibilityResponse(BaseModel):
    inputs: dict
    results: list[RateRowResult]
    summary: EligibilitySummary
    trace: list[TraceStep] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "inputs": {
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
                        "cltv": 72.31,
                    },
                    "summary": {
                        "eligible_count": 32,
                        "ineligible_count": 0,
                        "total_count": 32,
                        "best_by_product": [
                            {
                                "product_id": "SYNTHETIC_30Y_HELOC",
                                "investor": "Investor Alpha (synthetic)",
                                "lock_period_days": 45,
                                "rate": 7.875,
                                "final_rate": 7.875,
                                "price": 101.25,
                                "final_price": 101.25,
                            }
                        ],
                    },
                    "results": [],
                    "trace": [
                        {
                            "step": 1,
                            "name": "validate_input",
                            "inputs": {},
                            "matched": None,
                            "output": {},
                            "status": "ok",
                            "duration_ms": 0.01,
                        },
                        {
                            "step": 8,
                            "name": "compute_final_price",
                            "inputs": {"rate_rows": 32},
                            "matched": None,
                            "output": {
                                "formula": "final_price = base_price + llpa_total - margin_points",
                                "borrower_level_grids_reused": True,
                            },
                            "status": "ok",
                            "duration_ms": 1.2,
                        },
                    ],
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ProductsResponse(BaseModel):
    product_ids: list[str]


class AdminMeta(BaseModel):
    uploaded_at: str | None = None
    filename: str | None = None


class AdminGetResponse(BaseModel):
    rows: list | dict | None = None
    meta: AdminMeta | None = None


class UploadOkResponse(BaseModel):
    ok: Literal[True]
    meta: AdminMeta | None = None


class UploadPreviewResponse(BaseModel):
    ok: Literal[True]
    rows: list | dict
    summary: dict
    total_rows: int
    errors: list[str] = Field(default_factory=list)


class UploadErrorResponse(BaseModel):
    ok: Literal[False]
    errors: list[str]


class PutOkResponse(BaseModel):
    ok: Literal[True]


class ScenariosResponse(BaseModel):
    scenarios: list[dict]


OPENAPI_DESCRIPTION = """HELOC eligibility and pricing engine. **All rate sheets, grids, and margins are SYNTHETIC** examples for development only.

### Engine pipeline (execution trace)
Each `POST /api/eligibility` response may include an ordered `trace` of eight steps:
1. **validate_input** — parse and normalize loan, borrower, property
2. **compute_cltv** — raw and rounded CLTV; CLTV column per grid
3. **load_rate_sheet_rows** — product/lock filters, row counts, investors
4. **match_grid_a_llpa** — FICO row × CLTV column (borrower-level, reused for all rate rows)
5. **match_grid_b_llpas** — five attributes (occupancy, property_type, fico, loan_amount, dti)
6. **apply_margin** — margin row, dollar/percent → margin points
7. **eligibility_checks** — borrower-level pass/fail with reasons
8. **compute_final_price** — `base_price + LLPAs − margin_points` per rate row

Omit trace with `?trace=false`."""