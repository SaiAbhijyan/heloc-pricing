# HELOC pricing engine

Local HELOC eligibility and price engine with admin uploads and a small web UI.

**All `examples/SYNTHETIC_*` and `EXAMPLE_*` files are fictional. They are not real market prices.**

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --port 8811
```

Open http://127.0.0.1:8811/ for eligibility. Admin tables: `/ratesheet`, `/grids`, `/margins`. API explorer: `/explorer`. Swagger: `/docs`.

## Test

```bash
.venv/bin/pytest -q
```

## File formats

See `AGENTS.md`. Short form:

- Rate sheet: `product_id`, `investor`, `lock_period_days`, `base_rate`, `base_price`
- Grid A: `fico_min`, `fico_max`, then CLTV headers like `0-60`, `90.01+`
- Grid B: `attribute`, `band`, then same CLTV headers
- Margins: `loan_amount_min`, `loan_amount_max`, `margin_dollar`, `margin_percent`

Regenerate synthetic data:

```bash
.venv/bin/python scripts/make_synthetic.py
```

## Example request

```bash
curl -s -X POST http://127.0.0.1:8811/api/eligibility \
  -H 'Content-Type: application/json' \
  -d '{"loan":{"heloc_amount":150000,"first_lien_balance":320000,"lock_period_days":45},"borrower":{"fico":760,"dti":32},"property":{"value":650000,"occupancy":"primary","property_type":"single_family"}}'
```

Response includes `inputs.cltv`, `results[]` with `eligible`, LLPAs, margin, `final_price`, and `reasons`.