-- =====================================================================
-- GLOBAL SUPERSTORE — 03: ANALYSIS
-- Every query below is tagged "-- @output: <name>".
-- scripts/run_sql.py executes each one against MySQL and saves the
-- result to outputs/<name>.csv, so every number in the README comes
-- straight from these queries.
--
-- Techniques: aggregations, GROUP BY / HAVING, CASE, multi-table JOINs,
-- CTEs (incl. chained CTEs), window functions (LAG, RANK, DENSE_RANK,
-- ROW_NUMBER, SUM/AVG OVER with frames and partitions).
-- =====================================================================

USE global_superstore;

-- ---------------------------------------------------------------------
-- @output: data_quality_checks
-- Row counts, nulls, duplicates and join integrity after loading.
-- ---------------------------------------------------------------------
SELECT 'orders_rows'                       AS check_name, COUNT(*) AS value FROM Orders
UNION ALL SELECT 'returns_rows',            COUNT(*) FROM Returns
UNION ALL SELECT 'people_rows',             COUNT(*) FROM People
UNION ALL SELECT 'distinct_order_ids',      COUNT(DISTINCT `Order ID`) FROM Orders
UNION ALL SELECT 'order_ids_in_2_markets',  COUNT(*) FROM (
              SELECT `Order ID` FROM Orders GROUP BY `Order ID` HAVING COUNT(DISTINCT Market) > 1) t
UNION ALL SELECT 'duplicate_order_lines',   COUNT(*) FROM (
              SELECT `Order ID`, `Product ID`, `Order Date`, Sales, Quantity, Discount, Profit
              FROM Orders
              GROUP BY `Order ID`, `Product ID`, `Order Date`, Sales, Quantity, Discount, Profit
              HAVING COUNT(*) > 1) t
UNION ALL SELECT 'null_postal_code',        SUM(`Postal Code` IS NULL) FROM Orders
UNION ALL SELECT 'negative_ship_days',      SUM(`Ship Days` < 0) FROM Orders
UNION ALL SELECT 'returns_not_matching_an_order', COUNT(*)
              FROM Returns r LEFT JOIN Orders o
                ON o.`Order ID` = r.`Order ID` AND o.Market = r.Market
              WHERE o.`Order ID` IS NULL
UNION ALL SELECT 'regions_without_manager', COUNT(DISTINCT o.Region)
              FROM Orders o LEFT JOIN People p ON p.Region = o.Region
              WHERE p.Person IS NULL
UNION ALL SELECT 'returned_flag_mismatches', COUNT(*)
              FROM Orders o LEFT JOIN Returns r
                ON r.`Order ID` = o.`Order ID` AND r.Market = o.Market
              WHERE (r.`Order ID` IS NOT NULL) <> (o.Returned = 'Yes')
UNION ALL SELECT 'distinct_customer_ids',   COUNT(DISTINCT `Customer ID`) FROM Orders
UNION ALL SELECT 'distinct_customer_names', COUNT(DISTINCT `Customer Name`) FROM Orders
UNION ALL SELECT 'distinct_product_ids',    COUNT(DISTINCT `Product ID`) FROM Orders
UNION ALL SELECT 'distinct_product_names',  COUNT(DISTINCT `Product Name`) FROM Orders;

