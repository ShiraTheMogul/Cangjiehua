#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote
from html.parser import HTMLParser

import requests


# -----------------------------
# Configuration
# -----------------------------

PROMPT_MAP = {
    "a": "日", "b": "月", "c": "金", "d": "木", "e": "水", "f": "火", "g": "土",
    "h": "竹", "i": "戈", "j": "十", "k": "大", "l": "中", "m": "一", "n": "弓",
    "o": "人", "p": "心", "q": "手", "r": "口", "s": "尸", "t": "廿", "u": "山",
    "v": "女", "w": "田", "x": "難", "y": "卜", "z": "重",
}

HAN_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF"
    r"\U00020000-\U0002A6DF\U0002A700-\U0002B73F"
    r"\U0002B740-\U0002B81D\U0002B820-\U0002CEAD"
    r"\U0002CEB0-\U0002EBE0\U00031350-\U000323AF"
    r"\U0002EBF0-\U0002EE5D\U000323B0-\U00033479"
    r"\U0002F800-\U0002FA1F]"
)

# -----------------------------
# Cache
# -----------------------------

def init_cache(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS unihan (
               char TEXT PRIMARY KEY,
               kcangjie TEXT
           )"""
    )
    conn.commit()
    return conn


def cache_get(conn: sqlite3.Connection, ch: str) -> str | None:
    row = conn.execute("SELECT kcangjie FROM unihan WHERE char=?", (ch,)).fetchone()
    return row[0] if row else None


def cache_put(conn: sqlite3.Connection, ch: str, kc: str):
    conn.execute(
        "INSERT OR REPLACE INTO unihan(char, kcangjie) VALUES (?, ?)",
        (ch, kc),
    )
    conn.commit()


# -----------------------------
# Unihan lookup
# -----------------------------

class UnihanTableParser(HTMLParser):
    """
    Parses the Unihan HTML page and extracts a mapping of data-type -> value
    by reading table rows (<tr>) of two cells (<td> ... </td><td> ... </td>).

    This is robust to:
    - kCangjie wrapped in <a>
    - values wrapped in <code>
    - whitespace/newlines between tags
    """
    def __init__(self):
        super().__init__()
        self.in_tr = False
        self.in_td = False
        self.current_cell = []
        self.row_cells = []
        self.data = {}

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "tr":
            self.in_tr = True
            self.row_cells = []
        elif t == "td" and self.in_tr:
            self.in_td = True
            self.current_cell = []

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "td" and self.in_tr and self.in_td:
            self.in_td = False
            cell_text = "".join(self.current_cell).strip()
            # squash internal whitespace
            cell_text = " ".join(cell_text.split())
            self.row_cells.append(cell_text)
        elif t == "tr" and self.in_tr:
            self.in_tr = False
            if len(self.row_cells) >= 2:
                key = self.row_cells[0]
                val = self.row_cells[1]
                if key and val and key not in self.data:
                    self.data[key] = val

    def handle_data(self, data):
        if self.in_tr and self.in_td:
            self.current_cell.append(data)

def fetch_unihan_field(ch: str, field: str, session: requests.Session) -> str:
    url = "https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=" + quote(ch)
    r = session.get(url, timeout=20, headers={"User-Agent": "unihan-cangjie-tool/1.1"})
    r.raise_for_status()

    p = UnihanTableParser()
    p.feed(r.text)
    return p.data.get(field, "")

def get_kcangjie(ch, conn, session, sleep_s, verbose, refresh_empty=False):
    cached = cache_get(conn, ch)
    if cached is not None and not (refresh_empty and cached == ""):
        if verbose:
            print(f"  [cache] {ch} → {cached}")
        return cached

    time.sleep(sleep_s)
    if verbose:
        print(f"  [fetch] {ch}")
    try:
        kc = fetch_unihan_field(ch, "kCangjie", session)
    except Exception as e:
        if verbose:
            print(f"  [error] {ch}: {e}")
        kc = ""

    cache_put(conn, ch, kc)
    return kc

def render(code: str, mode: str) -> str:
    if not code:
        return ""
    if mode == "latin":
        return code.lower()
    prompts = "".join(PROMPT_MAP.get(c.lower(), c) for c in code)
    if mode == "prompts":
        return prompts
    return f"{code.lower()} ({prompts})"


# -----------------------------
# Core annotation
# -----------------------------

def annotate_text(text: str, conn, session, sleep_s, mode, verbose) -> str:
    out = []
    for ch in HAN_RE.findall(text or ""):
        kc = get_kcangjie(ch, conn, session, sleep_s, verbose)
        if kc:
            out.append(render(kc, mode))
    return " ".join(out)


# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Unified Unihan kCangjie annotator")
    ap.add_argument("--mode", choices=["paste", "csv"], required=True)

    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)

    ap.add_argument("--source-col", help="CSV mode only: source column name")
    ap.add_argument("--out-col", default="kCangjie")

    ap.add_argument("--render", choices=["latin", "prompts", "both"], default="prompts")
    ap.add_argument("--stop-after", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--cache-db", default="unihan_cache.sqlite", type=Path)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--refresh-empty", action="store_true",
               help="Re-fetch entries that are cached as empty (fixes earlier bad cache).")

    args = ap.parse_args()

    conn = init_cache(args.cache_db)
    session = requests.Session()

    empty_run = 0

    if args.mode == "paste":
        with args.input.open("r", encoding="utf-8") as fin, \
             args.output.open("w", encoding="utf-8") as fout:

            for line in fin:
                raw = line.rstrip("\n")

                if not raw.strip():
                    empty_run += 1
                    fout.write("\n")
                    if args.verbose:
                        print(f"[empty {empty_run}/{args.stop_after}]")
                    if empty_run >= args.stop_after:
                        break
                    continue

                empty_run = 0
                fout.write(
                    annotate_text(raw, conn, session, args.sleep,
                                  args.render, args.verbose) + "\n"
                )

    else:  # CSV mode
        with args.input.open("r", encoding="utf-8-sig", newline="") as fin:
            reader = csv.DictReader(fin)
            if args.source_col not in reader.fieldnames:
                raise SystemExit(f"Missing column {args.source_col}")

            fieldnames = list(reader.fieldnames)
            if args.out_col not in fieldnames:
                fieldnames.append(args.out_col)

            with args.output.open("w", encoding="utf-8-sig", newline="") as fout:
                writer = csv.DictWriter(fout, fieldnames=fieldnames)
                writer.writeheader()

                for i, row in enumerate(reader, 1):
                    cell = (row.get(args.source_col) or "").strip()
                    if not cell:
                        empty_run += 1
                        row[args.out_col] = ""
                        writer.writerow(row)
                        if args.verbose:
                            print(f"[row {i}] empty {empty_run}/{args.stop_after}")
                        if empty_run >= args.stop_after:
                            break
                        continue

                    empty_run = 0
                    if args.verbose:
                        print(f"[row {i}] {cell}")
                    row[args.out_col] = annotate_text(
                        cell, conn, session, args.sleep,
                        args.render, args.verbose
                    )
                    writer.writerow(row)

    conn.close()


if __name__ == "__main__":
    main()
