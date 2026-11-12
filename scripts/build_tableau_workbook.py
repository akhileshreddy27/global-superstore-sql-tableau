#!/usr/bin/env python3
"""Generate the Tableau workbook tableau/Global_Superstore_Dashboard.twbx.

Steps:
  1. Load tableau/superstore_tableau_source.csv (the MySQL view v_orders_enriched
     exported by scripts/run_sql.py) into a Hyper extract with the official
     Tableau Hyper API -> tableau/Data/superstore_extract.hyper.
     Tableau Public only opens workbooks whose data sources are extracts.
  2. Write tableau/Global_Superstore_Dashboard.twb pointing at that extract.
  3. Package both into tableau/Global_Superstore_Dashboard.twbx (open this one).

The workbook contains three interactive dashboards:

  1. Executive Overview          KPI cards, monthly trend, yearly sales, market + category
  2. Product & Profitability     sub-category profit, sales-vs-profit scatter,
                                 discount-band margin, top 10 products
  3. Customers, Regions & Ops    market/region margin, segment, return rate, ship mode

Clicking a mark on the market / category / sub-category / segment charts
filters the rest of that dashboard (dashboard filter actions).

Requires: pip install tableauhyperapi

Usage:
  python3 scripts/build_tableau_workbook.py
"""
from __future__ import annotations

import csv
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parent.parent
TABLEAU_DIR = ROOT / "tableau"
SOURCE_CSV = TABLEAU_DIR / "superstore_tableau_source.csv"
OUT = TABLEAU_DIR / "Global_Superstore_Dashboard.twb"
TWBX = TABLEAU_DIR / "Global_Superstore_Dashboard.twbx"
HYPER_REL = "Data/superstore_extract.hyper"   # relative to the .twb / inside the .twbx
HYPER = TABLEAU_DIR / HYPER_REL

DS = "federated.superstore01"
DS_CAPTION = "Global Superstore (MySQL v_orders_enriched)"
CONN = "hyper.superstore01"
OBJECT_ID = "Orders Enriched"

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
TYPES = {
    "Row ID": "integer", "Quantity": "integer", "Ship Days": "integer",
    "Order Date": "date", "Ship Date": "date",
    "Sales": "real", "Discount": "real", "Profit": "real", "Shipping Cost": "real",
}
MEASURES = {"Sales", "Quantity", "Discount", "Profit", "Shipping Cost", "Ship Days"}

CURRENCY = 'c"$"#,##0;-"$"#,##0'
PCT = "p0.0%"

# name -> (caption, formula, format)
CALCS = {
    "Calculation_ProfitMargin": ("Profit Margin", "SUM([Profit]) / SUM([Sales])", PCT),
    "Calculation_AOV": ("Average Order Value", "SUM([Sales]) / COUNTD([Order ID])", CURRENCY),
    "Calculation_ReturnedOrder": ("Returned Order", "IF [Returned] = 'Yes' THEN [Order ID] END", None),
    "Calculation_ReturnRate": ("Return Rate",
                               "COUNTD(IF [Returned] = 'Yes' THEN [Order ID] END) / COUNTD([Order ID])",
                               PCT),
    "Calculation_Orders": ("Orders", "COUNTD([Order ID])", "n#,##0"),
    "Calculation_Customers": ("Customers", "COUNTD([Customer Name])", "n#,##0"),
}


def header() -> list[str]:
    with SOURCE_CSV.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def col_meta(name: str) -> tuple[str, str, str]:
    """(datatype, role, type) for a source column."""
    dt = TYPES.get(name, "string")
    if name in MEASURES:
        return dt, "measure", "quantitative"
    if dt == "date":
        return dt, "dimension", "ordinal"
    return dt, "dimension", "nominal"


# Tableau metadata codes for Hyper columns: (remote-type, default aggregation)
REMOTE = {"string": ("129", "Count"), "date": ("133", "Year"),
          "integer": ("20", "Sum"), "real": ("5", "Sum")}


def build_hyper(cols: list[str]) -> None:
    """Load the MySQL export into a Hyper extract (table "Extract"."Extract")."""
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, SqlType,
                                 TableDefinition, TableName, Telemetry, escape_string_literal)

    sql_types = {"string": SqlType.text(), "date": SqlType.date(),
                 "integer": SqlType.big_int(), "real": SqlType.double()}
    table = TableDefinition(TableName("Extract", "Extract"), [
        TableDefinition.Column(c, sql_types[col_meta(c)[0]]) for c in cols])
    HYPER.parent.mkdir(parents=True, exist_ok=True)
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(HYPER), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            rows = conn.execute_command(
                f"COPY {table.table_name} FROM {escape_string_literal(str(SOURCE_CSV))} "
                "WITH (format csv, header, NULL '')")
    print(f"  {HYPER.relative_to(ROOT)}  ({rows} rows)")


