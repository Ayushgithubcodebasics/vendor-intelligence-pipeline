# build_outputs.py — public API shim for backward compatibility.
# All logic lives in ingestion.py, transform.py, and reporting.py.

from src.ingestion import (
    build_vendor_name_map,
    load_purchase_prices,
    aggregate_purchases,
    aggregate_sales,
    aggregate_freight,
    compute_avg_inventory_by_vendor_brand,
    aggregate_sales_by_month,
)
from src.transform import (
    build_final_summary,
    build_lead_time_and_otif,
)
from src.reporting import (
    write_samples,
    write_validation_files,
)

__all__ = [
    'build_vendor_name_map',
    'load_purchase_prices',
    'aggregate_purchases',
    'aggregate_sales',
    'aggregate_freight',
    'compute_avg_inventory_by_vendor_brand',
    'aggregate_sales_by_month',
    'build_final_summary',
    'build_lead_time_and_otif',
    'write_samples',
    'write_validation_files',
]
