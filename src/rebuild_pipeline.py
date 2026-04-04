from __future__ import annotations

import argparse
import subprocess
import sys

import pandas as pd

from src.build_outputs import (
    aggregate_freight,
    aggregate_purchases,
    aggregate_sales,
    aggregate_sales_by_month,
    build_final_summary,
    build_lead_time_and_otif,
    build_vendor_name_map,
    compute_avg_inventory_by_vendor_brand,
    load_purchase_prices,
    write_samples,
    write_validation_files,
)
from src.config import OUTPUT_DIR
from src.utils import get_logger

logger = get_logger(__name__)
INTERMEDIATE = OUTPUT_DIR / '_intermediate'


def step_vendor_map():
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    vendor_map, variant_count = build_vendor_name_map()
    vendor_map.to_csv(INTERMEDIATE / 'vendor_map.csv', index=False)
    (INTERMEDIATE / 'vendor_name_variant_count.txt').write_text(str(variant_count), encoding='utf-8')


def step_purchase_prices():
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    pp, unknown_volume_rows, brand_fanout_detected = load_purchase_prices()
    pp.to_csv(INTERMEDIATE / 'purchase_prices_dedup.csv', index=False)
    (INTERMEDIATE / 'unknown_volume_rows.txt').write_text(str(unknown_volume_rows), encoding='utf-8')
    (INTERMEDIATE / 'brand_fanout_detected.txt').write_text(str(brand_fanout_detected), encoding='utf-8')


def step_purchases():
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    purchases, zero_df, po_df, zero_price_rows = aggregate_purchases()
    purchases.to_csv(INTERMEDIATE / 'purchases_agg.csv', index=False)
    zero_df.to_csv(INTERMEDIATE / 'zero_price_agg.csv', index=False)
    po_df.to_csv(INTERMEDIATE / 'purchase_orders_agg.csv', index=False)
    (INTERMEDIATE / 'zero_price_rows.txt').write_text(str(zero_price_rows), encoding='utf-8')


def step_sales():
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    aggregate_sales().to_csv(INTERMEDIATE / 'sales_agg.csv', index=False)


def step_freight():
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    aggregate_freight().to_csv(INTERMEDIATE / 'freight_agg.csv', index=False)


def step_finalize():
    vendor_map = pd.read_csv(INTERMEDIATE / 'vendor_map.csv')
    pp = pd.read_csv(INTERMEDIATE / 'purchase_prices_dedup.csv')
    purchases = pd.read_csv(INTERMEDIATE / 'purchases_agg.csv')
    zero_path = INTERMEDIATE / 'zero_price_agg.csv'
    zero_df = pd.read_csv(zero_path) if zero_path.exists() and zero_path.stat().st_size > 0 else pd.DataFrame(columns=['VendorNumber', 'Brand', 'ZeroPriceRowsExcluded'])
    po_df = pd.read_csv(INTERMEDIATE / 'purchase_orders_agg.csv', parse_dates=['PODate', 'ReceivingDate'])
    sales = pd.read_csv(INTERMEDIATE / 'sales_agg.csv')
    freight = pd.read_csv(INTERMEDIATE / 'freight_agg.csv')
    unknown_volume_rows = int((INTERMEDIATE / 'unknown_volume_rows.txt').read_text(encoding='utf-8').strip())
    zero_price_rows = int((INTERMEDIATE / 'zero_price_rows.txt').read_text(encoding='utf-8').strip())
    vendor_name_variant_count = int((INTERMEDIATE / 'vendor_name_variant_count.txt').read_text(encoding='utf-8').strip())
    brand_fanout_detected = ((INTERMEDIATE / 'brand_fanout_detected.txt').read_text(encoding='utf-8').strip() == 'True')

    vendor_inv_df, unmatched_inventory_brand_rows = compute_avg_inventory_by_vendor_brand(purchases)
    vendor_inv_df.to_csv(INTERMEDIATE / 'vendor_inventory_alloc.csv', index=False)

    final_df = build_final_summary(purchases, sales, pp, freight, vendor_map, zero_df, vendor_inv_df)
    lead, otif, negative_lead_rows = build_lead_time_and_otif(po_df, vendor_map)
    monthly_sales = aggregate_sales_by_month()
    monthly_sales_with_vendor = monthly_sales.merge(vendor_map, on='VendorNumber', how='left').rename(columns={'CanonicalVendorName': 'VendorName'})

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(OUTPUT_DIR / 'vendor_sales_summary_corrected.csv', index=False)
    lead.to_csv(OUTPUT_DIR / 'vendor_lead_time.csv', index=False)
    otif.to_csv(OUTPUT_DIR / 'vendor_otif.csv', index=False)
    monthly_sales_with_vendor.to_csv(OUTPUT_DIR / 'vendor_sales_monthly.csv', index=False)
    write_samples()
    write_validation_files(
        final_df,
        lead,
        otif,
        vendor_map,
        unknown_volume_rows,
        zero_price_rows,
        negative_lead_rows,
        vendor_name_variant_count,
        brand_fanout_detected,
        unmatched_inventory_brand_rows,
    )


def run_step(step: str):
    {
        'vendor_map': step_vendor_map,
        'purchase_prices': step_purchase_prices,
        'purchases': step_purchases,
        'sales': step_sales,
        'freight': step_freight,
        'finalize': step_finalize,
    }[step]()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--step', choices=['vendor_map', 'purchase_prices', 'purchases', 'sales', 'freight', 'finalize'])
    args = parser.parse_args()

    if args.step:
        run_step(args.step)
        return

    for step in ['vendor_map', 'purchase_prices', 'purchases', 'sales', 'freight', 'finalize']:
        logger.info('Running step: %s', step)
        subprocess.run([sys.executable, '-m', 'src.rebuild_pipeline', '--step', step], check=True)
    logger.info('Rebuild pipeline complete.')


if __name__ == '__main__':
    main()
