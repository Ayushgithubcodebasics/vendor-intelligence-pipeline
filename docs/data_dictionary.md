# Data Dictionary

## Source table: purchases.csv (2,372,474 rows)

| Column | Type | Description | Null policy |
|---|---|---|---|
| InventoryId | TEXT | Composite store-city-brand key. Malformed in a subset of rows, especially Store 46. | May be malformed — do not use as a primary join key |
| Store | INT | Store identifier. | Not null |
| VendorNumber | INT | Unique numeric vendor identifier. | Not null |
| VendorName | TEXT | Vendor legal name. Whitespace is stripped at ingest; legal-name variants exist. | Not null after strip |
| Brand | INT | Numeric product brand identifier. | Not null |
| Description | TEXT | Product description. Whitespace stripped at ingest. | Not null after strip |
| PONumber | INT | Purchase order number. | Not null |
| PODate | DATE | Date the purchase order was placed. | Not null for lead-time calculation |
| ReceivingDate | DATE | Date goods were received. | Not null for lead-time calculation |
| InvoiceDate | DATE | Vendor invoice date. | Nullable in analysis layer |
| PayDate | DATE | Payment date. | Nullable in analysis layer |
| PurchasePrice | DECIMAL | Unit cost paid to vendor. 153 source rows equal 0 and are excluded from KPI cost-basis calculations. | Numeric, with zero-value rows handled explicitly |
| Quantity | DECIMAL | Units ordered/received. | Not null after numeric coercion |
| Dollars | DECIMAL | Total purchase dollars for the row. | Not null after numeric coercion |
| Classification | INT | Product classification indicator. | Nullable for KPI logic |

## Source table: sales.csv (12,825,363 rows)

| Column | Type | Description | Null policy |
|---|---|---|---|
| InventoryId | TEXT | Composite inventory key string. | May be malformed; not used as primary summary join key |
| Store | INT | Store identifier. | Nullable in output layer |
| Brand | INT | Numeric product brand identifier. | Not null |
| Description | TEXT | Product description. | Not null after strip |
| SalesQuantity | DECIMAL | Units sold. | Not null after numeric coercion |
| SalesDollars | DECIMAL | Total sales value. | Not null after numeric coercion |
| SalesPrice | DECIMAL | Unit selling price. | Not null after numeric coercion |
| SalesDate | DATE | Transaction date. | Not null |
| Volume | DECIMAL | Product volume where present. | Nullable |
| Classification | INT | Product classification indicator. | Nullable |
| ExciseTax | DECIMAL | Tax amount assessed on the sale. | Not null after numeric coercion |
| VendorNo | INT | Vendor identifier linking to `purchases.VendorNumber`. | Not null |
| VendorName | TEXT | Vendor name string. Whitespace stripped at ingest. | Not null after strip |

## Source table: purchase_prices.csv (12,261 rows)

| Column | Type | Description | Null policy |
|---|---|---|---|
| Brand | INT | Numeric brand identifier. In the delivered raw file, Brand is unique across all rows. | Not null |
| Description | TEXT | Product description string. | Not null after strip |
| Price | DECIMAL | Reference/list price. Renamed to `ActualPrice` in the output layer. | Numeric after coercion |
| Size | TEXT | Package size descriptor. | Nullable |
| Volume | DECIMAL | Package volume. Five non-numeric values are coerced to null. | Nullable |
| VendorNumber | INT | Vendor identifier appearing in the price table. | Nullable |
| PurchasePrice | DECIMAL | Purchase price recorded in the price master. | Nullable |

## Source table: vendor_invoice.csv (5,543 rows)

| Column | Type | Description | Null policy |
|---|---|---|---|
| VendorNumber | INT | Vendor identifier. | Not null |
| VendorName | TEXT | Vendor name string. | Nullable |
| PONumber | INT | Purchase order number. | Not null |
| Quantity | DECIMAL | Invoice quantity. | Numeric after coercion |
| Dollars | DECIMAL | Invoice total excluding freight. | Numeric after coercion |
| Freight | DECIMAL | Freight or shipping cost billed on the invoice. | Nulls coerced to 0 |
| Approval | TEXT | Approval status field; mostly blank in the source data. | Mostly null — not used for KPI logic |

## Generated output: vendor_summary.csv