-- ---------------------------------------------------------------------
-- @output: kpi_summary
-- Executive KPIs. Returns joined on (Order ID, Market).
-- Note: Customer ID is issued per market (1,590 IDs for 795 people),
-- so unique customers are counted by name.
-- ---------------------------------------------------------------------
WITH returned AS (
    SELECT DISTINCT o.`Order ID`
    FROM Orders o
    JOIN Returns r ON r.`Order ID` = o.`Order ID` AND r.Market = o.Market
)
SELECT
    MIN(`Order Date`)                                        AS first_order_date,
    MAX(`Order Date`)                                        AS last_order_date,
    COUNT(*)                                                 AS order_lines,
    ROUND(SUM(Sales), 2)                                     AS total_sales,
    ROUND(SUM(Profit), 2)                                    AS total_profit,
    ROUND(SUM(Profit) / SUM(Sales) * 100, 2)                 AS profit_margin_pct,
    COUNT(DISTINCT `Order ID`)                               AS orders,
    COUNT(DISTINCT `Customer Name`)                          AS customers,
    COUNT(DISTINCT `Product Name`)                           AS products,
    SUM(Quantity)                                            AS quantity_sold,
    ROUND(SUM(Sales) / COUNT(DISTINCT `Order ID`), 2)        AS avg_order_value,
    (SELECT COUNT(*) FROM returned)                          AS returned_orders,
    ROUND((SELECT COUNT(*) FROM returned)
          / COUNT(DISTINCT `Order ID`) * 100, 2)             AS return_rate_pct
FROM Orders;

-- ---------------------------------------------------------------------
-- @output: yearly_performance
-- CTE + LAG for year-over-year growth; FIRST_VALUE for growth vs 2011.
-- ---------------------------------------------------------------------
WITH yearly AS (
    SELECT YEAR(`Order Date`)          AS sales_year,
           SUM(Sales)                  AS sales,
           SUM(Profit)                 AS profit,
           COUNT(DISTINCT `Order ID`)  AS orders,
           SUM(Quantity)               AS quantity
    FROM Orders
    GROUP BY YEAR(`Order Date`)
)
SELECT sales_year,
       ROUND(sales, 2)                                          AS sales,
       ROUND(profit, 2)                                         AS profit,
       orders,
       quantity,
       ROUND(profit / sales * 100, 2)                           AS profit_margin_pct,
       ROUND((sales - LAG(sales) OVER w) / LAG(sales) OVER w * 100, 2)
                                                                AS yoy_sales_growth_pct,
       ROUND((profit - LAG(profit) OVER w) / LAG(profit) OVER w * 100, 2)
                                                                AS yoy_profit_growth_pct,
       ROUND((sales / FIRST_VALUE(sales) OVER w - 1) * 100, 2)  AS cumulative_growth_vs_2011_pct
FROM yearly
WINDOW w AS (ORDER BY sales_year)
ORDER BY sales_year;

-- ---------------------------------------------------------------------
-- @output: monthly_performance
-- Same-month YoY (LAG 12), year-to-date running total, 3-month moving avg.
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT DATE_FORMAT(`Order Date`, '%Y-%m') AS month,
           YEAR(`Order Date`)                 AS sales_year,
           SUM(Sales)                         AS sales,
           SUM(Profit)                        AS profit,
           COUNT(DISTINCT `Order ID`)         AS orders
    FROM Orders
    GROUP BY DATE_FORMAT(`Order Date`, '%Y-%m'), YEAR(`Order Date`)
)
SELECT month,
       ROUND(sales, 2)                                                    AS sales,
       ROUND(profit, 2)                                                   AS profit,
       orders,
       ROUND(profit / sales * 100, 2)                                     AS profit_margin_pct,
       ROUND((sales - LAG(sales, 12) OVER (ORDER BY month))
             / LAG(sales, 12) OVER (ORDER BY month) * 100, 2)             AS yoy_sales_growth_pct,
       ROUND(SUM(sales) OVER (PARTITION BY sales_year ORDER BY month), 2) AS ytd_sales,
       ROUND(AVG(sales) OVER (ORDER BY month
                              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS sales_3m_moving_avg
FROM monthly
ORDER BY month;

-- ---------------------------------------------------------------------
-- @output: category_performance
-- Aggregation + share of total via SUM() OVER ().
-- ---------------------------------------------------------------------
SELECT Category,
       ROUND(SUM(Sales), 2)                                   AS sales,
       ROUND(SUM(Profit), 2)                                  AS profit,
       COUNT(DISTINCT `Order ID`)                             AS orders,
       SUM(Quantity)                                          AS quantity,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)               AS profit_margin_pct,
       ROUND(SUM(Sales) / SUM(SUM(Sales)) OVER () * 100, 2)   AS sales_share_pct,
       ROUND(SUM(Profit) / SUM(SUM(Profit)) OVER () * 100, 2) AS profit_share_pct
FROM Orders
GROUP BY Category
ORDER BY sales DESC;

-- ---------------------------------------------------------------------
-- @output: subcategory_performance
-- RANK within category (PARTITION BY) and overall sales rank.
-- ---------------------------------------------------------------------
SELECT Category,
       `Sub-Category`                                                  AS sub_category,
       ROUND(SUM(Sales), 2)                                            AS sales,
       ROUND(SUM(Profit), 2)                                           AS profit,
       COUNT(DISTINCT `Order ID`)                                      AS orders,
       SUM(Quantity)                                                   AS quantity,
       ROUND(AVG(Discount) * 100, 2)                                   AS avg_discount_pct,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)                        AS profit_margin_pct,
       ROUND(SUM(Sales) / SUM(SUM(Sales)) OVER () * 100, 2)            AS sales_share_pct,
       RANK() OVER (ORDER BY SUM(Sales) DESC)                          AS overall_sales_rank,
       RANK() OVER (PARTITION BY Category ORDER BY SUM(Profit) DESC)   AS profit_rank_in_category
