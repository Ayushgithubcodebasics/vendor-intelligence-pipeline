from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.config import CHUNK_SIZE, RAW_DATA_DIR
from src.utils import get_logger

logger = get_logger(__name__)


def _strip(series: pd.Series) -> pd.Series:
    return series.astype('string').str.strip()


def build_vendor_name_map() -> tuple[pd.DataFrame, int]:
    """
    Build a canonical vendor name by finding the most-frequently-seen name
    variant for each VendorNumber across purchases, sales, and invoice files.
    Tie-breaks go to the alphabetically earlier name. Returns the map and
    a count of how many vendors had more than one name variant.
    """
    logger.info('Building canonical vendor name map...')
    counter: dict[tuple[int, str], int] = defaultdict(int)
    sources = [
        ('purchases.csv', 'VendorNumber', 'VendorName'),
        ('sales.csv', 'VendorNo', 'VendorName'),
        ('vendor_invoice.csv', 'VendorNumber', 'VendorName'),
    ]
    for fname, vendor_col, name_col in sources:
        for chunk in pd.read_csv(
            RAW_DATA_DIR / fname,
            usecols=[vendor_col, name_col],
            chunksize=CHUNK_SIZE,
            low_memory=False,
        ):
            chunk = chunk.rename(columns={vendor_col: 'VendorNumber', name_col: 'VendorName'})
            chunk['VendorName'] = _strip(chunk['VendorName'])
            chunk = chunk.dropna(subset=['VendorNumber', 'VendorName'])
            grp = chunk.groupby(['VendorNumber', 'VendorName']).size().reset_index(name='count')
            for row in grp.itertuples(index=False):
                counter[(int(row.VendorNumber), str(row.VendorName))] += int(row.count)

    best: dict[int, tuple[str, int]] = {}
    for (vendor, name), count in counter.items():
        current = best.get(vendor)
        if current is None or count > current[1] or (count == current[1] and name < current[0]):
            best[vendor] = (name, count)

    vendor_name_df = pd.DataFrame(
        [{'VendorNumber': vendor, 'CanonicalVendorName': name_count[0]} for vendor, name_count in sorted(best.items())]
    )
    seen_names: dict[int, set[str]] = defaultdict(set)
    for vendor, name in counter:
        seen_names[vendor].add(name)
    variant_count = sum(1 for names in seen_names.values() if len(names) > 1)
    return vendor_name_df, variant_count


def load_purchase_prices() -> tuple[pd.DataFrame, int, bool]:
    logger.info('Loading purchase_prices.csv...')
    pp = pd.read_csv(RAW_DATA_DIR / 'purchase_prices.csv', low_memory=False)
    pp['Description'] = _strip(pp['Description'])
    pp['Price'] = pd.to_numeric(pp['Price'], errors='coerce')
    pp['Volume'] = pd.to_numeric(pp['Volume'], errors='coerce')
    unknown_volume_rows = int(pp['Volume'].isna().sum())
    raw_brand_count = len(pp)
    pp = pp.sort_values(['Brand', 'Description', 'Price'], ascending=[True, True, False])
    pp = pp.drop_duplicates(subset=['Brand'], keep='first').rename(columns={'Price': 'ActualPrice'})
    brand_fanout_detected = bool(len(pp) < raw_brand_count)
    return pp[['Brand', 'Description', 'ActualPrice', 'Volume']], unknown_volume_rows, brand_fanout_detected


