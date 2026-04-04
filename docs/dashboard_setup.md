# Power BI Dashboard Setup

These are the steps I used to configure the Power BI report from the pipeline
outputs. If you are loading the CSV files into Power BI yourself, here is what
to watch for:

1. Type these fields explicitly in Power Query: `SalesToPurchaseRatio`, `UnsoldInventoryValue`, `ZeroPriceRowsExcluded`, `CostBasisAvailable`, `RowType`.
2. If you apply a positive `ProfitMargin` filter in visuals, add a visible dashboard note that only the positive-margin matched subset is shown.
3. Add an OTIF caveat note: all measurable vendors in this dataset fall into one reliability tier, so OTIF has no differentiation value on this source year.
4. Load `outputs/vendor_sales_monthly.csv` and create a monthly trend visual.

5. Use `outputs/vendor_summary.csv` as the primary data source for the main dashboard page.
6. Use `outputs/vendor_sales_monthly.csv` as the secondary data source for the monthly trend visual.
7. `FreightCost` is row-level allocated freight and is safe to SUM in Power BI — vendor-level totals in the invoice data are already distributed across vendor-brand rows in proportion to purchase dollars during the rebuild.