def metadata_records(cols: list[str]) -> str:
    recs = []
    for i, c in enumerate(cols):
        dt = col_meta(c)[0]
        rtype, agg = REMOTE[dt]
        recs.append(f"""          <metadata-record class='column'>
            <remote-name>{escape(c)}</remote-name>
            <remote-type>{rtype}</remote-type>
            <local-name>[{escape(c)}]</local-name>
            <parent-name>[Extract]</parent-name>
            <remote-alias>{escape(c)}</remote-alias>
            <ordinal>{i}</ordinal>
            <local-type>{dt}</local-type>
            <aggregation>{agg}</aggregation>
            <contains-null>true</contains-null>
            <_.fcp.ObjectModelEncapsulateLegacy.true...object-id>[{OBJECT_ID}]</_.fcp.ObjectModelEncapsulateLegacy.true...object-id>
          </metadata-record>""")
    return "\n".join(recs)


def datasource_xml(cols: list[str]) -> str:
    relation = (f"connection='{CONN}' name='Extract' table='[Extract].[Extract]' type='table'")
    fmt_cols = []
    for c, fmt in (("Sales", CURRENCY), ("Profit", CURRENCY), ("Shipping Cost", CURRENCY),
                   ("Discount", "p0%")):
        dt, role, typ = col_meta(c)
        fmt_cols.append(
            f"      <column datatype='{dt}' default-format={quoteattr(fmt)} name='[{c}]' "
            f"role='{role}' type='{typ}' />")
    calc_cols = []
    for name, (caption, formula, fmt) in CALCS.items():
        is_dim = fmt is None
        attrs = (f"caption={quoteattr(caption)} datatype='{'string' if is_dim else 'real'}' "
                 f"name='[{name}]' role='{'dimension' if is_dim else 'measure'}' "
                 f"type='{'nominal' if is_dim else 'quantitative'}'")
        if fmt:
            attrs += f" default-format={quoteattr(fmt)}"
        calc_cols.append(
            f"      <column {attrs}>\n"
            f"        <calculation class='tableau' formula={quoteattr(formula)} />\n"
            f"      </column>")
    return f"""  <datasources>
    <datasource caption={quoteattr(DS_CAPTION)} inline='true' name='{DS}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='Superstore Extract' name='{CONN}'>
            <connection authentication='auth-none' author-locale='en_US' class='hyper' dbname='{HYPER_REL}' default-settings='yes' port='' sslmode='' username='tableau_internal_user' />
          </named-connection>
        </named-connections>
        <_.fcp.ObjectModelEncapsulateLegacy.false...relation {relation} />
        <_.fcp.ObjectModelEncapsulateLegacy.true...relation {relation} />
        <metadata-records>
{metadata_records(cols)}
        </metadata-records>
      </connection>
      <aliases enabled='yes' />
{chr(10).join(fmt_cols)}
{chr(10).join(calc_cols)}
      <_.fcp.ObjectModelTableType.true...column caption='{OBJECT_ID}' datatype='table' name='[__tableau_internal_object_id__].[{OBJECT_ID}]' role='measure' type='quantitative' />
      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
      <_.fcp.ObjectModelEncapsulateLegacy.true...object-graph>
        <objects>
          <object caption='{OBJECT_ID}' id='{OBJECT_ID}'>
            <properties context=''>
              <relation {relation} />
            </properties>
          </object>
        </objects>
      </_.fcp.ObjectModelEncapsulateLegacy.true...object-graph>
    </datasource>
  </datasources>"""