def aggregate_purchases() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    """
    Aggregate purchases.csv in chunks, computing a true weighted average
    purchase price per vendor-brand (not a chunk-level mean). Rows where
    PurchasePrice = 0 are excluded from aggregation and counted separately.
    Returns: aggregated purchases, zero-price row counts, PO-level date map,
    and total zero-price row count.
    """
    logger.info('Aggregating purchases.csv...')
    purchase_map: dict[tuple[int, int], dict[str, float | str]] = {}
    zero_map: dict[tuple[int, int], int] = defaultdict(int)
    po_map: dict[tuple[int, int], tuple[pd.Timestamp, pd.Timestamp]] = {}
    zero_price_rows = 0

    usecols = [
        'VendorNumber',
        'VendorName',
        'Brand',
        'Description',
        'PONumber',
        'PODate',
        'ReceivingDate',
        'PurchasePrice',
        'Quantity',
        'Dollars',
    ]
    for chunk in pd.read_csv(RAW_DATA_DIR / 'purchases.csv', usecols=usecols, chunksize=CHUNK_SIZE, low_memory=False):
        chunk['Description'] = _strip(chunk['Description'])
        chunk['PurchasePrice'] = pd.to_numeric(chunk['PurchasePrice'], errors='coerce')
        chunk['Quantity'] = pd.to_numeric(chunk['Quantity'], errors='coerce').fillna(0)
        chunk['Dollars'] = pd.to_numeric(chunk['Dollars'], errors='coerce').fillna(0)

        zero_mask = chunk['PurchasePrice'].fillna(0).eq(0)
        zero_price_rows += int(zero_mask.sum())
        if zero_mask.any():
            zgrp = chunk.loc[zero_mask].groupby(['VendorNumber', 'Brand']).size().reset_index(name='ZeroPriceRowsExcluded')
            for row in zgrp.itertuples(index=False):
                zero_map[(int(row.VendorNumber), int(row.Brand))] += int(row.ZeroPriceRowsExcluded)

        pos = chunk.loc[~zero_mask]
        if not pos.empty:
            grp = pos.groupby(['VendorNumber', 'Brand'], as_index=False).agg(
                Description=('Description', 'first'),
                PurchasePrice=('PurchasePrice', 'mean'),
                TotalPurchaseQuantity=('Quantity', 'sum'),
                TotalPurchaseDollars=('Dollars', 'sum'),
            )
            for row in grp.itertuples(index=False):
                key = (int(row.VendorNumber), int(row.Brand))
                qty = float(row.TotalPurchaseQuantity)
                price = float(row.PurchasePrice)
                if key not in purchase_map:
                    purchase_map[key] = {
                        'Description': str(row.Description),
                        'PurchasePrice': price,
                        'TotalPurchaseQuantity': qty,
                        'TotalPurchaseDollars': float(row.TotalPurchaseDollars),
                        '_qty_for_price': qty,
                    }
                else:
                    prev_qty = float(purchase_map[key]['_qty_for_price'])
                    purchase_map[key]['TotalPurchaseQuantity'] += qty
                    purchase_map[key]['TotalPurchaseDollars'] += float(row.TotalPurchaseDollars)
                    if prev_qty + qty > 0:
                        purchase_map[key]['PurchasePrice'] = (
                            float(purchase_map[key]['PurchasePrice']) * prev_qty + price * qty
                        ) / (prev_qty + qty)
                    purchase_map[key]['_qty_for_price'] = prev_qty + qty

        dates = chunk[['VendorNumber', 'PONumber', 'PODate', 'ReceivingDate']].dropna().copy()
        if not dates.empty:
            dates['PODate'] = pd.to_datetime(dates['PODate'], errors='coerce')
            dates['ReceivingDate'] = pd.to_datetime(dates['ReceivingDate'], errors='coerce')
            dates = dates.dropna(subset=['PODate', 'ReceivingDate'])
            po_grp = dates.groupby(['VendorNumber', 'PONumber'], as_index=False).agg(
                PODate=('PODate', 'min'),
                ReceivingDate=('ReceivingDate', 'max'),
            )
            for row in po_grp.itertuples(index=False):
                key = (int(row.VendorNumber), int(row.PONumber))
                po_date = pd.Timestamp(row.PODate)
                recv_date = pd.Timestamp(row.ReceivingDate)
                if key not in po_map:
                    po_map[key] = (po_date, recv_date)
                else:
                    cur_po, cur_recv = po_map[key]
                    po_map[key] = (min(cur_po, po_date), max(cur_recv, recv_date))

    purchases = pd.DataFrame([
        {
            'VendorNumber': k[0],
            'Brand': k[1],
            'Description': v['Description'],
            'PurchasePrice': v['PurchasePrice'],
            'TotalPurchaseQuantity': v['TotalPurchaseQuantity'],
            'TotalPurchaseDollars': v['TotalPurchaseDollars'],
        }
        for k, v in sorted(purchase_map.items())
    ])

    zero_df = pd.DataFrame([
        {'VendorNumber': k[0], 'Brand': k[1], 'ZeroPriceRowsExcluded': v}
        for k, v in sorted(zero_map.items())
    ])

    po_df = pd.DataFrame([
        {'VendorNumber': k[0], 'PONumber': k[1], 'PODate': v[0], 'ReceivingDate': v[1]}
        for k, v in sorted(po_map.items())
    ])

    return purchases, zero_df, po_df, zero_price_rows


