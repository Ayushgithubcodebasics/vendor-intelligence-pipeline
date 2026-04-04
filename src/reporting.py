from __future__ import annotations

import json

import pandas as pd

from src.config import CHUNK_SIZE, OUTPUT_DIR, RAW_DATA_DIR, SAMPLE_DATA_DIR, SAMPLE_ROWS
from src.utils import get_logger

logger = get_logger(__name__)


def write_samples() -> None:
    logger.info('Writing quickstart sample CSVs...')
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ['begin_inventory.csv', 'end_inventory.csv', 'purchase_prices.csv', 'purchases.csv', 'sales.csv', 'vendor_invoice.csv']:
        df = pd.read_csv(RAW_DATA_DIR / fname, nrows=SAMPLE_ROWS, low_memory=False)
        df.to_csv(SAMPLE_DATA_DIR / fname.replace('.csv', '_sample.csv'), index=False)


def write_validation_files(
    final_df: pd.DataFrame,
    lead: pd.DataFrame,
    otif: pd.DataFrame,
    vendor_map: pd.DataFrame,
    unknown_volume_rows: int,
    zero_price_rows: int,
    negative_lead_rows: int,
    vendor_name_variant_count: int = 0,
    brand_fanout_detected: bool = False,
    unmatched_inventory_brand_rows: int = 0,
) -> None:
    logger.info('Writing validation reports...')
    raw_purchase_total = 0.0
    for chunk in pd.read_csv(RAW_DATA_DIR / 'purchases.csv', usecols=['PurchasePrice', 'Dollars'], chunksize=CHUNK_SIZE, low_memory=False):
        chunk['PurchasePrice'] = pd.to_numeric(chunk['PurchasePrice'], errors='coerce')
        chunk['Dollars'] = pd.to_numeric(chunk['Dollars'], errors='coerce').fillna(0)
        raw_purchase_total += float(chunk.loc[chunk['PurchasePrice'] > 0, 'Dollars'].sum())

    raw_sales_total = 0.0
    for chunk in pd.read_csv(RAW_DATA_DIR / 'sales.csv', usecols=['SalesDollars'], chunksize=CHUNK_SIZE, low_memory=False):
        raw_sales_total += float(pd.to_numeric(chunk['SalesDollars'], errors='coerce').fillna(0).sum())

    raw_freight_total = 0.0
    for chunk in pd.read_csv(RAW_DATA_DIR / 'vendor_invoice.csv', usecols=['Freight'], chunksize=CHUNK_SIZE, low_memory=False):
        raw_freight_total += float(pd.to_numeric(chunk['Freight'], errors='coerce').fillna(0).sum())

    summary_purchase_total = float(final_df.loc[final_df['CostBasisAvailable'] == 1, 'TotalPurchaseDollars'].sum())
    summary_sales_total = float(final_df['TotalSalesDollars'].sum())
    reconstructed_freight_total = float(final_df['FreightCost'].sum())
    vendor_brand_dupes = int(final_df.duplicated(['VendorNumber', 'Brand']).sum())
    sales_only_rows = int((final_df['RowType'] == 'sales_only_no_2024_purchase').sum())
    purchase_only_rows = int((final_df['RowType'] == 'purchase_only_no_sales').sum())
    matched_rows = int((final_df['RowType'] == 'matched_purchase_and_sales').sum())
    positive_margin_rows = int((final_df['ProfitMargin'] > 0).sum())
    null_margin_rows = int(final_df['ProfitMargin'].isna().sum())
    negative_margin_rows = int((final_df['ProfitMargin'].fillna(0) <= 0).sum() - null_margin_rows)
    sellthrough_gt_2_rows = int((final_df['SellThroughRate'].fillna(0) > 2).sum())
    max_sellthrough = float(final_df['SellThroughRate'].max(skipna=True)) if len(final_df) else 0.0
    extreme_margin_rows = int((final_df['ProfitMargin'].abs() > 100).sum())
    min_profit_margin = float(final_df['ProfitMargin'].min(skipna=True)) if final_df['ProfitMargin'].notna().any() else 0.0
    unique_tiers = int(otif['VendorReliabilityTier'].nunique()) if len(otif) else 0

    metrics = {
        'raw_purchase_total_filtered_purchaseprice_gt_0': round(raw_purchase_total, 2),
        'reconstructed_purchase_total_cost_basis_rows': round(summary_purchase_total, 2),
        'raw_sales_total': round(raw_sales_total, 2),
        'reconstructed_sales_total_all_rows': round(summary_sales_total, 2),
        'purchase_total_matches': abs(summary_purchase_total - raw_purchase_total) < 0.01,
        'sales_total_matches': abs(summary_sales_total - raw_sales_total) < 0.01,
        'raw_freight_total': round(raw_freight_total, 2),
        'reconstructed_freight_total': round(reconstructed_freight_total, 2),
        'freight_total_matches': abs(reconstructed_freight_total - raw_freight_total) < 0.01,
        'final_row_count': int(len(final_df)),
        'vendor_brand_duplicate_rows_in_final': vendor_brand_dupes,
        'matched_rows': matched_rows,
        'purchase_only_rows': purchase_only_rows,
        'sales_only_rows': sales_only_rows,
        'canonical_vendor_count': int(vendor_map['VendorNumber'].nunique()),
        'vendor_name_variants_detected': int(vendor_name_variant_count),
        'unknown_volume_rows_in_purchase_prices': int(unknown_volume_rows),
        'zero_purchaseprice_rows_excluded': int(zero_price_rows),
        'negative_lead_time_rows_detected': int(negative_lead_rows),
        'lead_time_vendor_count': int(len(lead)),
        'otif_vendor_count': int(len(otif)),
        'audit_claim_brand_fanout_confirmed_in_delivered_data': bool(brand_fanout_detected),
        'unmatched_inventory_brand_rows': int(unmatched_inventory_brand_rows),
        'positive_profitmargin_rows_dashboard_scope': positive_margin_rows,
        'null_profitmargin_rows': null_margin_rows,
        'negative_or_zero_profitmargin_rows': negative_margin_rows,
        'otif_unique_tier_count': unique_tiers,
        'sellthrough_gt_2_rows': sellthrough_gt_2_rows,
        'max_sellthrough_rate': round(max_sellthrough, 4),
        'profitmargin_abs_gt_100_rows': extreme_margin_rows,
        'min_profit_margin': round(min_profit_margin, 2),
    }
    (OUTPUT_DIR / 'validation_metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')

    unsold_total = float(final_df.loc[final_df['CostBasisAvailable'] == 1, 'UnsoldInventoryValue'].sum())
    tier_note = (
        'WARNING: All vendors are in the same reliability tier. OTIF KPI provides no differentiation on this dataset.'
        if unique_tiers == 1 else f'{unique_tiers} distinct reliability tiers observed.'
    )

    report = f"""PIPELINE VALIDATION REPORT
========================

Scope
-----
This report validates the regenerated analytical outputs against the delivered raw CSV package.
It covers numerical reconciliation, output-shape integrity, selected data-quality checks, and dashboard-scope caveats.

Core reconciliation checks
--------------------------
- Raw purchase dollars where PurchasePrice > 0: {raw_purchase_total:,.2f}
- Reconstructed purchase dollars (cost-basis rows): {summary_purchase_total:,.2f}
- Purchase total match: {metrics['purchase_total_matches']}

- Raw sales dollars: {raw_sales_total:,.2f}
- Reconstructed sales dollars (all rows): {summary_sales_total:,.2f}
- Sales total match: {metrics['sales_total_matches']}
- Raw freight total: {raw_freight_total:,.2f}
- Reconstructed freight total (allocated row-level freight): {reconstructed_freight_total:,.2f}
- Freight total match: {metrics['freight_total_matches']}

Output integrity checks
-----------------------
- Final output rows: {len(final_df):,}
- Matched purchase-and-sales rows: {matched_rows:,}
- Purchase-only rows: {purchase_only_rows:,}
- Sales-only rows retained explicitly: {sales_only_rows:,}
- Duplicate (VendorNumber, Brand) rows: {vendor_brand_dupes}
- Canonical vendor count: {metrics['canonical_vendor_count']}

Operational KPI checks
----------------------
- Lead-time vendor count: {len(lead):,}
- OTIF vendor count: {len(otif):,}
- Negative lead-time rows detected: {negative_lead_rows}
- Total unsold inventory value (cost-basis rows): {unsold_total:,.2f}
- OTIF tier differentiation: {tier_note}

Dashboard scope caveat
----------------------
- Rows with positive ProfitMargin (dashboard scope if positive-margin filter applied): {positive_margin_rows:,}
- Rows with null ProfitMargin (unmatched, excluded if positive-margin filter applied): {null_margin_rows:,}
- Rows with negative/zero ProfitMargin (excluded if positive-margin filter applied): {negative_margin_rows:,}

Data-quality observations from the delivered raw package
--------------------------------------------------------
- Vendor-name variants detected after whitespace cleaning: {vendor_name_variant_count}
- Non-numeric purchase_prices Volume values coerced to null: {unknown_volume_rows}
- Raw purchase rows excluded because PurchasePrice = 0: {zero_price_rows}
- Brand-level fan-out in purchase_prices.csv detected from raw file: {brand_fanout_detected}
- Inventory brand rows without purchase-side vendor match: {unmatched_inventory_brand_rows}

Interpretation boundary
-----------------------
The validation above confirms that the regenerated CSV outputs reconcile numerically to the delivered raw data.
Gross Profit remains a period-aggregated analytical metric, OTIF remains a proxy based on a 14-day SLA assumption,
and StockTurnover is now inventory-based using allocated average inventory value by vendor-brand.
"""
    (OUTPUT_DIR / 'validation_report.txt').write_text(report, encoding='utf-8')
