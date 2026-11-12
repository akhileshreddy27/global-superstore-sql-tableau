#!/usr/bin/env python3
"""Build the Excel workbook and PNG charts from the MySQL result tables.

Reads only outputs/*.csv (written by scripts/run_sql.py), so every number in
the workbook and charts comes from the SQL queries.

Usage:
  python3 scripts/build_reports.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"

# Palette (validated default categorical slots + neutral inks)
BLUE = "#2a78d6"      # primary series / positive
ORANGE = "#eb6834"    # negative / loss
GREY = "#8a8985"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / f"{name}.csv", keep_default_na=False, na_values=[""])


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def money(v: float, _pos=None) -> str:
    a = abs(v)
    if a >= 1e6:
        s = f"${a / 1e6:.1f}M"
    elif a >= 1e3:
        s = f"${a / 1e3:.0f}K"
    else:
        s = f"${a:.0f}"
    return f"-{s}" if v < 0 else s


def style_axes(ax, title: str, subtitle: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=10, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=INK, pad=24)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=10, color=INK_2)


def new_fig(w=10, h=5.5):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(CHARTS / f"{name}.png", facecolor=SURFACE)
    plt.close(fig)
    print(f"  charts/{name}.png")


def chart_yearly() -> None:
    df = read("yearly_performance")
    fig, ax = new_fig(9, 5)
    bars = ax.bar(df.sales_year.astype(str), df.sales, color=BLUE, width=0.55)
    for b, s, g in zip(bars, df.sales, df.yoy_sales_growth_pct):
        label = money(s) + ("" if pd.isna(g) else f"\n+{g + 1e-9:.1f}% YoY")  # 26.25 -> 26.3
        ax.text(b.get_x() + b.get_width() / 2, s, label, ha="center", va="bottom",
                fontsize=10, color=INK)
    ax.yaxis.set_major_formatter(FuncFormatter(money))
    ax.set_ylim(0, df.sales.max() * 1.22)
    total = read("yearly_performance").cumulative_growth_vs_2011_pct.iloc[-1]
    style_axes(ax, "Sales by year", f"Sales grew {total:.1f}% from 2011 to 2014")
    save(fig, "yearly_sales_growth")


def chart_monthly() -> None:
    df = read("monthly_performance")
    x = pd.to_datetime(df.month + "-01")
    fig, ax = new_fig(11, 5)
    ax.plot(x, df.sales, color=GREY, linewidth=1.2, label="Monthly sales")
    ax.plot(x, df.sales_3m_moving_avg, color=BLUE, linewidth=2.2, label="3-month moving average")
    ax.yaxis.set_major_formatter(FuncFormatter(money))
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=INK_2)
    style_axes(ax, "Monthly sales, 2011–2014", "Strong year-end seasonality; every year beats the last")
    save(fig, "monthly_sales_trend")


def chart_category() -> None:
    df = read("category_performance").sort_values("sales")
    fig, ax = new_fig(9, 4)
    bars = ax.barh(df.Category, df.sales, color=BLUE, height=0.55)
    for b, s, m in zip(bars, df.sales, df.profit_margin_pct):
        ax.text(s, b.get_y() + b.get_height() / 2, f"  {money(s)}  ·  {m:.1f}% margin",
                va="center", fontsize=10, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(money))
    ax.set_xlim(0, df.sales.max() * 1.35)
    style_axes(ax, "Sales by category", "Technology leads in sales and margin; Furniture's margin is half the others'")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    save(fig, "category_sales")


def chart_subcategory() -> None:
    df = read("subcategory_performance").sort_values("profit")
    fig, ax = new_fig(10, 7)
    colors = [ORANGE if p < 0 else BLUE for p in df.profit]
    labels = df.sub_category + "  (" + df.Category + ")"
    ax.barh(labels, df.profit, color=colors, height=0.65)
    ax.axvline(0, color=INK_2, linewidth=0.8)
    for y, p in enumerate(df.profit):
        ax.text(p, y, f"  {money(p)}  " if p >= 0 else f"{money(p)}  ", va="center",
                ha="left" if p >= 0 else "right", fontsize=9, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(money))
    lo, hi = df.profit.min(), df.profit.max()
    ax.set_xlim(lo * 1.6, hi * 1.2)
    style_axes(ax, "Profit by sub-category", "Tables is the only sub-category that loses money")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    save(fig, "subcategory_profit")


def chart_discount() -> None:
    df = read("discount_analysis")
    fig, ax = new_fig(9, 5)
    colors = [ORANGE if m < 0 else BLUE for m in df.profit_margin_pct]
    bars = ax.bar(df.discount_band, df.profit_margin_pct, color=colors, width=0.6)
    ax.axhline(0, color=INK_2, linewidth=0.8)
    for b, m in zip(bars, df.profit_margin_pct):
        ax.text(b.get_x() + b.get_width() / 2, m, f"{m:.1f}%", ha="center",
                va="bottom" if m >= 0 else "top", fontsize=10, color=INK)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_ylim(df.profit_margin_pct.min() * 1.18, df.profit_margin_pct.max() * 1.6)
    ax.set_xlabel("Discount band", color=INK_2)
    r = read("discount_profit_correlation").iloc[0, 0]
    style_axes(ax, "Profit margin by discount band",
               f"Margins turn negative above a 20% discount (Discount–Profit r = {r:.2f})")
    save(fig, "discount_profit")


def chart_returns() -> None:
    df = read("return_rate_by_market").sort_values("return_rate_pct")
    fig, ax = new_fig(9, 4.5)
    tracked = df.returned_orders > 0
    ax.barh(df.Market, df.return_rate_pct, color=[BLUE if t else GRID for t in tracked], height=0.55)
    for y, (r, t) in enumerate(zip(df.return_rate_pct, tracked)):
        ax.text(r, y, f"  {r:.2f}%" if t else "  no return records", va="center",
                fontsize=10, color=INK if t else INK_2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlim(0, df.return_rate_pct.max() * 1.4)
    style_axes(ax, "Order return rate by market", "Returns are only recorded for four markets")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    save(fig, "return_rate_by_market")


def chart_regions() -> None:
    df = read("region_performance").sort_values("profit_margin_pct")
    labels = df.Market + " – " + df.Region
    fig, ax = new_fig(10, 7)
    ax.barh(labels, df.profit_margin_pct, color=BLUE, height=0.65)
    for y, m in enumerate(df.profit_margin_pct):
        ax.text(m, y, f"  {m:.1f}%", va="center", fontsize=9, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlim(0, df.profit_margin_pct.max() * 1.15)
    style_axes(ax, "Profit margin by market and region", "Canada and North Asia lead; Southeast Asia trails at 2%")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    save(fig, "region_margin")


# ---------------------------------------------------------------------------
# Excel workbook
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=16, color="1F3A5F")
THIN = Side(style="thin", color="D9D9D9")

SHEETS = [
    ("yearly_performance", "Yearly"),
    ("monthly_performance", "Monthly"),
    ("category_performance", "Category"),
    ("subcategory_performance", "Sub-Category"),
    ("top5_subcategory_share", "Top5 Share"),
    ("market_performance", "Market"),
    ("region_performance", "Region"),
    ("segment_performance", "Segment"),
    ("top_products_by_sales", "Top Products"),
    ("bottom_products_by_profit", "Loss Products"),
    ("top_customers", "Top Customers"),
    ("discount_analysis", "Discount Bands"),
    ("discount_threshold_summary", "Discount 20pct"),
    ("tables_discount_breakdown", "Tables Discounts"),
    ("return_rate_by_market", "Returns Market"),
    ("return_rate_by_category", "Returns Category"),
    ("ship_mode_analysis", "Ship Mode"),
    ("yearly_category_rank", "Year x Category"),
    ("manager_performance", "Managers"),
    ("data_quality_checks", "Data Quality"),
]

MONEY_COLS = {"sales", "profit", "total_sales", "total_profit", "top5_sales",
              "avg_order_value", "returned_sales", "ytd_sales", "sales_3m_moving_avg"}


def number_format(col: str) -> str | None:
    if col in MONEY_COLS:
        return '$#,##0;[Red]-$#,##0'
    if col.endswith("_pct"):
        return '0.00"%"'
    if col in {"orders", "quantity", "order_lines", "customers", "quantity_sold", "returned_orders"}:
        return "#,##0"
    return None


def write_table(ws, df: pd.DataFrame, start_row: int = 1) -> None:
    for c, col in enumerate(df.columns, 1):
        cell = ws.cell(row=start_row, column=c, value=col)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r, row in enumerate(df.itertuples(index=False), start_row + 1):
        for c, (col, val) in enumerate(zip(df.columns, row), 1):
            cell = ws.cell(row=r, column=c, value=None if pd.isna(val) else val)
            fmt = number_format(col)
            if fmt:
                cell.number_format = fmt
            cell.border = Border(bottom=THIN)
    for c, col in enumerate(df.columns, 1):
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2
        ws.column_dimensions[get_column_letter(c)].width = min(max(width, 10), 60)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(df.columns))}{start_row + len(df)}"


def build_dashboard_sheet(wb: Workbook, kpi: pd.Series) -> None:
    ws = wb["Dashboard"]
    ws["A1"] = "Global Superstore — Sales & Profitability Summary"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"Source: MySQL 8 (sql/03_analysis.sql) · {kpi.first_order_date} to "
                f"{kpi.last_order_date} · {int(kpi.order_lines):,} order lines")
    ws["A2"].font = Font(italic=True, color="595959")

    # Raw inputs, then KPIs that are live Excel formulas over those inputs.
    rows = [
        ("Total Sales", float(kpi.total_sales), '$#,##0'),
        ("Total Profit", float(kpi.total_profit), '$#,##0'),
        ("Orders", int(kpi.orders), "#,##0"),
        ("Returned Orders", int(kpi.returned_orders), "#,##0"),
        ("Customers", int(kpi.customers), "#,##0"),
        ("Products", int(kpi.products), "#,##0"),
        ("Quantity Sold", int(kpi.quantity_sold), "#,##0"),
        ("Profit Margin", "=B5/B4", "0.00%"),
        ("Average Order Value", "=B4/B6", '$#,##0.00'),
        ("Return Rate", "=B7/B6", "0.00%"),
        ("Sales Growth 2011→2014", "='Yearly'!B5/'Yearly'!B2-1", "0.0%"),
    ]
    ws["A3"], ws["B3"] = "KPI", "Value"
    for cell in (ws["A3"], ws["B3"]):
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for i, (label, value, fmt) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        v = ws.cell(row=i, column=2, value=value)
        v.number_format = fmt
        v.border = Border(bottom=THIN)
    ws["A16"] = "Profit Margin, AOV, Return Rate and Growth are Excel formulas over the SQL results."
    ws["A16"].font = Font(italic=True, color="595959")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 18

    def ref(sheet, col, n):
        return Reference(wb[sheet], min_col=col, min_row=1, max_row=n + 1)

    def cats(sheet, col, n):
        return Reference(wb[sheet], min_col=col, min_row=2, max_row=n + 1)

    yearly = BarChart()
    yearly.title, yearly.y_axis.title = "Sales by Year", "Sales ($)"
    yearly.add_data(ref("Yearly", 2, 4), titles_from_data=True)
    yearly.set_categories(cats("Yearly", 1, 4))
    yearly.height, yearly.width, yearly.legend = 7.5, 14, None
    ws.add_chart(yearly, "D3")

    monthly = LineChart()
    monthly.title, monthly.y_axis.title = "Monthly Sales", "Sales ($)"
    monthly.add_data(ref("Monthly", 2, 48), titles_from_data=True)
    monthly.add_data(ref("Monthly", 8, 48), titles_from_data=True)
    monthly.set_categories(cats("Monthly", 1, 48))
    monthly.height, monthly.width = 7.5, 20
    ws.add_chart(monthly, "M3")

    cat = BarChart()
    cat.type, cat.title = "bar", "Profit by Sub-Category"
    cat.add_data(ref("Sub-Category", 4, 17), titles_from_data=True)
    cat.set_categories(cats("Sub-Category", 2, 17))
    cat.height, cat.width, cat.legend = 10, 14, None
    ws.add_chart(cat, "D19")

    disc = BarChart()
    disc.title, disc.y_axis.title = "Profit Margin by Discount Band", "Margin (%)"
    disc.add_data(ref("Discount Bands", 6, 6), titles_from_data=True)
    disc.set_categories(cats("Discount Bands", 1, 6))
    disc.height, disc.width, disc.legend = 10, 20, None
    ws.add_chart(disc, "M19")


def build_workbook() -> None:
    kpi = read("kpi_summary").iloc[0]
    wb = Workbook()
    wb.active.title = "Dashboard"  # first tab; filled once the data sheets exist
    for name, title in SHEETS:
        write_table(wb.create_sheet(title), read(name))
    build_dashboard_sheet(wb, kpi)
    dest = OUT / "analysis_summary.xlsx"
    wb.save(dest)
    print(f"  {dest.relative_to(ROOT)}  ({len(wb.sheetnames)} sheets)")


def main() -> None:
    CHARTS.mkdir(exist_ok=True)
    print("charts")
    for fn in (chart_yearly, chart_monthly, chart_category, chart_subcategory,
               chart_discount, chart_returns, chart_regions):
        fn()
    print("excel")
    build_workbook()


if __name__ == "__main__":
    main()
