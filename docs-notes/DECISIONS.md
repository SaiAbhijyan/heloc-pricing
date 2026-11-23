# Decisions and assumptions

## Stack

- Python 3.12, FastAPI, stdlib sqlite3, openpyxl, vanilla HTML/JS/CSS. No front-end build.
- SQLite file `heloc.db` in project root (gitignored).

## Assumptions (record for Sai)

| ID | Assumption | Question for Sai |
|----|------------|------------------|
| A1 | CLTV = (first lien + HELOC line) / property value × 100; value must be > 0. Rounded to 2 dp with ROUND_HALF_UP before any band lookup; the rounded CLTV is returned in the API. | Confirm lien inclusion and whether HALF_UP matches investor systems. |
| R1 | Ineligible rate rows collect every failure reason (grid A, each grid B attribute, margins) in one list. | Should reasons be de-duplicated or ranked? |
| A2 | Loan amount for grid B bands and margins = HELOC line amount. | Should total liens or draw amount be used instead? |
| A3 | Bands inclusive; blank max = no upper limit; overlaps rejected on upload; gaps → ineligible with axis-specific reason. | Any products that allow gap pricing? |
| A4 | Blank / NA / N/A grid cells → ineligible with grid, row, column in reason. | Should NA mean “not offered” vs hard decline? |
| A5 | Prices in points (100 = par); LLPAs added to base (negative = borrower cost). | Confirm sign convention vs investor sheet. |
| A6 | margin_points = % + ($ / loan) × 100; final_price = base + LLPAs − margin_points; final_rate = base rate. | Is margin a rate margin over Prime instead? |
| A7 | Grids A/B apply to all products/investors. | Per-investor grids later? |
| A8 | Grid B: each attribute matches one row (case-insensitive categorical); each adds CLTV column cell. | manufactured = NA everywhere until allowed. |
| A9 | Optional lock period filters results; optional product_id filters rate sheet rows. | Default lock when omitted? |
| A10 | Upload replaces whole table; keep uploaded_at and file name. | Version history needed? |
| A11 | DTI percent; FICO 300–850; invalid request → 422. | Additional fields (state, lien position)? |
| A12 | Results sorted by product, lock, then final_price descending among eligible. | Sort by rate instead for some channels? |
| A13 | Best execution per product: lowest final rate among eligible rows with final price ≥ 100 (par); if none at/above par, highest final price. UI default shows one par-pick row per product×investor×lock (same rule); toggle shows full ladder. | Confirm par floor vs best-rate tie-break when multiple investors hit par. |