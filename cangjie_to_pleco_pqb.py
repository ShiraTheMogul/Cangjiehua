#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build a Pleco .pqb dictionary from Cangjie 3/5 tables.

Input files: cangjie3.txt, cangjie5.txt
Expected line format (robust): <latin_code><whitespace/tab><hanzi><...optional...>
Example: a\t日\t500

Output:
- One entry per character
- defn formatted as:

Cangjie3:
日 月 / ...
a b / ...

Cangjie5:
...

If CJ3 == CJ5, only one section "Cangjie:" is output.

Linebreaks use U+EAB1 (Pleco newline).

Dependencies:
  pip install pypinyin
"""

from __future__ import annotations

import argparse
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Sequence, Set

from pypinyin import Style
from pypinyin import pinyin as pypinyin_pinyin

PLECO_NL = "\ueab1"

# Latin -> Chinese key shape map provided by user
LATIN_TO_SHAPE = {
    "a":"日","b":"月","c":"金","d":"木","e":"水","f":"火","g":"土",
    "h":"竹","i":"戈","j":"十","k":"大","l":"中","m":"一","n":"弓",
    "o":"人","p":"心","q":"手","r":"口","s":"尸","t":"廿","u":"山",
    "v":"女","w":"田","x":"難","y":"卜","z":"重"
}

# CJK filter (same ranges you’ve been using)
CJK_RANGES = [
    (0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F), (0x2B740, 0x2B81D), (0x2B820, 0x2CEAD),
    (0x2CEB0, 0x2EBE0), (0x31350, 0x323AF), (0x2EBF0, 0x2EE5D),
    (0x323B0, 0x33479), (0x2F800, 0x2FA1F),
]
EXTRA_ALLOWED = {0x3007}  # 〇

def is_cjk_word(word: str) -> bool:
    if not word:
        return False
    for ch in word:
        cp = ord(ch)
        if cp in EXTRA_ALLOWED:
            continue
        if not any(lo <= cp <= hi for lo, hi in CJK_RANGES):
            return False
    return True

def load_cangjie_table(path: str) -> Dict[str, Set[str]]:
    """
    Returns: {hanzi: {latin_code1, latin_code2, ...}}
    """
    table: Dict[str, Set[str]] = {}
    p = Path(path)
    text = p.read_text(encoding="utf-8").lstrip("\ufeff")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # robust split: tabs or spaces
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        code, char = parts[0].strip(), parts[1].strip()
        if not code or not char:
            continue
        # Some tables may include non-CJK stuff; filter to single Han character
        if len(char) != 1 or not is_cjk_word(char):
            continue
        table.setdefault(char, set()).add(code)
    return table

def latin_code_to_shapes(code: str) -> str:
    """
    Turn 'abc' into '日月金' based on LATIN_TO_SHAPE.
    Unknown letters are left as-is (rare but safer than dropping).
    """
    out = []
    for ch in code:
        out.append(LATIN_TO_SHAPE.get(ch, ch))
    return "".join(out)

def format_section(label: str, codes: Sequence[str]) -> str:
    """
    Format one section:
      Cangjie3:
      日月 / 日月金
      ab / abc
    """
    # preserve stable ordering
    codes = list(dict.fromkeys(codes))
    shapes = [latin_code_to_shapes(c) for c in codes]
    return (
        f"{label}:{PLECO_NL}"
        f"{' / '.join(shapes)}{PLECO_NL}"
        f"{' / '.join(codes)}"
    )

# ---------------- Plecofreq-style DB output ----------------

_FULLWIDTH_OFFSET = 0xFEE0
def to_fullwidth_ascii(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        out.append(chr(o + _FULLWIDTH_OFFSET) if 0x21 <= o <= 0x7E else ch)
    return "".join(out)

def mandarin_pinyin_tone3(word: str) -> List[str]:
    py = pypinyin_pinyin(word, style=Style.TONE3, heteronym=False, errors=lambda _: [""])
    out = []
    for item in py:
        syl = (item[0] if item else "") or ""
        out.append(syl.replace("ü", "v"))
    return out

def make_sortkey(py_syllables: List[str], word: str) -> str:
    # same pattern as plecofreq: fullwidth(pinyin) + hanzi
    if len(word) == 1:
        return to_fullwidth_ascii(py_syllables[0] if py_syllables else "") + word
    return "".join(to_fullwidth_ascii(s) + c for c, s in zip(word, py_syllables))

def split_pron_tokens(pron: str) -> List[str]:
    return [p for p in re.split(r"[\s@]+", pron.strip()) if p]

SCHEMA_SQL = [
    """
    CREATE TABLE 'pleco_dict_entries' (
      "uid" INTEGER PRIMARY KEY AUTOINCREMENT,
      "created" INTEGER,
      "modified" INTEGER,
      "length" INTEGER,
      "word" TEXT COLLATE NOCASE,
      "altword" TEXT COLLATE NOCASE,
      "pron" TEXT COLLATE NOCASE,
      "defn" TEXT,
      "sortkey" TEXT UNIQUE
    );
    """,
    """
    CREATE TABLE 'pleco_dict_imports' (
      "id" INTEGER PRIMARY KEY AUTOINCREMENT,
      "starttime" INTEGER,
      "endtime" INTEGER,
      "startentry" INTEGER,
      "endentry" INTEGER
    );
    """,
    """
    CREATE TABLE 'pleco_dict_properties' (
      "propset" INTEGER,
      "propid" TEXT,
      "propvalue" TEXT,
      "propisstring" INTEGER,
      UNIQUE ("propset","propid")
    );
    """,
    "CREATE TABLE 'pleco_dict_posdex_hz_1' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_hz_2' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_hz_3' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_hz_4' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_py_1' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_py_2' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_py_3' (syllable TEXT, uid INTEGER, length INTEGER);",
    "CREATE TABLE 'pleco_dict_posdex_py_4' (syllable TEXT, uid INTEGER, length INTEGER);",
]

INDEX_SQL = [
    "CREATE INDEX idx_pleco_dict_entries_sortkey ON pleco_dict_entries (sortkey);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_1_syllable_uid_length ON pleco_dict_posdex_hz_1 (syllable, uid, length);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_1_uid ON pleco_dict_posdex_hz_1 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_2_syllable_uid ON pleco_dict_posdex_hz_2 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_2_uid ON pleco_dict_posdex_hz_2 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_3_syllable_uid ON pleco_dict_posdex_hz_3 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_3_uid ON pleco_dict_posdex_hz_3 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_4_syllable_uid ON pleco_dict_posdex_hz_4 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_hz_4_uid ON pleco_dict_posdex_hz_4 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_1_syllable_uid_length ON pleco_dict_posdex_py_1 (syllable, uid, length);",
    "CREATE INDEX idx_pleco_dict_posdex_py_1_uid ON pleco_dict_posdex_py_1 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_2_syllable_uid ON pleco_dict_posdex_py_2 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_2_uid ON pleco_dict_posdex_py_2 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_3_syllable_uid ON pleco_dict_posdex_py_3 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_3_uid ON pleco_dict_posdex_py_3 (uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_4_syllable_uid ON pleco_dict_posdex_py_4 (syllable, uid);",
    "CREATE INDEX idx_pleco_dict_posdex_py_4_uid ON pleco_dict_posdex_py_4 (uid);",
]

def write_properties(cur: sqlite3.Cursor, *, dict_name: str, menu_name: str, short_name: str, icon: str,
                     entry_count: int, now: int) -> None:
    file_id = random.randint(-2_000_000_000, 2_000_000_000)
    file_creator = random.randint(1, 50_000_000)
    props = [
        ("DictIconFillColor", "39372", 0),
        ("DictIconName", icon, 1),
        ("DictIconTextColor", "16777215", 0),
        ("DictLang", "Chinese", 1),
        ("DictMenuName", menu_name, 1),
        ("DictName", dict_name, 1),
        ("DictShortName", short_name, 1),
        ("EntryCount", str(entry_count), 0),
        ("FileCreated", str(now), 0),
        ("FileCreator", str(file_creator), 0),
        ("FileGenerator", "Pleco Engine 2.0", 1),
        ("FileID", str(file_id), 0),
        ("FilePlatform", "Android", 1),
        ("FormatString", "Pleco SQL Dictionary Database", 1),
        ("FormatVersion", "8", 0),
        ("TransLang", "English", 1),
    ]
    for propid, propvalue, propisstring in props:
        cur.execute(
            "INSERT OR REPLACE INTO pleco_dict_properties (propset, propid, propvalue, propisstring) VALUES (0, ?, ?, ?);",
            (propid, propvalue, propisstring),
        )

def insert_posdex(cur: sqlite3.Cursor, uid: int, word: str, pron: str) -> None:
    wlen = len(word)
    # hz
    for i, ch in enumerate(list(word)[:4], start=1):
        cur.execute(f"INSERT INTO pleco_dict_posdex_hz_{i} (syllable, uid, length) VALUES (?, ?, ?);", (ch, uid, wlen))
    # py
    py_tokens = split_pron_tokens(pron)
    for i, syl in enumerate(py_tokens[:4], start=1):
        cur.execute(f"INSERT INTO pleco_dict_posdex_py_{i} (syllable, uid, length) VALUES (?, ?, ?);", (syl, uid, wlen))

def build_pqb(entries: Dict[str, str], out_path: str,
              dict_name: str, menu_name: str, short_name: str, icon: str) -> None:
    out = Path(out_path)
    if out.exists():
        out.unlink()

    con = sqlite3.connect(str(out))
    con.execute("PRAGMA page_size=1024;")
    con.execute("PRAGMA journal_mode=DELETE;")
    con.execute("PRAGMA synchronous=FULL;")
    cur = con.cursor()

    for sql in SCHEMA_SQL:
        cur.executescript(sql)
    for sql in INDEX_SQL:
        cur.execute(sql)

    now = int(time.time())
    uid = 1

    for ch in sorted(entries.keys()):
        defn = entries[ch]
        py = mandarin_pinyin_tone3(ch)
        pron = " ".join(py)  # match store dictionary style (helps “alongside”)
        sk = make_sortkey(py, ch) or ch

        cur.execute(
            "INSERT INTO pleco_dict_entries (uid, created, modified, length, word, altword, pron, defn, sortkey) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (uid, now, now, 1, ch, None, pron, defn, sk),
        )
        insert_posdex(cur, uid, ch, pron)
        uid += 1

    count = uid - 1
    write_properties(cur, dict_name=dict_name, menu_name=menu_name, short_name=short_name,
                     icon=icon, entry_count=count, now=now)
    cur.execute(
        "INSERT INTO pleco_dict_imports (starttime, endtime, startentry, endentry) VALUES (?, ?, 1, ?);",
        (now, now, count)
    )

    con.commit()
    con.close()
    print(f"Wrote {out_path} with {count} entries.")

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cj3", default="cangjie3.txt", help="Cangjie3 table (default: cangjie3.txt)")
    ap.add_argument("--cj5", default="cangjie5.txt", help="Cangjie5 table (default: cangjie5.txt)")
    ap.add_argument("--out", required=True, help="Output .pqb")

    ap.add_argument("--dict-name", default="Cangjie Input Dictionary 倉頡輸入字典")
    ap.add_argument("--menu-name", default="Cangjie Input Dictionary")
    ap.add_argument("--short-name", default="Cangjie Input Dictionary")
    ap.add_argument("--icon", default="CJ")

    args = ap.parse_args()

    cj3 = load_cangjie_table(args.cj3)
    cj5 = load_cangjie_table(args.cj5)

    all_chars = set(cj3.keys()) | set(cj5.keys())

    entries: Dict[str, str] = {}
    for ch in all_chars:
        codes3 = sorted(cj3.get(ch, set()))
        codes5 = sorted(cj5.get(ch, set()))

        if not codes3 and not codes5:
            continue

        if codes3 == codes5:
            # identical => single section
            entries[ch] = format_section("Cangjie", codes3)
        else:
            parts = []
            if codes3:
                parts.append(format_section("Cangjie3", codes3))
            if codes5:
                parts.append(format_section("Cangjie5", codes5))
            entries[ch] = (PLECO_NL + PLECO_NL).join(parts)

    if not entries:
        raise SystemExit("No entries found — check input file formats/paths.")

    build_pqb(entries, args.out, args.dict_name, args.menu_name, args.short_name, args.icon)

if __name__ == "__main__":
    main()