| Column | Type | Description / Formula |
|---|---|---|
| VendorNumber | INT | Primary key component. |
| VendorName | TEXT | Canonical vendor name after modal-variant normalisation. |
| Brand | INT | Primary key component. |
| Description | TEXT | Product description from purchases, or fallback description from sales/price table. |
| PurchasePrice | DECIMAL | Unit purchase cost. Null for sales-only rows. |
| ActualPrice | DECIMAL | Reference/list price from `purchase_prices.csv`. |
| Volume | DECIMAL | Product volume from `purchase_prices.csv`; null where unknown. |
| TotalPurchaseQuantity | DECIMAL | Sum of `Quantity` from purchases where `PurchasePrice > 0`. |
| TotalPurchaseDollars | DECIMAL | Sum of `Dollars` from purchases where `PurchasePrice > 0`. |
| TotalSalesQuantity | DECIMAL | Sum of `SalesQuantity` from sales. |
| TotalSalesDollars | DECIMAL | Sum of `SalesDollars` from sales. |
| TotalSalesPrice | DECIMAL | Sum of `SalesPrice` from sales. |
| TotalExciseTax | DECIMAL | Sum of `ExciseTax` from sales. |
| FreightCost | DECIMAL | Row-level allocated freight cost. Vendor freight is allocated across purchase-backed vendor-brand rows in proportion to `TotalPurchaseDollars`, making the column additive in downstream BI tools. Sales-only rows receive 0. |
| GrossProfit | DECIMAL | `TotalSalesDollars - TotalPurchaseDollars`; null for sales-only rows without cost basis. |
| ProfitMargin | DECIMAL | `GrossProfit / TotalSalesDollars × 100`; null when no valid cost-basis margin should be computed. |
| SellThroughRate | DECIMAL | `TotalSalesQuantity / TotalPurchaseQuantity`; values above 1 indicate prior-period stock contribution. |
| StockTurnover | DECIMAL | Financial inventory turnover ratio = TotalPurchaseDollars / AllocatedAvgInventoryValue (vendor-brand allocated). Higher = faster inventory turnover. Values range widely (near-zero to 35,000x+) due to prior-period inventory in this dataset — cap or filter outliers before using in averages or Power BI visuals. Null where average inventory value is zero. Not comparable to SellThroughRate. |
| SalesToPurchaseRatio | DECIMAL | `TotalSalesDollars / TotalPurchaseDollars`; null when no purchase dollars exist. |
| UnsoldInventoryValue | DECIMAL | `max(0, TotalPurchaseQuantity - TotalSalesQuantity) × PurchasePrice`. |
| ZeroPriceRowsExcluded | DECIMAL | Count of raw purchase rows excluded because `PurchasePrice = 0` for the same vendor-brand key. Stored as a numeric/float field in CSV output for compatibility with grouped numeric exports. |
| CostBasisAvailable | INT | `1` when purchase cost basis exists; `0` for sales-only rows. |
| RowType | TEXT | `matched_purchase_and_sales`, `purchase_only_no_sales`, or `sales_only_no_2024_purchase`. |

## Generated output: vendor_lead_time.csv

| Column | Description |
|---|---|
| VendorNumber | Vendor identifier. |
| VendorName | Canonical vendor name. |
| TotalPOs | Count of distinct purchase orders. |
| AvgLeadTimeDays | Mean of `ReceivingDate - PODate` in calendar days. |
| MinLeadTimeDays | Minimum observed lead time. |
| MaxLeadTimeDays | Maximum observed lead time. |
| LeadTimeVariance | Population variance of lead time days. |
| NegativeLeadTimeCount | Count of rows where `ReceivingDate < PODate`; excluded from KPI calculations. |

## Generated output: vendor_otif.csv

| Column | Description |
|---|---|
| VendorNumber | Vendor identifier. |
| VendorName | Canonical vendor name. |
| TotalPOs | Count of distinct purchase orders. |
| OnTimePOs | Count of POs delivered within 14 days of `PODate`. |
| OTIFRatePct | `OnTimePOs / TotalPOs × 100`. |
| VendorReliabilityTier | `TIER_1_RELIABLE`, `TIER_2_ACCEPTABLE`, or `TIER_3_AT_RISK`. |


## Generated output: vendor_sales_monthly.csv

| Column | Description |
|---|---|
| VendorNumber | Vendor identifier |
| Brand | Brand identifier |
| YearMonth | Calendar month in YYYY-MM format derived from SalesDate |
| MonthlyQuantity | Sum of SalesQuantity for the vendor-brand-month |
| MonthlyDollars | Sum of SalesDollars for the vendor-brand-month |
| VendorName | Canonical vendor name joined from vendor map |
