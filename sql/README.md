# SQL Analysis Layer

These queries run directly against the SQLite database populated by `src/ingest_sqlite.py`.
They answer the same business questions as `docs/findings.md` and serve as an independent
validation of the Python pipeline outputs.

## Setup

```bash
# 1. Run the full pipeline first to generate vendor_summary.csv
python -m src.rebuild_pipeline

# 2. Load all raw tables + vendor_summary into SQLite
python -m src.ingest_sqlite

# 3. Run any query file
sqlite3 inventory.db < sql/01_vendor_concentration.sql
```

Or open `inventory.db` in DB Browser for SQLite and run queries interactively.

## Query files

| File | Business question | Key techniques |
|---|---|---|
| `01_vendor_concentration.sql` | Which vendors concentrate procurement risk? ABC classification. | CTE, `SUM OVER`, `RANK`, cumulative % |
| `02_margin_and_profitability.sql` | Which SKUs are loss-making at scale? Margin quartile distribution. | CTE, `NTILE`, `RANK`, `CASE WHEN` |
| `03_inventory_and_working_capital.sql` | Where is working capital tied up in unsold stock? | CTE, `SUM OVER`, `RANK`, ratio analysis |
| `04_lead_time_and_delivery.sql` | Which vendors have unpredictable delivery windows? MoM purchase trend. | CTE, `LAG`, `JULIANDAY`, variance, OTIF |

## What these queries prove vs. the pipeline

The Python pipeline aggregates across 15.65M rows in memory-safe chunks. These SQL queries
run the same logic against the raw tables in SQLite and produce the same figures — confirming
that the aggregation, vendor name canonicalization, and KPI formulas are correct.

Key cross-checks:
- `01_vendor_concentration.sql` Q1 → should match Finding 1 (top-10 = 65.3% of spend)
- `02_margin_and_profitability.sql` Q2 → should surface the same 5 negative-margin SKUs as Finding 2
- `03_inventory_and_working_capital.sql` Q1 → should match Finding 3 ($15.6M total unsold)
- `04_lead_time_and_delivery.sql` Q1 → should match Finding 5 (avg 9.7 days, all vendors TIER_1)
