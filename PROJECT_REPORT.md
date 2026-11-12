# Global Superstore — Project Report

## 1. Executive summary

Global Superstore sold **$12.64M** with **$1.47M profit** (11.61% margin) across 25,035 orders between
January 2011 and December 2014. Sales grew **90.3%** over the period. Profit is held back by heavy
discounting: order lines discounted above 20% lost **$814.7K**, giving back 36% of the $2.28M profit
earned on every other line. All figures below come from MySQL 8.4 queries in `sql/03_analysis.sql`.

## 2. Data and preparation

| Table | Rows | Notes |
|---|---:|---|
| Orders | 51,290 | one row per order line, 28 columns (24 source + Year, Month, Ship Days, Returned) |
| Returns | 1,173 | 1,172 distinct orders (one Order ID is returned in two markets) |
| People | 13 | one manager per region |

Cleaning steps in `sql/02_load_and_clean.sql`:
- Postal codes converted from float text to proper strings, with US ZIP leading zeros restored. They're NULL outside the US (41,296 lines).
- Returns market `United States` renamed to `US`, and People region `AMEA` renamed to `EMEA`, so all joins match.
- Returns joined on **(Order ID, Market)**. 37 Order IDs exist in two markets. Joining on Order ID alone mislabels 7 lines, which is what the original `Returned` flag in the CSV did.

Data-quality results (`outputs/data_quality_checks.csv`): no orphaned returns, every region has a manager, no negative ship times. There are 9 line pairs identical except for Row ID, kept as in the source.

## 3. SQL analysis

22 queries in four files, covering:
- **KPIs and trends:** yearly performance with `LAG` and `FIRST_VALUE`, and monthly performance with same-month YoY (`LAG(…, 12)`), YTD running totals and a 3-month moving average.
- **Product mix:** category and sub-category share of total (`SUM(SUM()) OVER ()`), `RANK … PARTITION BY Category`, top-5 concentration (chained CTEs), top and loss-making products (`ROW_NUMBER`, `HAVING`).
- **Geography and customers:** market and region rankings (`DENSE_RANK`), manager performance (`JOIN People`, `GROUP_CONCAT`), top customers.
- **Discounts:** band analysis, a 20% threshold comparison, Pearson correlation computed in SQL, and a Tables drill-down.
- **Returns and operations:** return rate by market and category (`LEFT JOIN Returns`), ship-mode speed and shipping-cost ratio.

## 4. Results

### Yearly performance

| Year | Sales | Profit | Orders | Margin | YoY sales growth |
|---|---:|---:|---:|---:|---:|
| 2011 | $2,259,451 | $248,941 | 4,440 | 11.02% | — |
| 2012 | $2,677,439 | $307,415 | 5,343 | 11.48% | +18.50% |
| 2013 | $3,405,746 | $406,935 | 6,721 | 11.95% | +27.20% |
| 2014 | $4,299,866 | $504,166 | 8,531 | 11.73% | +26.25% |

### Category performance

| Category | Sales | Profit | Margin | Share of sales | Share of profit |
|---|---:|---:|---:|---:|---:|
| Technology | $4,744,557 | $663,779 | 13.99% | 37.53% | 45.23% |
| Furniture | $4,110,874 | $285,205 | 6.94% | 32.52% | 19.44% |
| Office Supplies | $3,787,070 | $518,474 | 13.69% | 29.96% | 35.33% |

### Discount impact

| Discount band | Sales | Profit | Margin |
|---|---:|---:|---:|
| 0% | $6,992,411 | $1,770,695 | 25.32% |
| 0–10% | $1,962,619 | $338,189 | 17.23% |
| 10–20% | $1,757,261 | $173,255 | 9.86% |
| 20–30% | $382,555 | –$21,156 | –5.53% |
| 30–50% | $1,176,031 | –$380,945 | –32.39% |
| 50%+ | $371,625 | –$412,582 | –111.02% |

Lines discounted at or below 20% earned a 21.30% margin. Lines above 20% lost 42.21%. Line-level correlation between Discount and Profit is r = –0.3165.

### Return rate (markets that record returns)

| Market | Orders | Returned | Rate |
|---|---:|---:|---:|
| EU | 4,593 | 284 | 6.18% |
| US | 5,009 | 296 | 5.91% |
| LATAM | 5,138 | 297 | 5.78% |
| APAC | 5,437 | 296 | 5.44% |

Africa, Canada and EMEA have no return records.

## 5. Deliverables

- **Excel** (`outputs/analysis_summary.xlsx`): a Dashboard sheet whose Profit Margin, AOV, Return Rate and growth are live Excel formulas over the SQL results, with four native Excel charts, plus 20 formatted, filterable result sheets.
- **Tableau** (`tableau/Global_Superstore_Dashboard.twbx`, with a Hyper extract): three interactive dashboards with KPI cards, trends, product profitability, discount impact, regional margin, returns and shipping, and click-to-filter actions. See `TABLEAU_DASHBOARD_GUIDE.md`.
- **Charts** (`charts/`): 7 PNGs for slides or the README.

## 6. Recommendations

1. Cap discounts at 20% and require approval above it. That is where margin turns negative.
2. Fix Tables pricing. It is profitable undiscounted (23.1% margin) and loses 76.7% above a 40% discount.
3. Review Southeast Asia (2.0% margin) and EMEA (5.5%) before investing in more volume there.
4. Prioritise high-margin Technology lines: Copiers (17.1%) and Accessories (17.3%).
5. Start recording returns in Africa, Canada and EMEA.

## 7. Limitations

- Returns are only recorded for four markets, so the global return rate (4.68%) understates reality.
- The dataset is a public teaching dataset. Profit figures are as given, not audited.
