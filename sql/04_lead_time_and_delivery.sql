-- =============================================================================
-- 04_lead_time_and_delivery.sql
-- Business question: How reliable is vendor delivery, and which suppliers
-- introduce the most scheduling uncertainty despite acceptable average times?
--
-- Requires: inventory.db populated via `python -m src.ingest_sqlite`
-- Tables used: purchases
-- Key techniques: CTE, window functions (AVG OVER, RANK, LAG), date arithmetic,
--                CASE WHEN, GROUP BY HAVING
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q1. Vendor lead time summary — average, variance, and OTIF against 14-day SLA
-- Answers: Which vendors are reliably on time vs. which introduce risk?
-- All vendors meet the 14-day SLA on this dataset — variance is the
-- differentiator. Used in Finding 5 of findings.md.
-- -----------------------------------------------------------------------------

WITH po_level AS (
    SELECT
        VendorNumber,
        VendorName,
        PONumber,
        MIN(PODate)        AS PODate,
        MIN(ReceivingDate) AS ReceivingDate,
        -- Lead time in days. Negative values (receiving before PO) are excluded.
        JULIANDAY(MIN(ReceivingDate)) - JULIANDAY(MIN(PODate)) AS LeadTimeDays
    FROM purchases
    WHERE PODate       IS NOT NULL
      AND ReceivingDate IS NOT NULL
    GROUP BY VendorNumber, PONumber
    HAVING LeadTimeDays >= 0   -- exclude data-quality anomalies
),
vendor_stats AS (
    SELECT
        VendorNumber,
        -- Canonical vendor name: most-frequent name variant per vendor ID
        (
            SELECT VendorName FROM po_level p2
            WHERE p2.VendorNumber = p.VendorNumber
            GROUP BY VendorName ORDER BY COUNT(*) DESC LIMIT 1
        )                                               AS VendorName,
        COUNT(DISTINCT PONumber)                        AS TotalPOs,
        ROUND(AVG(LeadTimeDays), 1)                     AS AvgLeadDays,
        ROUND(MIN(LeadTimeDays), 0)                     AS MinLeadDays,
        ROUND(MAX(LeadTimeDays), 0)                     AS MaxLeadDays,
        -- Population variance: measures spread around the mean
        ROUND(
            AVG(LeadTimeDays * LeadTimeDays) - AVG(LeadTimeDays) * AVG(LeadTimeDays)
        , 2)                                            AS LeadTimeVariance,
        -- OTIF: % of POs received within 14-day SLA proxy
        ROUND(
            SUM(CASE WHEN LeadTimeDays <= 14 THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 1
        )                                               AS OTIFRatePct,
        CASE
            WHEN SUM(CASE WHEN LeadTimeDays <= 14 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) >= 95
                THEN 'TIER_1_RELIABLE'
            WHEN SUM(CASE WHEN LeadTimeDays <= 14 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) >= 80
                THEN 'TIER_2_ACCEPTABLE'
            ELSE 'TIER_3_AT_RISK'
        END                                             AS ReliabilityTier
    FROM po_level p
    GROUP BY VendorNumber
    HAVING TotalPOs >= 5   -- exclude vendors with too few POs for meaningful stats
)
SELECT
    VendorName,
    TotalPOs,
    AvgLeadDays,
    MinLeadDays,
    MaxLeadDays,
    LeadTimeVariance,
    OTIFRatePct,
    ReliabilityTier,
    RANK() OVER (ORDER BY LeadTimeVariance DESC) AS VarianceRank
FROM vendor_stats
ORDER BY LeadTimeVariance DESC
LIMIT 15;


-- -----------------------------------------------------------------------------
-- Q2. Month-over-month purchase volume trend using LAG()
-- Answers: Is procurement volume growing, shrinking, or seasonal?
-- Complements the sales seasonality finding (Finding 4) — do purchase
-- volumes lead or lag the Q4 revenue peak?
-- -----------------------------------------------------------------------------

WITH monthly AS (
    SELECT
        STRFTIME('%Y-%m', PODate)     AS YearMonth,
        ROUND(SUM(Dollars), 2)        AS MonthlyPurchaseDollars,
        COUNT(DISTINCT VendorNumber)  AS ActiveVendors,
        COUNT(DISTINCT PONumber)      AS TotalPOs
    FROM purchases
    WHERE PODate IS NOT NULL
      AND PurchasePrice > 0
    GROUP BY YearMonth
)
SELECT
    YearMonth,
    MonthlyPurchaseDollars,
    ActiveVendors,
    TotalPOs,
    LAG(MonthlyPurchaseDollars) OVER (ORDER BY YearMonth) AS PrevMonthDollars,
    ROUND(
        (MonthlyPurchaseDollars - LAG(MonthlyPurchaseDollars) OVER (ORDER BY YearMonth))
        / LAG(MonthlyPurchaseDollars) OVER (ORDER BY YearMonth) * 100
    , 1)                                                   AS MoMChangePct
FROM monthly
ORDER BY YearMonth;


-- -----------------------------------------------------------------------------
-- Q3. Vendors with negative lead times (data quality check)
-- Answers: Are there any purchase orders where goods were received before
-- the PO was raised? These are data integrity issues that should be
-- excluded from lead time calculations.
-- -----------------------------------------------------------------------------

SELECT
    VendorNumber,
    VendorName,
    PONumber,
    PODate,
    ReceivingDate,
    JULIANDAY(ReceivingDate) - JULIANDAY(PODate) AS LeadTimeDays
FROM purchases
WHERE PODate       IS NOT NULL
  AND ReceivingDate IS NOT NULL
  AND JULIANDAY(ReceivingDate) < JULIANDAY(PODate)
ORDER BY LeadTimeDays ASC
LIMIT 20;
