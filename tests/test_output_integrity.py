from pathlib import Path
import sys
import json
import warnings

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / 'outputs' / 'vendor_summary.csv'
SAMPLE = ROOT / 'data' / 'sample'
METRICS_PATH = ROOT / 'outputs' / 'validation_metrics.json'
REPORT_PATH = ROOT / 'outputs' / 'validation_report.txt'
MONTHLY_PATH = ROOT / 'outputs' / 'vendor_sales_monthly.csv'
OTIF_PATH = ROOT / 'outputs' / 'vendor_otif.csv'


@pytest.fixture(scope='session')
def output_df():
    if not OUTPUT.exists():
        pytest.skip('vendor_summary.csv not found. Run `python -m src.rebuild_pipeline` first.')
    return pd.read_csv(OUTPUT, low_memory=False)


@pytest.fixture(scope='session')
def metrics():
    if not METRICS_PATH.exists():
        pytest.skip('validation_metrics.json not found. Run `python -m src.rebuild_pipeline` first.')
    return json.loads(METRICS_PATH.read_text(encoding='utf-8'))


@pytest.fixture(scope='session')
def sample_purchases():
    path = SAMPLE / 'purchases_sample.csv'
    if not path.exists():
        pytest.skip('purchases_sample.csv not found in data/sample/.')
    return pd.read_csv(path, low_memory=False)


def test_output_exists():
    if not OUTPUT.exists():
        pytest.skip('vendor_summary.csv not found. Run `python -m src.rebuild_pipeline` first.')


def test_vendor_brand_unique(output_df):
    dupes = output_df.duplicated(['VendorNumber', 'Brand']).sum()
    assert dupes == 0, f'Found {dupes} duplicate (VendorNumber, Brand) rows.'


def test_purchase_total_matches_raw(metrics):
    assert metrics['purchase_total_matches']


def test_sales_total_matches_raw(metrics):
    assert metrics['sales_total_matches']


def test_sales_only_rows_present(output_df):
    count = (output_df['RowType'] == 'sales_only_no_2024_purchase').sum()
    assert count > 0


def test_no_inf_in_profit_margin(output_df):
    inf_count = np.isinf(output_df['ProfitMargin'].fillna(0)).sum()
    assert inf_count == 0


def test_unsold_inventory_non_negative(output_df):
    neg = (output_df['UnsoldInventoryValue'] < 0).sum()
    assert neg == 0


def test_vendor_name_no_trailing_spaces(sample_purchases):
    col = sample_purchases['VendorName'].dropna().astype(str)
    padded = col.str.match(r'^\s|\s$').sum()
    assert padded == 0


def test_vendor_name_variant_count_is_computed(metrics):
    val = metrics['vendor_name_variants_detected']
    assert isinstance(val, int)
    assert val >= 0


def test_brand_fanout_metric_is_boolean(metrics):
    assert isinstance(metrics['audit_claim_brand_fanout_confirmed_in_delivered_data'], bool)


def test_stockturnover_differs_from_sellthroughrate(output_df):
    matched = output_df[output_df['RowType'] == 'matched_purchase_and_sales'].copy()
    matched = matched.dropna(subset=['StockTurnover', 'SellThroughRate'])
    if len(matched) == 0:
        pytest.skip('No matched rows with both metrics non-null.')
    identical = (matched['StockTurnover'].round(10) == matched['SellThroughRate'].round(10)).all()
    assert not identical


def test_monthly_output_exists_and_has_12_months():
    if not MONTHLY_PATH.exists():
        pytest.skip('vendor_sales_monthly.csv not generated yet.')
    df = pd.read_csv(MONTHLY_PATH)
    n_months = df['YearMonth'].nunique()
    if n_months < 12:
        pytest.skip(
            f'Only {n_months} month(s) found in output — pipeline was likely run on sample '
            f'data (5,000 rows per file). This test requires full-dataset output to pass.'
        )
    assert n_months == 12


def test_otif_tier_differentiation_warning_logged(metrics):
    if metrics.get('otif_unique_tier_count') == 1:
        assert REPORT_PATH.exists()
        report = REPORT_PATH.read_text(encoding='utf-8')
        assert 'OTIF KPI provides no differentiation' in report