# ---------------------------------------------------------------------------
# Field references
# ---------------------------------------------------------------------------
class F:
    """A field placed on a shelf: column + derivation -> column-instance."""

    DERIV = {  # derivation -> (prefix, suffix)
        "None": ("none", "nk"), "Sum": ("sum", "qk"), "Avg": ("avg", "qk"),
        "CountD": ("ctd", "qk"), "Year": ("yr", "ok"), "Month-Trunc": ("tmn", "qk"),
        "User": ("usr", "qk"),
    }

    def __init__(self, column: str, derivation: str):
        self.column, self.derivation = column, derivation

    @property
    def is_calc(self) -> bool:
        return self.column in CALCS

    @property
    def instance(self) -> str:
        p, s = self.DERIV[self.derivation]
        if self.derivation == "None" and self.is_calc:
            s = "nk"
        return f"[{p}:{self.column}:{s}]"

    @property
    def ref(self) -> str:
        return f"[{DS}].{self.instance}"

    def column_xml(self) -> str:
        if self.is_calc:
            caption, formula, fmt = CALCS[self.column]
            is_dim = fmt is None
            return (f"            <column caption={quoteattr(caption)} "
                    f"datatype='{'string' if is_dim else 'real'}' name='[{self.column}]' "
                    f"role='{'dimension' if is_dim else 'measure'}' "
                    f"type='{'nominal' if is_dim else 'quantitative'}'>\n"
                    f"              <calculation class='tableau' formula={quoteattr(formula)} />\n"
                    f"            </column>")
        dt, role, typ = col_meta(self.column)
        return (f"            <column datatype='{dt}' name='[{self.column}]' "
                f"role='{role}' type='{typ}' />")

    def instance_xml(self) -> str:
        p, s = self.DERIV[self.derivation]
        typ = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[s]
        if self.derivation == "None" and self.is_calc:
            typ = "nominal"
        return (f"            <column-instance column='[{self.column}]' derivation='{self.derivation}' "
                f"name='{self.instance}' pivot='key' type='{typ}' />")


def dim(c):    return F(c, "None")
def total(c):  return F(c, "Sum")
def avg(c):    return F(c, "Avg")
def calc(c):   return F(c, "User")
def year(c):   return F(c, "Year")
def month(c):  return F(c, "Month-Trunc")


# ---------------------------------------------------------------------------
# Worksheets
# ---------------------------------------------------------------------------
class Sheet:
    def __init__(self, name, mark, rows=(), cols=(), color=None, label=None,
                 detail=(), tooltip=(), sort=None, top_n=None, title=None):
        self.name, self.mark = name, mark
        self.rows, self.cols = list(rows), list(cols)
        self.color, self.label = color, label
        self.detail, self.tooltip = list(detail), list(tooltip)
        self.sort = sort          # (dimension F, measure F, 'ASC'|'DESC')
        self.top_n = top_n        # (dimension F, n, formula)
        self.title = title or name

    def fields(self) -> list[F]:
        out = self.rows + self.cols + self.detail + self.tooltip
        out += [f for f in (self.color, self.label) if f]
        if self.sort:
            out += [self.sort[0], self.sort[1]]
        if self.top_n:
            out.append(self.top_n[0])
        seen, uniq = set(), []
        for f in out:
            if f.instance not in seen:
                seen.add(f.instance)
                uniq.append(f)
        return uniq

    def xml(self) -> str:
        fields = self.fields()
        cols_xml, seen = [], set()
        for f in fields:
            if f.column not in seen:
                seen.add(f.column)
                cols_xml.append(f.column_xml())
        inst_xml = [f.instance_xml() for f in fields]

        filters = ""
        if self.top_n:
            f, n, formula = self.top_n
            filters = f"""          <filter class='categorical' column='{f.ref}'>
            <groupfilter count='{n}' end='top' function='end' units='records' user:ui-marker='end' user:ui-top-by-field='true'>
              <groupfilter direction='DESC' expression={quoteattr(formula)} function='order' user:ui-marker='order'>
                <groupfilter function='level-members' level='{f.instance}' user:ui-enumeration='all' user:ui-marker='enumerate' />
              </groupfilter>
            </groupfilter>
          </filter>
"""
        sort = ""
        if self.sort:
            d, m, direction = self.sort
            sort = (f"          <computed-sort column='{d.ref}' direction='{direction}' "
                    f"using='{m.ref}' />\n")

        enc = []
        if self.color:
            enc.append(f"              <color column='{self.color.ref}' />")
        if self.label:
            enc.append(f"              <text column='{self.label.ref}' />")
        for f in self.detail:
            enc.append(f"              <lod column='{f.ref}' />")
        for f in self.tooltip:
            enc.append(f"              <tooltip column='{f.ref}' />")
        encodings = ("            <encodings>\n" + "\n".join(enc) + "\n            </encodings>\n") if enc else ""

        pane_style = ""
        if self.label and self.mark != "Text":
            pane_style = """            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
              </style-rule>
            </style>
"""
        if self.mark == "Text":
            pane_style = """            <style>
              <style-rule element='mark'>
                <format attr='font-size' value='24' />
                <format attr='font-weight' value='bold' />
                <format attr='mark-labels-show' value='true' />
              </style-rule>
            </style>
"""

        def shelf(fs):
            return " / ".join(f.ref for f in fs) if fs else ""

        rows, cols = shelf(self.rows), shelf(self.cols)
        return f"""    <worksheet name={quoteattr(self.name)}>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontsize='12'>{escape(self.title)}</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption={quoteattr(DS_CAPTION)} name='{DS}' />
          </datasources>
          <datasource-dependencies datasource='{DS}'>
{chr(10).join(cols_xml)}
{chr(10).join(inst_xml)}
          </datasource-dependencies>
{filters}{sort}          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{self.mark}' />
{encodings}{pane_style}          </pane>
        </panes>
        <rows>{rows}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_URL, self.name)).upper()}}}' />
    </worksheet>"""


