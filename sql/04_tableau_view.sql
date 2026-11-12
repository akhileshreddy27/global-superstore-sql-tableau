-- =====================================================================
-- GLOBAL SUPERSTORE — 04: TABLEAU DATA SOURCE
-- One enriched, line-level view that joins all three tables.
-- scripts/run_sql.py exports it to tableau/superstore_tableau_source.csv,
-- which the Tableau workbook (tableau/Global_Superstore_Dashboard.twb) reads.
-- =====================================================================

USE global_superstore;

CREATE OR REPLACE VIEW v_orders_enriched AS
SELECT
    o.`Row ID`,
    o.`Order ID`,
    o.`Order Date`,
    o.`Ship Date`,
    o.`Ship Mode`,
    o.`Customer ID`,
    o.`Customer Name`,
    o.Segment,
    o.City,
    o.State,
    o.Country,
    o.Market,
    o.Region,
    CONCAT(o.Market, ' - ', o.Region)                     AS `Market Region`,
    p.Person                                              AS `Regional Manager`,
    o.`Product ID`,
    o.Category,
    o.`Sub-Category`,
    o.`Product Name`,
    o.Sales,
    o.Quantity,
    o.Discount,
    CASE
        WHEN o.Discount = 0     THEN '0%'
        WHEN o.Discount <= 0.10 THEN '0-10%'
        WHEN o.Discount <= 0.20 THEN '10-20%'
        WHEN o.Discount <= 0.30 THEN '20-30%'
        WHEN o.Discount <= 0.50 THEN '30-50%'
        ELSE '50%+'
    END                                                   AS `Discount Band`,
    o.Profit,
    o.`Shipping Cost`,
    o.`Order Priority`,
    DATEDIFF(o.`Ship Date`, o.`Order Date`)               AS `Ship Days`,
    CASE WHEN r.`Order ID` IS NOT NULL THEN 'Yes' ELSE 'No' END AS Returned,
    CASE WHEN rm.Market IS NOT NULL THEN 'Yes' ELSE 'No' END   AS `Returns Tracked`
FROM Orders o
LEFT JOIN People  p  ON p.Region = o.Region
LEFT JOIN Returns r  ON r.`Order ID` = o.`Order ID` AND r.Market = o.Market
LEFT JOIN (SELECT DISTINCT Market FROM Returns) rm ON rm.Market = o.Market;

-- @output: tableau_source
SELECT * FROM v_orders_enriched ORDER BY `Row ID`;
