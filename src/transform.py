from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import OTIF_SLA_DAYS
from src.ingestion import _strip
from src.utils import get_logger

logger = get_logger(__name__)


def build_lead_time_and_otif(po_df: pd.DataFrame, vendor_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    logger.info('Computing lead time and OTIF outputs...')
    po_df = po_df.copy()
    po_df['LeadTimeDays'] = (po_df['ReceivingDate'] - po_df['PODate']).dt.days
    negative_rows = int((po_df['LeadTimeDays'] < 0).sum())
    valid = po_df.loc[po_df['LeadTimeDays'] >= 0].copy()

    lead = valid.groupby('VendorNumber', as_index=False).agg(
        TotalPOs=('PONumber', 'nunique'),
        AvgLeadTimeDays=('LeadTimeDays', 'mean'),
        MinLeadTimeDays=('LeadTimeDays', 'min'),
        MaxLeadTimeDays=('LeadTimeDays', 'max'),
        LeadTimeVariance=('LeadTimeDays', lambda s: float(np.var(s, ddof=0))),
    )
    neg = po_df.loc[po_df['LeadTimeDays'] < 0].groupby('VendorNumber', as_index=False).size().rename(columns={'size': 'NegativeLeadTimeCount'})
    lead = lead.merge(neg, on='VendorNumber', how='left').fillna({'NegativeLeadTimeCount': 0})
    lead['NegativeLeadTimeCount'] = lead['NegativeLeadTimeCount'].astype(int)
    lead = lead.merge(vendor_map, on='VendorNumber', how='left').rename(columns={'CanonicalVendorName': 'VendorName'})
    lead = lead[['VendorNumber', 'VendorName', 'TotalPOs', 'AvgLeadTimeDays', 'MinLeadTimeDays', 'MaxLeadTimeDays', 'LeadTimeVariance', 'NegativeLeadTimeCount']]
    lead = lead.sort_values(['AvgLeadTimeDays', 'VendorNumber'])

    otif = valid.assign(DeliveredOnTime=(valid['LeadTimeDays'] <= OTIF_SLA_DAYS).astype(int)).groupby('VendorNumber', as_index=False).agg(
        TotalPOs=('PONumber', 'nunique'),
        OnTimePOs=('DeliveredOnTime', 'sum'),
    )
    otif['OTIFRatePct'] = np.where(otif['TotalPOs'] > 0, otif['OnTimePOs'] / otif['TotalPOs'] * 100, np.nan)
    otif['VendorReliabilityTier'] = np.select(
        [otif['OTIFRatePct'] >= 95, otif['OTIFRatePct'] >= 80],
        ['TIER_1_RELIABLE', 'TIER_2_ACCEPTABLE'],
        default='TIER_3_AT_RISK',
    )
    otif = otif.merge(vendor_map, on='VendorNumber', how='left').rename(columns={'CanonicalVendorName': 'VendorName'})
    otif = otif[['VendorNumber', 'VendorName', 'TotalPOs', 'OnTimePOs', 'OTIFRatePct', 'VendorReliabilityTier']]
    otif = otif.sort_values(['OTIFRatePct', 'VendorNumber'], ascending=[False, True])
    return lead, otif, negative_rows


def build_final_summary(
    purchases: pd.DataFrame,
    sales: pd.DataFrame,
    pp: pd.DataFrame,
    freight: pd.DataFrame,
    vendor_map: pd.DataFrame,
    zero_df: pd.DataFrame,
    vendor_inv_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Join purchase aggregates, sales aggregates, price reference, freight,
    and inventory data into the final vendor-brand summary. Appends
    sales-only rows that have no 2024 purchase record. Allocates vendor-level
    freight to individual vendor-brand rows in proportion to purchase dollars.
    """
    logger.info('Building vendor summary...')
    summary = purchases.merge(vendor_map, on='VendorNumber', how='left').rename(columns={'CanonicalVendorName': 'VendorName'})
    summary = summary.merge(pp[['Brand', 'Description', 'ActualPrice', 'Volume']].rename(columns={'Description': 'PPDescription'}), on='Brand', how='left')
    summary['Description'] = summary['Description'].fillna(summary['PPDescription'])
    summary = summary.drop(columns=['PPDescription'])
    summary = summary.merge(sales, left_on=['VendorNumber', 'Brand'], right_on=['VendorNo', 'Brand'], how='left').drop(columns=['VendorNo'])
    summary = summary.merge(freight, on='VendorNumber', how='left').merge(zero_df, on=['VendorNumber', 'Brand'], how='left')

    for col in ['TotalSalesQuantity', 'TotalSalesDollars', 'TotalSalesPrice', 'TotalExciseTax', 'FreightCost', 'ZeroPriceRowsExcluded']:
        summary[col] = pd.to_numeric(summary[col], errors='coerce').fillna(0)

    vendor_purchase_totals = summary.groupby('VendorNumber', as_index=False)['TotalPurchaseDollars'].sum().rename(columns={'TotalPurchaseDollars': 'VendorPurchaseDollars'})
    summary = summary.merge(vendor_purchase_totals, on='VendorNumber', how='left')
    summary['FreightCost'] = np.where(
        summary['VendorPurchaseDollars'] > 0,
        summary['FreightCost'] * (summary['TotalPurchaseDollars'] / summary['VendorPurchaseDollars']),
        0.0,
    )
    summary = summary.drop(columns=['VendorPurchaseDollars'])

    summary['CostBasisAvailable'] = 1
    summary['RowType'] = np.where(summary['TotalSalesDollars'] > 0, 'matched_purchase_and_sales', 'purchase_only_no_sales')
    summary['GrossProfit'] = summary['TotalSalesDollars'] - summary['TotalPurchaseDollars']
    summary['ProfitMargin'] = np.where(summary['TotalSalesDollars'] > 0, summary['GrossProfit'] / summary['TotalSalesDollars'] * 100, np.nan)
    summary['SellThroughRate'] = np.where(summary['TotalPurchaseQuantity'] > 0, summary['TotalSalesQuantity'] / summary['TotalPurchaseQuantity'], np.nan)
    summary['SalesToPurchaseRatio'] = np.where(summary['TotalPurchaseDollars'] > 0, summary['TotalSalesDollars'] / summary['TotalPurchaseDollars'], np.nan)
    summary['UnsoldInventoryValue'] = np.maximum(0, summary['TotalPurchaseQuantity'] - summary['TotalSalesQuantity']) * summary['PurchasePrice']

    if vendor_inv_df is not None and len(vendor_inv_df) > 0:
        summary = summary.merge(vendor_inv_df, on=['VendorNumber', 'Brand'], how='left')
        summary['StockTurnover'] = np.where(
            summary['AllocatedAvgInventoryValue'] > 0,
            summary['TotalPurchaseDollars'] / summary['AllocatedAvgInventoryValue'],
            np.nan,
        )
        summary = summary.drop(columns=['AllocatedAvgInventoryValue'])
    else:
        summary['StockTurnover'] = np.nan
        logger.warning('AllocatedAvgInventoryValue not available — StockTurnover set to null.')

    purchase_keys = summary[['VendorNumber', 'Brand']].drop_duplicates()
    sales_only = sales.rename(columns={'VendorNo': 'VendorNumber'}).merge(purchase_keys, on=['VendorNumber', 'Brand'], how='left', indicator=True)
    sales_only = sales_only.loc[sales_only['_merge'] == 'left_only'].drop(columns=['_merge'])
    if not sales_only.empty:
        sales_only = sales_only.merge(vendor_map, on='VendorNumber', how='left').rename(columns={'CanonicalVendorName': 'VendorName'})
        sales_only = sales_only.merge(pp[['Brand', 'Description', 'ActualPrice', 'Volume']].rename(columns={'Description': 'PPDescription'}), on='Brand', how='left')
        sales_only = sales_only.merge(freight, on='VendorNumber', how='left')
        sales_only['Description'] = sales_only['SalesDescription'].fillna(sales_only['PPDescription'])
        sales_only['PurchasePrice'] = np.nan
        sales_only['TotalPurchaseQuantity'] = 0.0
        sales_only['TotalPurchaseDollars'] = 0.0
        sales_only['ZeroPriceRowsExcluded'] = 0.0
        sales_only['CostBasisAvailable'] = 0
        sales_only['RowType'] = 'sales_only_no_2024_purchase'
        sales_only['GrossProfit'] = np.nan
        sales_only['ProfitMargin'] = np.nan
        sales_only['SellThroughRate'] = np.nan
        sales_only['StockTurnover'] = np.nan
        sales_only['SalesToPurchaseRatio'] = np.nan
        sales_only['UnsoldInventoryValue'] = 0.0
        sales_only['FreightCost'] = 0.0
        sales_only = sales_only[[
            'VendorNumber', 'VendorName', 'Brand', 'Description', 'PurchasePrice', 'ActualPrice', 'Volume',
            'TotalPurchaseQuantity', 'TotalPurchaseDollars', 'TotalSalesQuantity', 'TotalSalesDollars',
            'TotalSalesPrice', 'TotalExciseTax', 'FreightCost', 'GrossProfit', 'ProfitMargin', 'StockTurnover',
            'SellThroughRate', 'SalesToPurchaseRatio', 'UnsoldInventoryValue', 'ZeroPriceRowsExcluded',
            'CostBasisAvailable', 'RowType',
        ]]
    else:
        sales_only = pd.DataFrame(columns=[
            'VendorNumber', 'VendorName', 'Brand', 'Description', 'PurchasePrice', 'ActualPrice', 'Volume',
            'TotalPurchaseQuantity', 'TotalPurchaseDollars', 'TotalSalesQuantity', 'TotalSalesDollars',
            'TotalSalesPrice', 'TotalExciseTax', 'FreightCost', 'GrossProfit', 'ProfitMargin', 'StockTurnover',
            'SellThroughRate', 'SalesToPurchaseRatio', 'UnsoldInventoryValue', 'ZeroPriceRowsExcluded',
            'CostBasisAvailable', 'RowType',
        ])

    summary = summary[[
        'VendorNumber', 'VendorName', 'Brand', 'Description', 'PurchasePrice', 'ActualPrice', 'Volume',
        'TotalPurchaseQuantity', 'TotalPurchaseDollars', 'TotalSalesQuantity', 'TotalSalesDollars',
        'TotalSalesPrice', 'TotalExciseTax', 'FreightCost', 'GrossProfit', 'ProfitMargin', 'StockTurnover',
        'SellThroughRate', 'SalesToPurchaseRatio', 'UnsoldInventoryValue', 'ZeroPriceRowsExcluded',
        'CostBasisAvailable', 'RowType',
    ]]
    final_df = pd.concat([summary, sales_only], ignore_index=True)
    final_df['VendorName'] = _strip(final_df['VendorName'])
    final_df['Description'] = _strip(final_df['Description'])
    final_df = final_df.sort_values(['TotalPurchaseDollars', 'TotalSalesDollars', 'VendorNumber', 'Brand'], ascending=[False, False, True, True]).reset_index(drop=True)
    return final_df