FROM Orders
GROUP BY Category, `Sub-Category`
ORDER BY sales DESC;

-- ---------------------------------------------------------------------
-- @output: top5_subcategory_share
-- Chained CTEs: concentration of sales in the top five sub-categories.
-- ---------------------------------------------------------------------
WITH sub AS (
    SELECT `Sub-Category` AS sub_category, SUM(Sales) AS sales
    FROM Orders
    GROUP BY `Sub-Category`
),
ranked AS (
    SELECT sub_category, sales,
           ROW_NUMBER() OVER (ORDER BY sales DESC) AS rn
    FROM sub
)
SELECT GROUP_CONCAT(CASE WHEN rn <= 5 THEN sub_category END
                    ORDER BY rn SEPARATOR ', ')                        AS top5_sub_categories,
       ROUND(SUM(CASE WHEN rn <= 5 THEN sales END), 2)                AS top5_sales,
       ROUND(SUM(sales), 2)                                           AS total_sales,
       ROUND(SUM(CASE WHEN rn <= 5 THEN sales END) / SUM(sales) * 100, 2) AS top5_share_pct
FROM ranked;

-- ---------------------------------------------------------------------
-- @output: market_performance
-- ---------------------------------------------------------------------
SELECT Market,
       ROUND(SUM(Sales), 2)                                 AS sales,
       ROUND(SUM(Profit), 2)                                AS profit,
       COUNT(DISTINCT `Order ID`)                           AS orders,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)             AS profit_margin_pct,
       ROUND(SUM(Sales) / SUM(SUM(Sales)) OVER () * 100, 2) AS sales_share_pct,
       DENSE_RANK() OVER (ORDER BY SUM(Sales) DESC)         AS sales_rank
FROM Orders
GROUP BY Market
ORDER BY sales DESC;

-- ---------------------------------------------------------------------
-- @output: region_performance
-- Region names such as Central / North / South are reused by several
-- markets, so the grain is Market + Region.
-- ---------------------------------------------------------------------
WITH region_perf AS (
    SELECT Market, Region,
           SUM(Sales)                 AS sales,
           SUM(Profit)                AS profit,
           COUNT(DISTINCT `Order ID`) AS orders
    FROM Orders
    GROUP BY Market, Region
)
SELECT Market,
       Region,
       ROUND(sales, 2)                                        AS sales,
       ROUND(profit, 2)                                       AS profit,
       orders,
       ROUND(profit / sales * 100, 2)                         AS profit_margin_pct,
       DENSE_RANK() OVER (ORDER BY sales DESC)                AS sales_rank,
       DENSE_RANK() OVER (ORDER BY profit / sales DESC)       AS margin_rank
