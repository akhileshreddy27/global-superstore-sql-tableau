#!/usr/bin/env python3
"""Run the Global Superstore SQL pipeline against MySQL 8 and export every result.

Steps
  1. sql/01_schema.sql         create database + tables
  2. sql/02_load_and_clean.sql LOAD DATA LOCAL INFILE + cleaning fixes
  3. sql/03_analysis.sql       each "-- @output: <name>" query -> outputs/<name>.csv
  4. sql/04_tableau_view.sql   enriched view -> tableau/superstore_tableau_source.csv

Uses the mysql command-line client, so no Python MySQL driver is needed.

Connection settings (environment variables, all optional):
  MYSQL_BIN       path to the mysql client (default: Homebrew mysql@8.4, else `mysql`)
  MYSQL_HOST      default 127.0.0.1
  MYSQL_PORT      default 3306
  MYSQL_USER      default root
  MYSQL_PWD       password (read by the mysql client itself; default none)

Usage (from anywhere):
  python3 scripts/run_sql.py
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
TABLEAU_DIR = ROOT / "tableau"
DATABASE = "global_superstore"

# Results that belong somewhere other than outputs/<name>.csv
SPECIAL_DESTINATIONS = {
    "tableau_source": TABLEAU_DIR / "superstore_tableau_source.csv",
}

MARKER = re.compile(r"^--\s*@output:\s*(\w+)\s*$", re.MULTILINE)


def mysql_bin() -> str:
    if os.environ.get("MYSQL_BIN"):
        return os.environ["MYSQL_BIN"]
    brew = Path("/opt/homebrew/opt/mysql@8.4/bin/mysql")
    if brew.exists():
        return str(brew)
    found = shutil.which("mysql")
    if not found:
        sys.exit("mysql client not found; set MYSQL_BIN")
    return found


def base_cmd(database: str | None = None, local_infile: bool = False) -> list[str]:
    cmd = [
        mysql_bin(),
        f"--host={os.environ.get('MYSQL_HOST', '127.0.0.1')}",
        f"--port={os.environ.get('MYSQL_PORT', '3306')}",
        f"--user={os.environ.get('MYSQL_USER', 'root')}",
        "--default-character-set=utf8mb4",
    ]
    if local_infile:
        cmd.append("--local-infile=1")
    if database:
        cmd.append(database)
    return cmd


def run(sql: str, *, database: str | None = DATABASE, local_infile: bool = False,
        batch: bool = False) -> str:
    cmd = base_cmd(database, local_infile)
    if batch:
        cmd += ["--batch", "--raw"]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(f"MySQL error:\n{proc.stderr.strip()}\n--- while running ---\n{sql[:800]}")
    return proc.stdout


def split_outputs(sql_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (setup_sql, [(output_name, query_sql), ...])."""
    parts = MARKER.split(sql_text)
    setup = parts[0]
    queries = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
    return setup, queries


def save_result(name: str, tsv: str) -> Path:
    dest = SPECIAL_DESTINATIONS.get(name, OUTPUT_DIR / f"{name}.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)
    reader = csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    rows = [["" if v == "NULL" else v for v in row] for row in reader]
    with dest.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"  {dest.relative_to(ROOT)}  ({len(rows) - 1} rows)")
    return dest


def run_output_file(path: Path) -> None:
    setup, queries = split_outputs(path.read_text())
    if setup.strip():
        run(setup)
    for name, query in queries:
        save_result(name, run(query, batch=True))


def main() -> None:
    version = run("SELECT VERSION();", database=None, batch=True).splitlines()[1]
    if int(version.split(".")[0]) < 8:
        sys.exit(f"MySQL {version} found; CTEs and window functions need MySQL 8.0+")
    print(f"MySQL {version}")

    print("01 schema")
    run((SQL_DIR / "01_schema.sql").read_text(), database=None)

    print("02 load + clean")
    print(run((SQL_DIR / "02_load_and_clean.sql").read_text(), local_infile=True, batch=True))

    print("03 analysis")
    run_output_file(SQL_DIR / "03_analysis.sql")

    print("04 tableau view")
    run_output_file(SQL_DIR / "04_tableau_view.sql")


if __name__ == "__main__":
    main()
