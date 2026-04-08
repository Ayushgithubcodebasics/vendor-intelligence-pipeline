-- =============================================================================
-- 01_vendor_concentration.sql
-- Business question: Which vendors concentrate procurement risk, and how does
-- that concentration look cumulatively across the supplier base?
--
-- Requires: inventory.db populated via `python -m src.ingest_sqlite`
-- Tables used: purchases, vendor_summary
-- Key techniques: CTE, window functions (SUM OVER, RANK, ROUND)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. Top 10 vendors by procurement spend with cumulative concentration %
-- Answers: Where is the top-10 concentration threshold, and which vendors
-- cross it? Used in Finding 1 of findings.md ($210.3M / 65.3%).
-- -----------------------------------------------------------------------------

WITH vendor_spend AS (
    -- Aggregate spend per vendor. VendorName may have legal-name variants;
    -- we take the most frequent name per VendorNumber to canonicalize.
    SELECT
        VendorNumber,
        VendorName,
        ROUND(SUM(Dollars), 2) AS TotalPurchaseDollars
    FROM purchases
    WHERE PurchasePrice > 0   -- exclude zero-price rows (no cost basis)
    GROUP BY VendorNumber, VendorName
),
vendor_total AS (
    -- Sum across all name variants to get one total per vendor
    SELECT VendorNumber, SUM(TotalPurchaseDollars) AS TotalPurchaseDollars
    FROM vendor_spend
    GROUP BY VendorNumber
),
vendor_canonical AS (
    -- Pick the most frequent name variant per vendor
    SELECT VendorNumber, VendorName,
           ROW_NUMBER() OVER (PARTITION BY VendorNumber ORDER BY SUM(TotalPurchaseDollars) DESC) AS rn
    FROM vendor_spend
    GROUP BY VendorNumber, VendorName
),
ranked AS (
    SELECT
        vt.VendorNumber,
        vc.VendorName,
        vt.TotalPurchaseDollars,
        RANK() OVER (ORDER BY vt.TotalPurchaseDollars DESC)      AS SpendRank,
        ROUND(vt.TotalPurchaseDollars
              / SUM(vt.TotalPurchaseDollars) OVER () * 100, 2)   AS SharePct,
        ROUND(
            SUM(vt.TotalPurchaseDollars) OVER (
                ORDER BY vt.TotalPurchaseDollars DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) / SUM(vt.TotalPurchaseDollars) OVER () * 100
        , 2)                                                      AS CumulativeSharePct
    FROM vendor_total vt
    JOIN vendor_canonical vc
      ON vt.VendorNumber = vc.VendorNumber AND vc.rn = 1
)
SELECT
    SpendRank,
    VendorName,
    TotalPurchaseDollars,
    SharePct,
    CumulativeSharePct
FROM ranked
WHERE SpendRank <= 10
ORDER BY SpendRank;


-- -----------------------------------------------------------------------------
-- Q2. ABC vendor classification by procurement spend
-- A = top 80% of cumulative spend (critical vendors)
-- B = next 15% (important vendors)
-- C = remaining 5% (tail vendors)
-- Used to prioritise vendor management effort and diversification review.
-- -----------------------------------------------------------------------------

WITH vendor_spend AS (
    SELECT
        VendorNumber,
        ROUND(SUM(Dollars), 2) AS TotalPurchaseDollars
    FROM purchases
    WHERE PurchasePrice > 0
    GROUP BY VendorNumber, VendorName
),
vendor_total AS (
    SELECT VendorNumber, SUM(TotalPurchaseDollars) AS TotalPurchaseDollars
    FROM vendor_spend GROUP BY VendorNumber
),
cumulative AS (
    SELECT
        VendorNumber,
        TotalPurchaseDollars,
        ROUND(
            SUM(TotalPurchaseDollars) OVER (
                ORDER BY TotalPurchaseDollars DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
            / SUM(TotalPurchaseDollars) OVER () * 100
        , 2) AS CumulativeSharePct
    FROM vendor_total
)
SELECT
    CASE
        WHEN CumulativeSharePct <= 80 THEN 'A — Critical'
        WHEN CumulativeSharePct <= 95 THEN 'B — Important'
        ELSE                               'C — Tail'
    END                                 AS ABCTier,
    COUNT(*)                            AS VendorCount,
    ROUND(SUM(TotalPurchaseDollars), 2) AS TierSpend,
    ROUND(
        SUM(TotalPurchaseDollars) / (SELECT SUM(Dollars) FROM purchases WHERE PurchasePrice > 0) * 100
    , 1)                                AS TierSharePct
FROM cumulative c
GROUP BY ABCTier
ORDER BY TierSpend DESC;