FROM region_perf
ORDER BY sales_rank;

-- ---------------------------------------------------------------------
-- @output: segment_performance
-- ---------------------------------------------------------------------
SELECT Segment,
       ROUND(SUM(Sales), 2)                              AS sales,
       ROUND(SUM(Profit), 2)                             AS profit,
       COUNT(DISTINCT `Order ID`)                        AS orders,
       COUNT(DISTINCT `Customer Name`)                   AS customers,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)          AS profit_margin_pct,
       ROUND(SUM(Sales) / COUNT(DISTINCT `Order ID`), 2) AS avg_order_value
FROM Orders
GROUP BY Segment
ORDER BY sales DESC;

-- ---------------------------------------------------------------------
-- @output: top_products_by_sales
-- Product Name is the real product; Product ID is not unique per name.
-- ---------------------------------------------------------------------
WITH product_perf AS (
    SELECT `Product Name` AS product_name, Category, `Sub-Category` AS sub_category,
           SUM(Sales) AS sales, SUM(Profit) AS profit, SUM(Quantity) AS quantity,
           COUNT(DISTINCT `Order ID`) AS orders
    FROM Orders
    GROUP BY `Product Name`, Category, `Sub-Category`
)
SELECT sales_rank, product_name, Category, sub_category,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit, quantity, orders,
       ROUND(profit / sales * 100, 2) AS profit_margin_pct
FROM (
    SELECT *, ROW_NUMBER() OVER (ORDER BY sales DESC) AS sales_rank
    FROM product_perf
) ranked
WHERE sales_rank <= 10
ORDER BY sales_rank;

-- ---------------------------------------------------------------------
-- @output: bottom_products_by_profit
-- Loss-making products (HAVING) ranked by loss.
-- ---------------------------------------------------------------------
WITH product_perf AS (
    SELECT `Product Name` AS product_name, Category, `Sub-Category` AS sub_category,
           SUM(Sales) AS sales, SUM(Profit) AS profit, SUM(Quantity) AS quantity,
           COUNT(DISTINCT `Order ID`) AS orders, AVG(Discount) AS avg_discount
    FROM Orders
    GROUP BY `Product Name`, Category, `Sub-Category`
    HAVING SUM(Profit) < 0
)
SELECT loss_rank, product_name, Category, sub_category,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit, quantity, orders,
       ROUND(avg_discount * 100, 2) AS avg_discount_pct,
       ROUND(profit / sales * 100, 2) AS profit_margin_pct
FROM (
    SELECT *, ROW_NUMBER() OVER (ORDER BY profit ASC) AS loss_rank
    FROM product_perf
) ranked
WHERE loss_rank <= 10
ORDER BY loss_rank;

-- ---------------------------------------------------------------------
-- @output: top_customers
-- Customers ranked by sales (DENSE_RANK) across all their markets.
-- ---------------------------------------------------------------------
WITH customer_perf AS (
    SELECT `Customer Name` AS customer_name,
           SUM(Sales) AS sales, SUM(Profit) AS profit,
           COUNT(DISTINCT `Order ID`) AS orders,
           COUNT(DISTINCT Market) AS markets
    FROM Orders
    GROUP BY `Customer Name`
)
SELECT customer_rank, customer_name,
       ROUND(sales, 2) AS sales, ROUND(profit, 2) AS profit, orders, markets,
       ROUND(profit / sales * 100, 2) AS profit_margin_pct
FROM (
    SELECT *, DENSE_RANK() OVER (ORDER BY sales DESC) AS customer_rank
    FROM customer_perf
) ranked
WHERE customer_rank <= 20
ORDER BY customer_rank;

