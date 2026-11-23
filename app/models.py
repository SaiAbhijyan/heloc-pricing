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