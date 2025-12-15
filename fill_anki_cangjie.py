#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional


HAN_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF"
    r"\U00020000-\U0002A6DF"
    r"\U0002A700-\U0002B73F"
    r"\U0002B740-\U0002B81D"
    r"\U0002B820-\U0002CEAD"
    r"\U0002CEB0-\U0002EBE0"
    r"\U00031350-\U000323AF"
    r"\U0002EBF0-\U0002EE5D"
    r"\U000323B0-\U00033479"
    r"\U0002F800-\U0002FA1F]"
)

PROMPT_MAP = {
    "a": "日", "b": "月", "c": "金", "d": "木", "e": "水", "f": "火", "g": "土", "h": "竹",
    "i": "戈", "j": "十", "k": "大", "l": "中", "m": "一", "n": "弓", "o": "人", "p": "心",
    "q": "手", "r": "口", "s": "尸", "t": "廿", "u": "山", "v": "女", "w": "田", "x": "難",
    "y": "卜", "z": "重",
}


def load_cangjie_table(path: Path) -> Dict[str, List[str]]:
    """SCIM/ibus-table format: code<TAB>char<TAB>freq"""
    mapping: Dict[str, List[str]] = {}
    in_table = False
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line == "BEGIN_TABLE":
                in_table = True
                continue
            if line == "END_TABLE":
                break
            if not in_table or not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue
            code = parts[0].strip().lower()
            ch = parts[1].strip()
            if len(ch) != 1 or not code:
                continue

            lst = mapping.setdefault(ch, [])
            if code not in lst:
                lst.append(code)
    return mapping


def code_to_prompts(code: str) -> str:
    return "".join(PROMPT_MAP.get(c, c) for c in code)


def format_codes(codes: List[str], output: str) -> str:
    if output == "prompts":
        return "/".join(code_to_prompts(c) for c in codes)
    return "/".join(codes)


def cangjie_for_text(text: str, table: Dict[str, List[str]], output: str) -> str:
    out: List[str] = []
    for han in HAN_RE.findall(text or ""):
        codes = table.get(han)
        if codes:
            out.append(format_codes(codes, output=output))
    return " ".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill existing Cangjie fields in an Anki TXT export.")
    ap.add_argument("--in-txt", required=True, type=Path)
    ap.add_argument("--out-txt", required=True, type=Path)

    # NEW: 1-based column selection (so “column 4” means 4)
    ap.add_argument("--source-col", required=True, type=int,
                    help="1-based column number to convert (e.g. 4 for your Hanzi column)")

    ap.add_argument("--cj3-col", type=int, help="1-based column number for CJ3 output field")
    ap.add_argument("--cj5-col", type=int, help="1-based column number for CJ5 output field")
    ap.add_argument("--cj3-table", type=Path, help="Path to CJ3 table")
    ap.add_argument("--cj5-table", type=Path, help="Path to CJ5 table")

    ap.add_argument("--output", choices=["codes", "prompts"], default="prompts",
                    help="Output Latin codes or prompt characters (default: prompts)")
    args = ap.parse_args()

    # Convert 1-based -> 0-based indices
    source_i = args.source_col - 1
    cj3_i = args.cj3_col - 1 if args.cj3_col is not None else None
    cj5_i = args.cj5_col - 1 if args.cj5_col is not None else None

    cj3: Optional[Dict[str, List[str]]] = load_cangjie_table(args.cj3_table) if cj3_i is not None else None
    cj5: Optional[Dict[str, List[str]]] = load_cangjie_table(args.cj5_table) if cj5_i is not None else None

    with args.in_txt.open("r", encoding="utf-8-sig", errors="replace") as fin, \
         args.out_txt.open("w", encoding="utf-8-sig", newline="") as fout:

        for line in fin:
            if line.startswith("#") or not line.strip():
                fout.write(line)
                continue

            fields = line.rstrip("\n").split("\t")

            # Pad so requested indices exist (handles occasional short rows)
            max_needed = max([source_i] + ([cj3_i] if cj3_i is not None else []) + ([cj5_i] if cj5_i is not None else []))
            if len(fields) <= max_needed:
                fields.extend([""] * (max_needed + 1 - len(fields)))

            src_text = fields[source_i]

            if cj3 is not None and cj3_i is not None:
                fields[cj3_i] = cangjie_for_text(src_text, cj3, output=args.output)
            if cj5 is not None and cj5_i is not None:
                fields[cj5_i] = cangjie_for_text(src_text, cj5, output=args.output)

            fout.write("\t".join(fields) + "\n")


if __name__ == "__main__":
    main()