-- ---------------------------------------------------------------------
-- @output: discount_analysis
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN Discount = 0    THEN '0%'
        WHEN Discount <= 0.10 THEN '0-10%'
        WHEN Discount <= 0.20 THEN '10-20%'
        WHEN Discount <= 0.30 THEN '20-30%'
        WHEN Discount <= 0.50 THEN '30-50%'
        ELSE '50%+'
    END                                           AS discount_band,
    MIN(Discount)                                 AS band_min_discount,
    COUNT(*)                                      AS order_lines,
    ROUND(SUM(Sales), 2)                          AS sales,
    ROUND(SUM(Profit), 2)                         AS profit,
    ROUND(SUM(Profit) / SUM(Sales) * 100, 2)      AS profit_margin_pct,
    ROUND(SUM(Sales) / SUM(SUM(Sales)) OVER () * 100, 2) AS sales_share_pct
FROM Orders
GROUP BY discount_band
ORDER BY band_min_discount;

-- ---------------------------------------------------------------------
-- @output: discount_threshold_summary
-- Profit above vs at-or-below a 20% discount.
-- ---------------------------------------------------------------------
SELECT CASE WHEN Discount > 0.20 THEN 'Discount > 20%' ELSE 'Discount <= 20%' END AS discount_group,
       COUNT(*)                                  AS order_lines,
       ROUND(SUM(Sales), 2)                      AS sales,
       ROUND(SUM(Profit), 2)                     AS profit,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)  AS profit_margin_pct
FROM Orders
GROUP BY discount_group
ORDER BY discount_group;

-- ---------------------------------------------------------------------
-- @output: discount_profit_correlation
-- Pearson correlation computed in SQL (line-level Discount vs Profit).
-- ---------------------------------------------------------------------
SELECT ROUND(
         (COUNT(*) * SUM(Discount * Profit) - SUM(Discount) * SUM(Profit))
         / ( SQRT(COUNT(*) * SUM(Discount * Discount) - POW(SUM(Discount), 2))
           * SQRT(COUNT(*) * SUM(Profit * Profit)     - POW(SUM(Profit), 2)) ),
       4) AS pearson_r_discount_profit
FROM Orders;

-- ---------------------------------------------------------------------
-- @output: tables_discount_breakdown
-- Why is Tables loss-making? Profit by discount band for Tables only.
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN Discount = 0    THEN '0%'
        WHEN Discount <= 0.20 THEN '0-20%'
        WHEN Discount <= 0.40 THEN '20-40%'
        ELSE '40%+'
    END                                       AS discount_band,
    MIN(Discount)                             AS band_min_discount,
    COUNT(*)                                  AS order_lines,
    ROUND(SUM(Sales), 2)                      AS sales,
    ROUND(SUM(Profit), 2)                     AS profit,
    ROUND(SUM(Profit) / SUM(Sales) * 100, 2)  AS profit_margin_pct
FROM Orders
WHERE `Sub-Category` = 'Tables'
GROUP BY discount_band
ORDER BY band_min_discount;

-- ---------------------------------------------------------------------
-- @output: return_rate_by_market
-- LEFT JOIN on (Order ID, Market); orders counted DISTINCT so an order
-- with several lines counts once.
-- ---------------------------------------------------------------------
SELECT o.Market,
       COUNT(DISTINCT o.`Order ID`)                                       AS orders,
       COUNT(DISTINCT CASE WHEN r.`Order ID` IS NOT NULL THEN o.`Order ID` END) AS returned_orders,
       ROUND(COUNT(DISTINCT CASE WHEN r.`Order ID` IS NOT NULL THEN o.`Order ID` END)
             / COUNT(DISTINCT o.`Order ID`) * 100, 2)                     AS return_rate_pct,
       ROUND(SUM(CASE WHEN r.`Order ID` IS NOT NULL THEN o.Sales ELSE 0 END), 2) AS returned_sales