PM = calc("Calculation_ProfitMargin")
RR = calc("Calculation_ReturnRate")
ORDERS = calc("Calculation_Orders")
CUSTOMERS = calc("Calculation_Customers")
SALES, PROFIT = total("Sales"), total("Profit")

SHEETS = [
    # --- Dashboard 1: Executive Overview
    Sheet("KPI Sales", "Text", label=SALES, title="Total Sales"),
    Sheet("KPI Profit", "Text", label=PROFIT, title="Total Profit"),
    Sheet("KPI Margin", "Text", label=PM, title="Profit Margin"),
    Sheet("KPI Orders", "Text", label=ORDERS, title="Orders"),
    Sheet("KPI Return Rate", "Text", label=RR, title="Return Rate"),
    Sheet("Monthly Sales Trend", "Line", rows=[SALES], cols=[month("Order Date")],
          tooltip=[PROFIT, PM], title="Monthly Sales Trend"),
    Sheet("Sales by Year", "Bar", rows=[SALES], cols=[year("Order Date")], label=SALES,
          tooltip=[PROFIT, PM], title="Sales by Year"),
    Sheet("Sales by Market", "Bar", rows=[dim("Market")], cols=[SALES], color=PM, label=SALES,
          tooltip=[PROFIT, ORDERS], sort=(dim("Market"), SALES, "DESC"),
          title="Sales by Market (colour = profit margin) — click to filter"),
    Sheet("Sales by Category", "Bar", rows=[dim("Category")], cols=[SALES], label=PM,
          tooltip=[PROFIT], sort=(dim("Category"), SALES, "DESC"),
          title="Sales by Category (label = margin)"),

    # --- Dashboard 2: Product & Profitability
    Sheet("Profit by Sub-Category", "Bar", rows=[dim("Sub-Category")], cols=[PROFIT],
          color=PROFIT, label=PROFIT, tooltip=[SALES, PM],
          sort=(dim("Sub-Category"), PROFIT, "DESC"),
          title="Profit by Sub-Category — click to filter"),
    Sheet("Sales vs Profit", "Circle", rows=[PROFIT], cols=[SALES], color=dim("Category"),
          detail=[dim("Sub-Category")], tooltip=[PM],
          title="Sales vs Profit by Sub-Category"),
    Sheet("Margin by Discount Band", "Bar", rows=[PM], cols=[dim("Discount Band")],
          color=PM, label=PM, tooltip=[SALES, PROFIT],
          title="Profit Margin by Discount Band"),
    Sheet("Top 10 Products", "Bar", rows=[dim("Product Name")], cols=[SALES], color=PM,
          label=SALES, tooltip=[PROFIT], sort=(dim("Product Name"), SALES, "DESC"),
          top_n=(dim("Product Name"), 10, "SUM([Sales])"),
          title="Top 10 Products by Sales (colour = margin)"),

    # --- Dashboard 3: Customers, Regions & Operations
    Sheet("Margin by Market Region", "Bar", rows=[dim("Market Region")], cols=[PM],
          color=PM, label=PM, tooltip=[SALES, PROFIT, dim("Regional Manager")],
          sort=(dim("Market Region"), PM, "DESC"),
          title="Profit Margin by Market – Region"),
    Sheet("Segment Performance", "Bar", rows=[dim("Segment")], cols=[SALES], label=PM,
          tooltip=[PROFIT, CUSTOMERS], sort=(dim("Segment"), SALES, "DESC"),
          title="Sales by Segment (label = margin) — click to filter"),
    Sheet("Return Rate by Market", "Bar", rows=[dim("Market")], cols=[RR], label=RR,
          tooltip=[ORDERS, dim("Returns Tracked")], sort=(dim("Market"), RR, "DESC"),
          title="Return Rate by Market (only 4 markets track returns)"),
    Sheet("Ship Mode", "Bar", rows=[dim("Ship Mode")], cols=[avg("Ship Days")],
          label=avg("Ship Days"), tooltip=[ORDERS, PM],
          sort=(dim("Ship Mode"), avg("Ship Days"), "ASC"),
          title="Average Days to Ship by Ship Mode"),
]

# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------
W, H = 1400, 900  # pixel size; zones use a 0..100000 coordinate space


def z(x, y, w, h):
    """Convert pixel box to Tableau's 100000-unit zone coordinates."""
    return (round(x / W * 100000), round(y / H * 100000),
            round(w / W * 100000), round(h / H * 100000))


DASHBOARDS = [
    ("Executive Overview",
     "Global Superstore — Executive Overview (2011–2014)",
     [("KPI Sales", (0, 60, 280, 110)), ("KPI Profit", (280, 60, 280, 110)),
      ("KPI Margin", (560, 60, 280, 110)), ("KPI Orders", (840, 60, 280, 110)),
      ("KPI Return Rate", (1120, 60, 280, 110)),
      ("Monthly Sales Trend", (0, 170, 900, 350)), ("Sales by Year", (900, 170, 500, 350)),
      ("Sales by Market", (0, 520, 700, 380)), ("Sales by Category", (700, 520, 700, 380))],
     ["Sales by Market"]),
    ("Product & Profitability",
     "Product & Profitability — where margin is made and lost",
     [("Profit by Sub-Category", (0, 60, 600, 470)), ("Sales vs Profit", (600, 60, 800, 470)),
      ("Margin by Discount Band", (0, 530, 600, 370)), ("Top 10 Products", (600, 530, 800, 370))],
     ["Profit by Sub-Category"]),
    ("Customers, Regions & Operations",
     "Customers, Regions & Operations",
     [("Margin by Market Region", (0, 60, 700, 840)), ("Segment Performance", (700, 60, 700, 280)),
      ("Return Rate by Market", (700, 340, 700, 300)), ("Ship Mode", (700, 640, 700, 260))],
     ["Segment Performance"]),
]


def dashboard_xml(name, title, layout, _sources) -> str:
    zones, zid = [], 3
    for sheet, box in layout:
        x, y, w, h = z(*box)
        zones.append(f"          <zone h='{h}' id='{zid}' name={quoteattr(sheet)} w='{w}' x='{x}' y='{y}' />")
        zid += 1
    tx, ty, tw, th = z(0, 0, W, 60)
    return f"""    <dashboard name={quoteattr(name)}>
      <style />
      <size maxheight='{H}' maxwidth='{W}' minheight='{H}' minwidth='{W}' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='{th}' id='2' type-v2='text' w='{tw}' x='{tx}' y='{ty}'>
            <formatted-text>
              <run bold='true' fontsize='20'>{escape(title)}</run>
            </formatted-text>
          </zone>
{chr(10).join(zones)}
        </zone>
      </zones>
      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_URL, 'db-' + name)).upper()}}}' />
    </dashboard>"""


def actions_xml() -> str:
    out, i = [], 1
    for dash, _t, _layout, sources in DASHBOARDS:
        for src in sources:
            out.append(f"""    <action caption={quoteattr(f'Filter {dash} by {src}')} name='[Action{i}]'>
      <activation auto-clear='true' type='on-select' />
      <source dashboard={quoteattr(dash)} type='sheet' worksheet={quoteattr(src)} />
      <command command='tsc:tsl-filter'>
        <param name='special-fields' value='all' />
        <param name='target' value={quoteattr(dash)} />
      </command>
    </action>""")
            i += 1
    return "  <actions>\n" + "\n".join(out) + "\n  </actions>"


WORKSHEET_CARDS = """      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
        </edge>
      </cards>
"""


