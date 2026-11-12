-- =====================================================================
-- GLOBAL SUPERSTORE — 02: LOAD + CLEAN
-- Run from the project root with local infile enabled, e.g.
--   mysql --local-infile=1 -u root global_superstore < sql/02_load_and_clean.sql
-- (server needs: SET GLOBAL local_infile = 1;)
-- =====================================================================

USE global_superstore;

-- ---------------------------------------------------------------------
-- Orders
--   * Postal Code arrives as a float string ('10024.0') -> strip '.0'
--   * US ZIP codes lost their leading zero in the float  -> LPAD to 5
--   * Blank postal codes (non-US orders)                 -> NULL
-- ---------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'data/orders_cleaned.csv'
INTO TABLE Orders
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY ''
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`Row ID`, `Order ID`, `Order Date`, `Ship Date`, `Ship Mode`, `Customer ID`,
 `Customer Name`, `Segment`, `City`, `State`, `Country`, @postal_code, `Market`,
 `Region`, `Product ID`, `Category`, `Sub-Category`, `Product Name`, `Sales`,
 `Quantity`, `Discount`, `Profit`, `Shipping Cost`, `Order Priority`,
 `Year`, `Month`, `Ship Days`, `Returned`)
SET `Postal Code` = CASE
        WHEN @postal_code = '' THEN NULL
        WHEN `Country` = 'United States' THEN LPAD(SUBSTRING_INDEX(@postal_code, '.', 1), 5, '0')
        ELSE SUBSTRING_INDEX(@postal_code, '.', 1)
    END;

-- ---------------------------------------------------------------------
-- Returns
--   * Source labels the US market 'United States'; Orders uses 'US'.
--     Normalise so Returns can be joined on (Order ID, Market).
-- ---------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'data/returns.csv'
INTO TABLE Returns
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY ''
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`Returned`, `Order ID`, @market)
SET `Market` = CASE WHEN @market = 'United States' THEN 'US' ELSE @market END;

-- ---------------------------------------------------------------------
-- People
--   * Source spells the EMEA region 'AMEA'; Orders uses 'EMEA'.
--     Without this fix the EMEA manager join returns NULL.
-- ---------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'data/people.csv'
INTO TABLE People
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY ''
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(`Person`, @region)
SET `Region` = CASE WHEN @region = 'AMEA' THEN 'EMEA' ELSE @region END;

-- Quick load check
SELECT 'Orders' AS table_name, COUNT(*) AS row_count FROM Orders
UNION ALL SELECT 'Returns', COUNT(*) FROM Returns
UNION ALL SELECT 'People',  COUNT(*) FROM People;
