# Vendor Profitability and Supply Chain Performance Analysis

**Author:** Ayush Butoliya — BSc Information Systems, Riga Nordic University  
**Stack:** Python 3.11+ · pandas · SQLite · pytest · Power BI  
**Data scale:** 15.65 million transaction and inventory rows across 6 source tables (2024 fiscal year)

---

## Live Dashboard

[![Power BI Dashboard](https://img.shields.io/badge/Power%20BI-Live%20Dashboard-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)](https://app.powerbi.com/view?r=eyJrIjoiZDYwNTZmZTItYjFlMi00ZWIxLTlkYWUtMDRiZmE3MjZjOWEzIiwidCI6ImM2ZTU0OWIzLTVmNDUtNDAzMi1hYWU5LWQ0MjQ0ZGM1YjJjNCJ9)

> Interactive vendor profitability, supply chain, and inventory analysis —
> built on 15.6 million transaction rows across 129 vendors (2024 fiscal year).

---

## Why I built this

I found this dataset on Kaggle — it covers a beverage alcohol distributor's full 2024
purchase, sales, and inventory records. I picked it because it had real problems in it:
the same vendor appearing under different legal entity names across three source files,
purchase orders with negative lead times (receiving date before the PO date), and product
descriptions that don't match cleanly across tables.

The ExciseTax field in the sales data made the industry obvious from the start. Alcohol
excise is collected from the distributor and passed through, so it doesn't affect gross
profit but it does inflate the headline sales price for non-analyst readers. I kept that
in mind when interpreting the margin numbers.

The hardest part technically was the weighted average purchase price across 2.3 million
rows read in 300,000-row chunks. A simple chunk-level mean gives the wrong answer when
chunk sizes are uneven — I had to track running totals of dollars and quantity separately
and compute the true weighted average only at the end. That took a while to get right.

---

## Business problem

A beverage alcohol distributor managing inventory across roughly 80 store locations and
129 vendors needed to answer three operational questions:

1. Which vendors generate the highest gross profit relative to procurement cost?
2. Which vendors are operationally reliable versus risky on delivery timeliness?
3. Which products tie up working capital through low sell-through and high unsold inventory value?

Without a consolidated analytical layer, answering these questions required manual work
across six disconnected CSV files and produced no reliable vendor-level KPI view.

---

## Solution architecture

```text
purchases.csv       ──┐
sales.csv            ─┤
purchase_prices.csv  ─┼──► src/rebuild_pipeline.py ──► outputs/
vendor_invoice.csv   ─┤         │
begin_inventory.csv  ─┤    Canonical vendor map
end_inventory.csv    ─┘    Lead time + OTIF KPIs
                           Dollar reconciliation
                           Validation test suite
```

---

## Key findings

**Finding 1 — Vendor concentration risk:** the top 10 vendors account for **65.3%** of total
procurement spend, representing **$210.3M of $321.9M**. This level of concentration is material
operational risk because a disruption among a small supplier tier would affect most purchasing volume.

**Finding 2 — Portfolio-level gross margin remains healthy, but only after excluding rows without
2024 purchase cost basis:** cost-basis rows produce an overall reconstructed gross margin of **28.7%**.
That is directionally strong, but 758 sales-only vendor-brand rows have no 2024 purchase record and must
be handled separately rather than forced into margin calculations.

**Finding 3 — Working capital is concentrated in a small supplier tier:** the top 10 vendors hold
**64.9%** of unsold inventory value, representing **$10.12M of $15.60M**. This makes targeted vendor
and SKU rationalisation more impactful than broad, portfolio-wide actions.

**Finding 4 — Delivery timing is extremely clean in the delivered dataset:** average vendor lead time is
**9.7 days**, median lead time is **9.8 days**, and the derived OTIF view classifies all 126 measurable
vendors as **TIER_1_RELIABLE**. That makes the KPI reproducible, but it also suggests the source data is
synthetic or unusually clean compared with real procurement operations.

---

## Vendor performance KPIs computed

| KPI | Formula | Source columns |
|---|---|---|
| Gross Profit | `TotalSalesDollars - TotalPurchaseDollars` | purchases, sales |
| Profit Margin % | `GrossProfit / TotalSalesDollars × 100` | Computed |
| Sell-Through Rate | `TotalSalesQuantity / TotalPurchaseQuantity` | purchases, sales |
| Sales-to-Purchase Ratio | `TotalSalesDollars / TotalPurchaseDollars` | purchases, sales |
| Unsold Inventory Value | `max(0, PurchaseQty - SalesQty) × PurchasePrice` | purchases, sales |
| Avg Lead Time (days) | `AVG(ReceivingDate - PODate)` per vendor | purchases |
| Lead Time Variance | `VAR(LeadTimeDays)` per vendor | purchases |
| OTIF Rate % | `% of POs received within 14-day SLA proxy` | purchases |
| Vendor Reliability Tier | `TIER_1 (≥95%), TIER_2 (≥80%), TIER_3 (<80%)` | Computed from OTIF |
| Freight Cost | Vendor freight allocated to vendor-brand rows by purchase-dollar share | vendor_invoice, purchases |

**Note:** `SellThroughRate` is the quantity-based operational ratio. `StockTurnover` is computed from
allocated average inventory value by vendor-brand, so the two metrics are not interchangeable.
`FreightCost` is safe to sum in downstream BI tools because vendor freight is allocated across
vendor-brand rows by purchase-dollar share during the rebuild.

---

## How to reproduce

```bash
# 1. Clone the repository
git clone https://github.com/Ayushgithubcodebasics/vendor-intelligence-pipeline.git
cd vendor-intelligence-pipeline

# 2. Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Place raw CSV files in data/raw/
#    (or use data/sample/ for lightweight inspection)

# 4. Run the full rebuild pipeline
python -m src.rebuild_pipeline

# 5. Validate outputs
pytest tests/ -v

# 6. Optionally load raw tables and vendor summary into SQLite
python -m src.ingest_sqlite
```

**Expected runtime on full data (~15.65M rows):** roughly 8–15 minutes on a standard laptop.  
**Expected runtime on sample data (5,000 rows per file):** under 30 seconds for lightweight inspection.

---

## Known limitations and data caveats

1. **Gross Profit is period-aggregated, not period-matched.** Sales in 2024 may be fulfilled from
   inventory purchased in earlier periods, so the gross-profit figure is directionally useful but not
   equivalent to a formal COGS-based accounting margin.

2. **OTIF uses a 14-day SLA proxy.** The raw dataset does not include an explicit contracted delivery-date
   field, so OTIF is calculated against a practical proxy rather than a contractual SLA.

3. **Malformed `InventoryId` values exist and should not be used as a master join key.** The issue is most
   visible in Store 46, with 1,284 malformed rows in `end_inventory.csv` and 1,690 malformed rows in
   `purchases.csv`, plus a small number elsewhere.

4. **VendorName variants are normalised deliberately.** For example, VendorNumber 1587 appears as both
   `VINEYARD BRANDS INC` and `VINEYARD BRANDS LLC`; the analytical layer maps such variants to a canonical
   vendor name for stable vendor-level reporting.

5. **758 sales-only vendor-brand rows have no 2024 purchase cost basis.** Those rows are retained in the
   final output with `CostBasisAvailable = 0` and `RowType = sales_only_no_2024_purchase` instead of being
   silently dropped.

6. **Sell-through outliers are real and materially distort averages.** The output contains **1,168 rows**
   with `SellThroughRate > 2.0`, and the maximum observed value is **274.5x**. Any Power BI average or
   scatter chart using sell-through should cap or filter these rows before interpretation.

7. **Profit-margin outliers are extreme because cost basis is period-aggregated.** The output contains
   **698 rows** with `|ProfitMargin| > 100%`, and the minimum observed margin is **-23,730.64%**. These
   are not formula bugs; they are a consequence of comparing 2024 sales against 2024 purchases when
   prior-period inventory is still being sold.

---

## Project structure

```text
vendor-intelligence-pipeline/
├── README.md
├── PROJECT_NOTES.txt
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/                      # full raw CSV package (kept local, not for public GitHub)
│   └── sample/                   # 5,000-row quickstart samples
├── docs/
│   ├── data_dictionary.md
│   ├── dashboard_setup.md
│   └── GDPR_statement.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── utils.py
│   ├── ingestion.py
│   ├── transform.py
│   ├── reporting.py
│   ├── build_outputs.py
│   ├── rebuild_pipeline.py
│   └── ingest_sqlite.py
├── tests/
│   └── test_output_integrity.py
└── outputs/
    ├── vendor_summary.csv
    ├── vendor_lead_time.csv
    ├── vendor_otif.csv
    ├── vendor_sales_monthly.csv
    ├── validation_metrics.json
    └── validation_report.txt
```

---

## What I'd improve next

- **CI/CD:** add a GitHub Actions workflow to run `pytest` on the sample data on every push
- **Cross-platform run script:** the current `run_rebuild_steps.ps1` is Windows-only; a `Makefile`
  with `make run` and `make test` targets would cover Mac and Linux users
- **Weighted average unit test:** a small fixed fixture (five rows, known correct answer) to
  specifically validate the chunk-aggregation logic in `aggregate_purchases()`
- **OTIF threshold sensitivity:** explore whether a tighter SLA window (7 days instead of 14)
  produces any tier separation, or whether the clean lead times in this dataset make differentiation
  impossible regardless of the threshold chosen
