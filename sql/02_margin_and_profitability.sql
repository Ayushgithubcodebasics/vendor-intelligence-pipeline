-- =============================================================================
-- 02_margin_and_profitability.sql
-- Business question: Which vendor-brand combinations are profitable and which
-- are structurally loss-making? Where should Category Management focus first?
--
-- Requires: inventory.db populated via `python -m src.ingest_sqlite`
-- Tables used: vendor_summary
-- Key techniques: CTE, CASE WHEN, window functions (NTILE, RANK), filtering
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. Vendor-level gross profit ranked, with margin tier classification
-- Answers: Which vendors generate the most gross profit, and how efficient
-- is each one relative to the portfolio average?
-- -----------------------------------------------------------------------------

WITH vendor_gp AS (
    SELECT
        VendorName,
        ROUND(SUM(TotalSalesDollars), 2)    AS TotalSales,
        ROUND(SUM(TotalPurchaseDollars), 2) AS TotalPurchase,
        ROUND(SUM(GrossProfit), 2)          AS GrossProfit
    FROM vendor_summary
    WHERE CostBasisAvailable = 1
      AND TotalSalesDollars > 0
    GROUP BY VendorName
)
SELECT
    VendorName,
    TotalSales,
    TotalPurchase,
    GrossProfit,
    ROUND(GrossProfit / TotalSales * 100, 2)    AS MarginPct,
    RANK() OVER (ORDER BY GrossProfit DESC)      AS GPRank,
    CASE
        WHEN GrossProfit / TotalSales * 100 >= 30 THEN 'High margin (≥30%)'
        WHEN GrossProfit / TotalSales * 100 >= 20 THEN 'Healthy margin (20–30%)'
        WHEN GrossProfit / TotalSales * 100 >= 0  THEN 'Low margin (0–20%)'
        ELSE                                           'Negative margin'
    END                                          AS MarginTier
FROM vendor_gp
ORDER BY GrossProfit DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- Q2. Negative-margin SKUs with material sales volume (>$50K annual sales)
-- Answers: Which specific products are loss-making at scale?
-- These are the SKUs for pricing or sourcing renegotiation.
-- Used in Finding 2 of findings.md (Buehler Znfdl Napa at -15.7% etc.)
-- -----------------------------------------------------------------------------

SELECT
    VendorName,
    Brand,
    Description,
    ROUND(TotalSalesDollars, 2)                     AS AnnualSales,
    ROUND(TotalPurchaseDollars, 2)                  AS AnnualCost,
    ROUND(GrossProfit, 2)                           AS GrossProfit,
    ROUND(ProfitMargin, 2)                          AS MarginPct,
    RANK() OVER (ORDER BY ProfitMargin ASC)         AS WorstMarginRank
FROM vendor_summary
WHERE CostBasisAvailable = 1
  AND TotalSalesDollars  > 50000   -- material volume only
  AND ProfitMargin       < 0       -- loss-making rows only
  AND ProfitMargin       > -100    -- exclude extreme period-aggregation outliers
ORDER BY ProfitMargin ASC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- Q3. Portfolio margin quartile distribution
-- Answers: How is margin spread across the full vendor-brand portfolio?
-- Used to understand whether the negative-margin SKUs are isolated outliers
-- or part of a broader pricing problem.
-- -----------------------------------------------------------------------------

WITH margin_bands AS (
    SELECT
        NTILE(4) OVER (ORDER BY ProfitMargin) AS Quartile,
        ProfitMargin
    FROM vendor_summary
    WHERE CostBasisAvailable = 1
      AND TotalSalesDollars  > 0
      AND ProfitMargin BETWEEN -100 AND 100   -- filter extreme outliers
)
SELECT
    Quartile,
    COUNT(*)                         AS SKUCount,
    ROUND(MIN(ProfitMargin), 1)      AS MinMarginPct,
    ROUND(AVG(ProfitMargin), 1)      AS AvgMarginPct,
    ROUND(MAX(ProfitMargin), 1)      AS MaxMarginPct
FROM margin_bands
GROUP BY Quartile
ORDER BY Quartile;
