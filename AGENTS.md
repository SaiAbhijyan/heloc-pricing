# HELOC pricing — agent guide

## Clean-room

Do not open, read, or copy `/workspace/loan-pricing`. Write this project from requirements only.

## No push

This repo is local only. Do not add a git remote or push.

## Architecture

| Path | Role |
|------|------|
| `app/pricing.py` | Pure pricing: CLTV, band match, LLPAs, margin, eligibility |
| `app/parsers.py` | CSV/XLSX → validated rows |
| `app/bands.py` | Band labels and overlap checks |
| `app/store.py` | SQLite load/save |
| `app/main.py` | FastAPI routes and static pages |
| `app/models.py` | Request validation |
| `static/` | HTML, CSS, JS (no build) |
| `examples/` | SYNTHETIC data only (`scripts/make_synthetic.py`) |
| `tests/` | pytest |

## Commands

```bash
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --port 8811
.venv/bin/pytest -q
.venv/bin/python scripts/make_synthetic.py
```

## Pricing math (see `app/pricing.py`)

- `CLTV = (first_lien_balance + heloc_amount) / property_value × 100`, rounded to 2 dp (ROUND_HALF_UP) before band lookup
- `final_price = base_price + sum(LLPA points) − margin_points`
- `margin_points = margin_percent + (margin_dollar / heloc_amount) × 100`
- `final_rate = base_rate` (unchanged in this build)

LLPA blank/NA → ineligible. No matching band → ineligible with reason. 100.000 points = par.

## Upload rules

Upload validates all rows before save. Overlapping bands in one axis/attribute reject the file. Row errors include row number and column.

## API

- `POST /api/eligibility` — price all rate-sheet rows (optional lock/product filter); optional `?trace=false` (default includes eight-step engine trace)
- `GET/POST /api/admin/{rate-sheet|grid-a|grid-b|margins}` — read or file upload (`preview=true` for dry run)
- `PUT /api/admin/{...}` — browser table save with same validation
- `GET /api/health`

Missing config → HTTP 409 with component names.