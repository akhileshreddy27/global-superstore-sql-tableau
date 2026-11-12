-- =====================================================================
-- GLOBAL SUPERSTORE — 01: SCHEMA
-- Target: MySQL 8.0+ (CTEs and window functions require 8.0)
-- Run order: 01_schema.sql -> 02_load_and_clean.sql -> 03_analysis.sql -> 04_tableau_view.sql
-- =====================================================================

CREATE DATABASE IF NOT EXISTS global_superstore
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE global_superstore;

DROP VIEW  IF EXISTS v_orders_enriched;
DROP TABLE IF EXISTS Returns;
DROP TABLE IF EXISTS People;
DROP TABLE IF EXISTS Orders;

-- One row per order line (51,290 rows). Columns match data/orders_cleaned.csv exactly.
CREATE TABLE Orders (
    `Row ID`         INT            NOT NULL PRIMARY KEY,
    `Order ID`       VARCHAR(30)    NOT NULL,
    `Order Date`     DATE           NOT NULL,
    `Ship Date`      DATE           NOT NULL,
    `Ship Mode`      VARCHAR(30)    NOT NULL,
    `Customer ID`    VARCHAR(30)    NOT NULL,
    `Customer Name`  VARCHAR(150)   NOT NULL,
    `Segment`        VARCHAR(30)    NOT NULL,
    `City`           VARCHAR(100)   NOT NULL,
    `State`          VARCHAR(100)   NOT NULL,
    `Country`        VARCHAR(100)   NOT NULL,
    `Postal Code`    VARCHAR(10)    NULL,          -- only populated for US orders
    `Market`         VARCHAR(30)    NOT NULL,
    `Region`         VARCHAR(50)    NOT NULL,
    `Product ID`     VARCHAR(30)    NOT NULL,
    `Category`       VARCHAR(50)    NOT NULL,
    `Sub-Category`   VARCHAR(50)    NOT NULL,
    `Product Name`   VARCHAR(255)   NOT NULL,
    `Sales`          DECIMAL(20,6)  NOT NULL,
    `Quantity`       INT            NOT NULL,
    `Discount`       DECIMAL(8,4)   NOT NULL,
    `Profit`         DECIMAL(20,6)  NOT NULL,
    `Shipping Cost`  DECIMAL(20,6)  NOT NULL,
    `Order Priority` VARCHAR(30)    NOT NULL,
    -- derived during cleaning
    `Year`           SMALLINT       NOT NULL,
    `Month`          CHAR(7)        NOT NULL,      -- 'YYYY-MM'
    `Ship Days`      SMALLINT       NOT NULL,
    `Returned`       VARCHAR(3)     NOT NULL,      -- 'Yes' / 'No'
    INDEX idx_order_id      (`Order ID`),
    INDEX idx_order_date    (`Order Date`),
    INDEX idx_market_region (`Market`, `Region`),
    INDEX idx_product       (`Product ID`),
    INDEX idx_customer      (`Customer ID`)
);

-- One row per returned order. The same Order ID can exist in two markets,
-- so the natural key is (Order ID, Market).
CREATE TABLE Returns (
    `Returned` VARCHAR(10)  NOT NULL,
    `Order ID` VARCHAR(30)  NOT NULL,
    `Market`   VARCHAR(30)  NOT NULL,
    PRIMARY KEY (`Order ID`, `Market`)
);

-- Regional managers (13 regions).
CREATE TABLE People (
    `Person` VARCHAR(150) NOT NULL,
    `Region` VARCHAR(50)  NOT NULL PRIMARY KEY
);