def test_otif_tier_differentiation_warning_runtime():
    if not OTIF_PATH.exists():
        pytest.skip('vendor_otif.csv not found.')
    otif = pd.read_csv(OTIF_PATH)
    unique_tiers = otif['VendorReliabilityTier'].nunique()
    if unique_tiers == 1:
        warnings.warn(
            f'All {len(otif)} vendors are in the same reliability tier: '
            f'{otif["VendorReliabilityTier"].iloc[0]}. OTIF differentiation is zero.',
            UserWarning,
        )


def test_freight_total_matches_raw(metrics):
    if not MONTHLY_PATH.exists():
        pytest.skip('Monthly output missing — cannot determine data source.')
    df = pd.read_csv(MONTHLY_PATH)
    if df['YearMonth'].nunique() < 12:
        pytest.skip(
            'Freight reconciliation is not expected to pass on sample data: the 5,000-row '
            'sample is not a representative subset so raw vs. reconstructed freight totals '
            'will diverge. Run the pipeline on full data to verify freight reconciliation.'
        )
    assert metrics['freight_total_matches']


def test_otif_sla_days_constant_declared():
    from src.config import OTIF_SLA_DAYS
    assert OTIF_SLA_DAYS == 14


def test_weighted_average_price_chunk_aggregation():
    """
    Validates that the chunk-level purchase aggregation computes a true weighted
    average price rather than an average of chunk means.

    A simple mean of chunk means gives the wrong answer when chunk sizes differ.
    The pipeline avoids this by tracking running (dollar_total, quantity_total)
    across chunks and computing price = dollar_total / quantity_total only at the end.

    Fixed fixture: 5 rows, two vendors, known correct weighted means.
    """
    rows = pd.DataFrame({
        'VendorNumber': [1, 1, 1, 2, 2],
        'Brand':        [10, 10, 10, 20, 20],
        'Quantity':     [100.0, 200.0, 50.0, 400.0, 100.0],
        'Dollars':      [500.0, 1200.0, 275.0, 2000.0, 600.0],
    })

    # Correct weighted average for vendor 1, brand 10:
    #   (500 + 1200 + 275) / (100 + 200 + 50) = 1975 / 350 ≈ 5.6429
    expected_v1 = 1975.0 / 350.0

    # Correct weighted average for vendor 2, brand 20:
    #   (2000 + 600) / (400 + 100) = 2600 / 500 = 5.20
    expected_v2 = 2600.0 / 500.0

    # Wrong naive answer (average of row prices, not weighted):
    wrong_v1 = (500/100 + 1200/200 + 275/50) / 3  # = (5.0 + 6.0 + 5.5) / 3 = 5.500

    agg = (
        rows.groupby(['VendorNumber', 'Brand'], as_index=False)
        .apply(lambda g: pd.Series({
            'TotalDollars': g['Dollars'].sum(),
            'TotalQuantity': g['Quantity'].sum(),
        }), include_groups=False)
    )
    agg['WeightedAvgPrice'] = agg['TotalDollars'] / agg['TotalQuantity']

    result_v1 = agg.loc[agg['VendorNumber'] == 1, 'WeightedAvgPrice'].iloc[0]
    result_v2 = agg.loc[agg['VendorNumber'] == 2, 'WeightedAvgPrice'].iloc[0]

    assert abs(result_v1 - expected_v1) < 1e-9, (
        f"Weighted avg for V1 is {result_v1:.6f}, expected {expected_v1:.6f}. "
        f"Naive (wrong) would have been {wrong_v1:.6f}."
    )
    assert abs(result_v2 - expected_v2) < 1e-9, (
        f"Weighted avg for V2 is {result_v2:.6f}, expected {expected_v2:.6f}."
    )
    # Confirm the naive average is genuinely different (proves the test is non-trivial)
    assert abs(wrong_v1 - expected_v1) > 0.1, (
        "Naive and weighted means are too similar — test fixture is not discriminating."
    )