FROM Orders o
LEFT JOIN Returns r
       ON r.`Order ID` = o.`Order ID`
      AND r.Market     = o.Market
GROUP BY o.Market
ORDER BY return_rate_pct DESC, o.Market;

-- ---------------------------------------------------------------------
-- @output: return_rate_by_category
-- Restricted to the four markets that have return records.
-- ---------------------------------------------------------------------
WITH covered AS (
    SELECT DISTINCT Market FROM Returns
)
SELECT o.Category,
       COUNT(DISTINCT o.`Order ID`)                                              AS orders,
       COUNT(DISTINCT CASE WHEN r.`Order ID` IS NOT NULL THEN o.`Order ID` END)  AS returned_orders,
       ROUND(COUNT(DISTINCT CASE WHEN r.`Order ID` IS NOT NULL THEN o.`Order ID` END)
             / COUNT(DISTINCT o.`Order ID`) * 100, 2)                            AS return_rate_pct
FROM Orders o
JOIN covered c ON c.Market = o.Market
LEFT JOIN Returns r
       ON r.`Order ID` = o.`Order ID`
      AND r.Market     = o.Market
GROUP BY o.Category
ORDER BY return_rate_pct DESC;

-- ---------------------------------------------------------------------
-- @output: ship_mode_analysis
-- ---------------------------------------------------------------------
SELECT `Ship Mode`                                          AS ship_mode,
       COUNT(DISTINCT `Order ID`)                           AS orders,
       ROUND(SUM(Sales), 2)                                 AS sales,
       ROUND(SUM(Profit), 2)                                AS profit,
       ROUND(SUM(Profit) / SUM(Sales) * 100, 2)             AS profit_margin_pct,
       ROUND(AVG(DATEDIFF(`Ship Date`, `Order Date`)), 2)   AS avg_ship_days,
       ROUND(SUM(`Shipping Cost`) / SUM(Sales) * 100, 2)    AS shipping_cost_pct_of_sales
FROM Orders
GROUP BY `Ship Mode`
ORDER BY avg_ship_days;

-- ---------------------------------------------------------------------
-- @output: yearly_category_rank
-- RANK partitioned by year + LAG partitioned by category.
-- ---------------------------------------------------------------------
WITH yc AS (
    SELECT YEAR(`Order Date`) AS sales_year, Category,
           SUM(Sales) AS sales, SUM(Profit) AS profit
    FROM Orders
    GROUP BY YEAR(`Order Date`), Category
)
SELECT sales_year, Category,
       ROUND(sales, 2)                                                 AS sales,
       ROUND(profit, 2)                                                AS profit,
       RANK() OVER (PARTITION BY sales_year ORDER BY sales DESC)       AS category_rank,
       ROUND((sales - LAG(sales) OVER (PARTITION BY Category ORDER BY sales_year))
             / LAG(sales) OVER (PARTITION BY Category ORDER BY sales_year) * 100, 2)
                                                                       AS yoy_sales_growth_pct
FROM yc
ORDER BY sales_year, category_rank;

-- ---------------------------------------------------------------------
-- @output: manager_performance
-- Orders JOIN People (region manager) with the markets each manager covers.
-- ---------------------------------------------------------------------
SELECT p.Person                                                 AS regional_manager,
       o.Region,
       GROUP_CONCAT(DISTINCT o.Market ORDER BY o.Market SEPARATOR ', ') AS markets,
       ROUND(SUM(o.Sales), 2)                                   AS sales,
       ROUND(SUM(o.Profit), 2)                                  AS profit,
       ROUND(SUM(o.Profit) / SUM(o.Sales) * 100, 2)             AS profit_margin_pct,
       RANK() OVER (ORDER BY SUM(o.Profit) DESC)                AS profit_rank
FROM Orders o
LEFT JOIN People p ON p.Region = o.Region
GROUP BY p.Person, o.Region
ORDER BY sales DESC;