def windows_xml() -> str:
    # Tableau needs exactly one visible, maximized window: that is the active sheet
    # the workbook opens on. Worksheets used only inside dashboards are hidden.
    wins = []
    for i, d in enumerate(DASHBOARDS):
        maxed = " maximized='true'" if i == 0 else ""
        viewpoints = "\n".join(
            f"        <viewpoint name={quoteattr(s)}>\n          <zoom type='entire-view' />\n        </viewpoint>"
            for s, _box in d[2])
        wins.append(f"""    <window class='dashboard'{maxed} name={quoteattr(d[0])}>
      <viewpoints>
{viewpoints}
      </viewpoints>
      <active id='-1' />
      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_URL, 'win-' + d[0])).upper()}}}' />
    </window>""")
    hidden = " hidden='true'" if DASHBOARDS else ""
    for i, s in enumerate(SHEETS):
        maxed = " maximized='true'" if not DASHBOARDS and i == 0 else ""
        wins.append(f"""    <window class='worksheet'{hidden}{maxed} name={quoteattr(s.name)}>
{WORKSHEET_CARDS}      <simple-id uuid='{{{str(uuid.uuid5(uuid.NAMESPACE_URL, 'win-' + s.name)).upper()}}}' />
    </window>""")
    return "  <windows source-height='72'>\n" + "\n".join(wins) + "\n  </windows>"


# Feature manifest + explain-data block, as written by Tableau 2025.x. Tableau's
# loader rejects the file if the manifest promises features whose elements are missing.
MANIFEST = """  <document-format-change-manifest>
    <_.fcp.AccessibleZoneTabOrder.true...AccessibleZoneTabOrder />
    <_.fcp.AnimationOnByDefault.true...AnimationOnByDefault />
    <AutoCreateAndUpdateDSDPhoneLayouts />
    <_.fcp.ExplainData_AuthorControls.true...ExplainData_AuthorControls />
    <_.fcp.ExplainData_NullValueExplanation.true...ExplainData_NullValueExplanation />
    <MapboxVectorStylesAndLayers />
    <_.fcp.MarkAnimation.true...MarkAnimation />
    <_.fcp.ObjectModelEncapsulateLegacy.true...ObjectModelEncapsulateLegacy />
    <_.fcp.ObjectModelTableType.true...ObjectModelTableType />
    <_.fcp.SchemaViewerObjectModel.true...SchemaViewerObjectModel />
    <SetMembershipControl />
    <SheetIdentifierTracking />
    <SortTagCleanup />
    <VizInTooltipHideWorksheet />
    <WindowsPersistSimpleIdentifiers />
    <WorksheetBackgroundTransparency />
    <ZoneFriendlyName />
  </document-format-change-manifest>
"""

EXPLAIN_DATA = """  <_.fcp.ExplainData_AuthorControls.true...explain-data enabled-for-viewer='false' extreme-values-enabled-for-all='false'>
    <explanation-types>
      <explanation-type enabled='true' type='number-of-records' />
      <explanation-type enabled='true' type='average-of-records' />
      <explanation-type enabled='true' type='aggregated-dimensions' />
      <explanation-type enabled='true' type='distribution-of-records' />
      <explanation-type enabled='true' type='unvisualized-measures' />
      <explanation-type enabled='true' type='extreme-values' />
      <_.fcp.ExplainData_NullValueExplanation.true...explanation-type enabled='true' type='null-value' />
      <explanation-type enabled='true' type='tvd-single-value' />
      <explanation-type enabled='true' type='ad-single-value' />
    </explanation-types>
  </_.fcp.ExplainData_AuthorControls.true...explain-data>
"""


def main() -> None:
    build_hyper(header())
    xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='0.0.0 (0000.25.1204.2135)' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
{MANIFEST}  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
{datasource_xml(header())}
  <worksheets>
{chr(10).join(s.xml() for s in SHEETS)}
  </worksheets>
  <dashboards>
{chr(10).join(dashboard_xml(*d) for d in DASHBOARDS)}
  </dashboards>
{windows_xml()}
{EXPLAIN_DATA}</workbook>
"""
    # actions sit between <datasources> and <worksheets> in Tableau's schema
    xml = xml.replace("  <worksheets>", actions_xml() + "\n  <worksheets>", 1)
    OUT.write_text(xml, encoding="utf-8")
    print(f"  {OUT.relative_to(ROOT)}  ({len(SHEETS)} worksheets, {len(DASHBOARDS)} dashboards)")

    # Packaged workbook: the .twb at the root plus the extract under Data/
    with zipfile.ZipFile(TWBX, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(OUT, OUT.name)
        zf.write(HYPER, HYPER_REL)
    print(f"  {TWBX.relative_to(ROOT)}  (open this in Tableau Public)")


if __name__ == "__main__":
    main()