def aggregate_sales() -> pd.DataFrame:
    logger.info('Aggregating sales.csv...')
    sales_map: dict[tuple[int, int], dict[str, float | str]] = {}
    usecols = ['VendorNo', 'VendorName', 'Brand', 'Description', 'SalesQuantity', 'SalesDollars', 'SalesPrice', 'ExciseTax']
    for chunk in pd.read_csv(RAW_DATA_DIR / 'sales.csv', usecols=usecols, chunksize=CHUNK_SIZE, low_memory=False):
        chunk['Description'] = _strip(chunk['Description'])
        for col in ['SalesQuantity', 'SalesDollars', 'SalesPrice', 'ExciseTax']:
            chunk[col] = pd.to_numeric(chunk[col], errors='coerce').fillna(0)
        grp = chunk.groupby(['VendorNo', 'Brand'], as_index=False).agg(
            SalesDescription=('Description', 'first'),
            TotalSalesQuantity=('SalesQuantity', 'sum'),
            TotalSalesDollars=('SalesDollars', 'sum'),
            TotalSalesPrice=('SalesPrice', 'sum'),
            TotalExciseTax=('ExciseTax', 'sum'),
        )
        for row in grp.itertuples(index=False):
            key = (int(row.VendorNo), int(row.Brand))
            if key not in sales_map:
                sales_map[key] = {
                    'SalesDescription': str(row.SalesDescription),
                    'TotalSalesQuantity': float(row.TotalSalesQuantity),
                    'TotalSalesDollars': float(row.TotalSalesDollars),
                    'TotalSalesPrice': float(row.TotalSalesPrice),
                    'TotalExciseTax': float(row.TotalExciseTax),
                }
            else:
                sales_map[key]['TotalSalesQuantity'] += float(row.TotalSalesQuantity)
                sales_map[key]['TotalSalesDollars'] += float(row.TotalSalesDollars)
                sales_map[key]['TotalSalesPrice'] += float(row.TotalSalesPrice)
                sales_map[key]['TotalExciseTax'] += float(row.TotalExciseTax)

    return pd.DataFrame([
        {
            'VendorNo': k[0],
            'Brand': k[1],
            'SalesDescription': v['SalesDescription'],
            'TotalSalesQuantity': v['TotalSalesQuantity'],
            'TotalSalesDollars': v['TotalSalesDollars'],
            'TotalSalesPrice': v['TotalSalesPrice'],
            'TotalExciseTax': v['TotalExciseTax'],
        }
        for k, v in sorted(sales_map.items())
    ])


def aggregate_freight() -> pd.DataFrame:
    logger.info('Aggregating vendor_invoice.csv...')
    freight_map: dict[int, float] = defaultdict(float)
    for chunk in pd.read_csv(RAW_DATA_DIR / 'vendor_invoice.csv', usecols=['VendorNumber', 'Freight'], chunksize=CHUNK_SIZE, low_memory=False):
        chunk['Freight'] = pd.to_numeric(chunk['Freight'], errors='coerce').fillna(0)
        grp = chunk.groupby('VendorNumber', as_index=False)['Freight'].sum()
        for row in grp.itertuples(index=False):
            freight_map[int(row.VendorNumber)] += float(row.Freight)
    return pd.DataFrame([{'VendorNumber': k, 'FreightCost': v} for k, v in sorted(freight_map.items())])


