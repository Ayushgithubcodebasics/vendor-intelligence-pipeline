-- =============================================================================
-- 03_inventory_and_working_capital.sql
-- Business question: Where is working capital tied up in unsold stock, and
-- which vendors and SKUs represent the highest recovery opportunity?
--
-- Requires: inventory.db populated via `python -m src.ingest_sqlite`
-- Tables used: vendor_summary
-- Key techniques: CTE, window functions (SUM OVER, RANK), CASE WHEN
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. Unsold inventory exposure by vendor with share of total
-- Answers: Which vendors concentrate working capital risk in unsold stock?
-- Used in Finding 3 of findings.md ($15.6M total, top-10 hold 64.9%).
-- -----------------------------------------------------------------------------

WITH vendor_unsold AS (
    SELECT
        VendorName,
        ROUND(SUM(UnsoldInventoryValue), 2)  AS UnsoldValue,
        COUNT(*)                              AS SKUCount
    FROM vendor_summary
    WHERE CostBasisAvailable = 1
    GROUP BY VendorName
),
total AS (
    SELECT SUM(UnsoldValue) AS GrandTotal FROM vendor_unsold
)
SELECT
    v.VendorName,
    v.UnsoldValue,
    v.SKUCount,
    ROUND(v.UnsoldValue / t.GrandTotal * 100, 2)            AS ShareOfTotalPct,
    ROUND(
        SUM(v.UnsoldValue) OVER (
            ORDER BY v.UnsoldValue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) / t.GrandTotal * 100
    , 2)                                                      AS CumulativeSharePct,
    RANK() OVER (ORDER BY v.UnsoldValue DESC)                AS UnsoldRank
FROM vendor_unsold v
CROSS JOIN total t
ORDER BY v.UnsoldValue DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- Q2. Highest-value unsold SKUs with sell-through context
-- Answers: Which specific products have the most capital tied up, and is the
-- low sell-through a real concern or just procurement scale?
-- Smirnoff Traveler ($169K) and Johnnie Walker positions should surface here.
-- -----------------------------------------------------------------------------

SELECT
    VendorName,
    Description,
    ROUND(TotalPurchaseDollars, 2)                      AS TotalPurchased,
    ROUND(TotalSalesDollars, 2)                         AS TotalSold,
    ROUND(UnsoldInventoryValue, 2)                      AS UnsoldValue,
    ROUND(SellThroughRate * 100, 1)                     AS SellThroughPct,
    CASE
        WHEN SellThroughRate < 0.80 THEN 'Critical — <80% sold'
        WHEN SellThroughRate < 0.90 THEN 'At risk — 80–90% sold'
        WHEN SellThroughRate < 0.95 THEN 'Monitor — 90–95% sold'
        ELSE                              'Healthy — >95% sold'
    END                                                  AS SellThroughStatus,
    RANK() OVER (ORDER BY UnsoldInventoryValue DESC)     AS UnsoldRank
FROM vendor_summary
WHERE CostBasisAvailable = 1
  AND UnsoldInventoryValue > 0
ORDER BY UnsoldInventoryValue DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- Q3. Vendors with critically low sell-through (>20% of procurement unsold)
-- Answers: Which vendor relationships may involve over-ordering or
-- discontinued product lines requiring return negotiation or markdown?
-- -----------------------------------------------------------------------------

WITH vendor_st AS (
    SELECT
        VendorName,
        COUNT(*)                                    AS SKUCount,
        ROUND(SUM(TotalPurchaseDollars), 2)        AS TotalProcured,
        ROUND(SUM(UnsoldInventoryValue), 2)        AS TotalUnsold,
        ROUND(
            SUM(UnsoldInventoryValue)
            / NULLIF(SUM(TotalPurchaseDollars), 0) * 100
        , 1)                                        AS UnsoldRatioPct
    FROM vendor_summary
    WHERE CostBasisAvailable = 1
      AND TotalPurchaseDollars > 1000   -- exclude micro-volume vendors
    GROUP BY VendorName
)
SELECT
    VendorName,
    SKUCount,
    TotalProcured,
    TotalUnsold,
    UnsoldRatioPct
FROM vendor_st
WHERE UnsoldRatioPct > 20
ORDER BY UnsoldRatioPct DESC;
