"""
universal.py
Cross-platform heuristic SQLite scanner that works on ANY application's SQLite database
(e.g., Bear, Joplin, Day One, browser histories, or custom mobile/desktop app databases).
"""

import re
import sqlite3
from typing import List, Set, Tuple

TEXT_COLUMN_KEYWORDS = (
    "hint",
    "title",
    "name",
    "subject",
    "text",
    "body",
    "note",
    "content",
    "desc",
    "label",
    "user",
    "account",
)


def run_universal_sqlite_analysis(
    cur: sqlite3.Cursor, user_clue: str = "", row_limit: int = 500
) -> None:
    """Scans all tables in an arbitrary SQLite database for hints, proper nouns, and clue matches."""
    print("\n" + "=" * 78)
    print(" 🌍 UNIVERSAL SQLITE HEURISTIC SCANNER (CROSS-PLATFORM APP MODE)")
    print("=" * 78)

    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
    ]
    print(f"[*] Discovered {len(tables)} table(s) in database. Scanning candidate text columns...\n")

    proper_nouns: Set[str] = set()
    numbers_spotted: Set[str] = set()
    hint_columns_found: List[Tuple[str, str, str]] = []
    clue_matches: List[Tuple[str, str, str]] = []

    for table in tables:
        try:
            col_info = cur.execute(f"PRAGMA table_info('{table}')").fetchall()
            cols = [c[1] for c in col_info]

            target_cols = [
                c for c in cols if any(k in c.lower() for k in TEXT_COLUMN_KEYWORDS)
            ]
            if not target_cols:
                continue

            quoted_cols = ", ".join([f'"{c}"' for c in target_cols])
            query = f'SELECT {quoted_cols} FROM "{table}" LIMIT {int(row_limit)}'
            rows = cur.execute(query).fetchall()

            for row in rows:
                for col_name, val in zip(target_cols, row):
                    if not isinstance(val, str) or not val.strip():
                        continue
                    clean_val = " ".join(val.split())

                    # Flag any column explicitly named *hint*
                    if "hint" in col_name.lower():
                        hint_columns_found.append((table, col_name, clean_val[:100]))

                    proper_nouns.update(re.findall(r"\b[A-Z][a-z]{2,15}\b", clean_val))
                    numbers_spotted.update(re.findall(r"\b\d{4,8}\b", clean_val))

                    if user_clue and user_clue.lower() in clean_val.lower():
                        clue_matches.append((table, col_name, clean_val[:90]))
        except sqlite3.Error:
            continue

    if hint_columns_found:
        print("🔑 EXPLICIT HINT COLUMNS DISCOVERED:")
        for tbl, col, val in hint_columns_found[:20]:
            print(f"  • [{tbl}.{col}] -> '{val}'")
        print()

    if user_clue:
        print(f"🔎 UNIVERSAL SEARCH RESULTS FOR CLUE: '{user_clue}'")
        if clue_matches:
            for tbl, col, snippet in clue_matches[:20]:
                print(f"  • [{tbl}.{col}]: {snippet}")
        else:
            print(f"  [-] No literal matches for '{user_clue}' across scanned text columns.")
        print()

    print("💡 EXTRACTED MEMORY JOGGERS ACROSS DATABASE:")
    if proper_nouns:
        print(f"  • Capitalized Words / Names : {', '.join(sorted(list(proper_nouns))[:40])}")
    if numbers_spotted:
        print(f"  • 4-8 Digit Numbers / Dates : {', '.join(sorted(list(numbers_spotted))[:30])}")
    if not proper_nouns and not numbers_spotted:
        print("  [-] No plaintext proper nouns or 4-8 digit numbers found in candidate columns.")