def compute_avg_inventory_by_vendor_brand(vendor_brand_purchases: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    logger.info('Computing average inventory value by vendor-brand...')
    begin_chunks, end_chunks = [], []
    for chunk in pd.read_csv(
        RAW_DATA_DIR / 'begin_inventory.csv',
        usecols=['Brand', 'onHand', 'Price'],
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        chunk['onHand'] = pd.to_numeric(chunk['onHand'], errors='coerce').fillna(0)
        chunk['Price'] = pd.to_numeric(chunk['Price'], errors='coerce').fillna(0)
        chunk['InventoryValue'] = chunk['onHand'] * chunk['Price']
        begin_chunks.append(chunk.groupby('Brand', as_index=False)['InventoryValue'].sum())
    begin_val = pd.concat(begin_chunks, ignore_index=True).groupby('Brand', as_index=False)['InventoryValue'].sum()
    begin_val = begin_val.rename(columns={'InventoryValue': 'BeginValue'})

    for chunk in pd.read_csv(
        RAW_DATA_DIR / 'end_inventory.csv',
        usecols=['Brand', 'onHand', 'Price'],
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        chunk['onHand'] = pd.to_numeric(chunk['onHand'], errors='coerce').fillna(0)
        chunk['Price'] = pd.to_numeric(chunk['Price'], errors='coerce').fillna(0)
        chunk['InventoryValue'] = chunk['onHand'] * chunk['Price']
        end_chunks.append(chunk.groupby('Brand', as_index=False)['InventoryValue'].sum())
    end_val = pd.concat(end_chunks, ignore_index=True).groupby('Brand', as_index=False)['InventoryValue'].sum()
    end_val = end_val.rename(columns={'InventoryValue': 'EndValue'})

    inv = begin_val.merge(end_val, on='Brand', how='outer').fillna(0)
    inv['AvgInventoryValue'] = (inv['BeginValue'] + inv['EndValue']) / 2

    vendor_brand = vendor_brand_purchases[['VendorNumber', 'Brand', 'TotalPurchaseDollars']].copy()
    brand_totals = vendor_brand.groupby('Brand', as_index=False)['TotalPurchaseDollars'].sum().rename(columns={'TotalPurchaseDollars': 'BrandPurchaseTotal'})
    vendor_brand = vendor_brand.merge(brand_totals, on='Brand', how='left')
    vendor_brand['InventoryShare'] = vendor_brand['TotalPurchaseDollars'] / vendor_brand['BrandPurchaseTotal']
    vendor_brand['InventoryShare'] = vendor_brand['InventoryShare'].fillna(0)

    alloc = inv.merge(vendor_brand[['VendorNumber', 'Brand', 'InventoryShare']], on='Brand', how='left')
    unmatched = int(alloc['VendorNumber'].isna().sum())
    if unmatched > 0:
        logger.warning(
            '%d Brand rows in inventory have no purchase-side VendorNumber match — excluded from StockTurnover calculation.',
            unmatched,
        )
    alloc = alloc.dropna(subset=['VendorNumber']).copy()
    alloc['VendorNumber'] = alloc['VendorNumber'].astype(int)
    alloc['AllocatedAvgInventoryValue'] = alloc['AvgInventoryValue'] * alloc['InventoryShare']
    vendor_brand_inv = alloc.groupby(['VendorNumber', 'Brand'], as_index=False)['AllocatedAvgInventoryValue'].sum()
    return vendor_brand_inv, unmatched


def aggregate_sales_by_month() -> pd.DataFrame:
    logger.info('Aggregating sales by month...')
    monthly_map: dict[tuple[int, int, str], dict[str, float]] = {}
    usecols = ['VendorNo', 'Brand', 'SalesDate', 'SalesQuantity', 'SalesDollars']
    for chunk in pd.read_csv(
        RAW_DATA_DIR / 'sales.csv',
        usecols=usecols,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        chunk['SalesDate'] = pd.to_datetime(chunk['SalesDate'], errors='coerce')
        chunk = chunk.dropna(subset=['SalesDate'])
        chunk['YearMonth'] = chunk['SalesDate'].dt.to_period('M').astype(str)
        chunk['SalesQuantity'] = pd.to_numeric(chunk['SalesQuantity'], errors='coerce').fillna(0)
        chunk['SalesDollars'] = pd.to_numeric(chunk['SalesDollars'], errors='coerce').fillna(0)
        grp = chunk.groupby(['VendorNo', 'Brand', 'YearMonth'], as_index=False).agg(
            MonthlyQuantity=('SalesQuantity', 'sum'),
            MonthlyDollars=('SalesDollars', 'sum'),
        )
        for row in grp.itertuples(index=False):
            key = (int(row.VendorNo), int(row.Brand), str(row.YearMonth))
            if key not in monthly_map:
                monthly_map[key] = {'MonthlyQuantity': 0.0, 'MonthlyDollars': 0.0}
            monthly_map[key]['MonthlyQuantity'] += float(row.MonthlyQuantity)
            monthly_map[key]['MonthlyDollars'] += float(row.MonthlyDollars)

    return pd.DataFrame([
        {
            'VendorNumber': k[0],
            'Brand': k[1],
            'YearMonth': k[2],
            'MonthlyQuantity': v['MonthlyQuantity'],
            'MonthlyDollars': v['MonthlyDollars'],
        }
        for k, v in sorted(monthly_map.items())
    ])
