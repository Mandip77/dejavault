"""
apple_notes.py
Specialized analyzer for macOS & iOS Apple Notes (NoteStore.sqlite).
Separates legacy per-note locks from account-level resets, converts CoreData
timestamps with COALESCE fallback, and performs +/- day window proximity analysis.
"""

import re
import sqlite3
import zlib
from typing import Dict, List, Optional, Set, Tuple

COREDATA_OFFSET = 978307200
SECONDS_PER_DAY = 86400


def _extract_protobuf_preview(zdata: Optional[bytes]) -> str:
    """Safely decompresses unlocked Apple Notes gzipped protobuf blobs to extract readable text."""
    if not zdata:
        return ""
    try:
        raw = zlib.decompress(zdata, 16 + zlib.MAX_WBITS)
        text = raw.decode("utf-8", errors="ignore")
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
        return " ".join(cleaned.split())[:200]
    except Exception:
        return ""


def run_apple_notes_analysis(
    cur: sqlite3.Cursor, window_days: int = 150, user_clue: str = ""
) -> None:
    """Executes full forensic metadata & context time-machine analysis on NoteStore.sqlite."""
    print("\n" + "=" * 78)
    print(" 🍏 APPLE NOTES FORENSIC METADATA & PASSWORD HINT INSPECTOR")
    print("=" * 78)

    # Use COALESCE so if ZCREATIONDATE1 is NULL (common on older iCloud notes),
    # it automatically falls back to ZCREATIONDATE3 or ZMODIFICATIONDATE1.
    lock_query = """
    SELECT 
        Z_PK,
        ZTITLE1,
        ZPASSWORDHINT,
        ZCRYPTOITERATIONCOUNT,
        COALESCE(ZCREATIONDATE1, ZCREATIONDATE3, ZMODIFICATIONDATE1) AS EffectiveTS,
        datetime(COALESCE(ZCREATIONDATE1, ZCREATIONDATE3, ZMODIFICATIONDATE1) + 978307200, 'unixepoch', 'localtime') AS EffectiveDate,
        datetime(ZMODIFICATIONDATE1 + 978307200, 'unixepoch', 'localtime') AS Modified,
        length(ZCRYPTOSALT) AS SaltLen,
        length(ZCRYPTOWRAPPEDKEY) AS KeyLen
    FROM ZICCLOUDSYNCINGOBJECT
    WHERE ZISPASSWORDPROTECTED = 1 
       OR ZPASSWORDHINT IS NOT NULL 
       OR ZCRYPTOSALT IS NOT NULL
    ORDER BY Z_PK ASC;
    """
    rows = cur.execute(lock_query).fetchall()
    locked_targets: List[Dict[str, object]] = []

    if not rows:
        print("[-] No password-protected notes or saved hints found in this database.")
    else:
        for pk, title, hint, iters, raw_ts, eff_date, modified, salt_len, key_len in rows:
            if title is None:
                print(f"\n[Account-Level Password Reset Object | Row ID: {pk}]")
                print(f"  • Account Hint     : '{hint if hint else 'None'}'")
                print(f"  • PBKDF2 Iterations: {iters}")
                print(
                    "  • Forensic Insight : This row represents a newer account-level password setting.\n"
                    "                       Changing your Notes password later does NOT update the\n"
                    "                       password on older locked notes!"
                )
            else:
                locked_targets.append(
                    {
                        "pk": pk,
                        "title": title,
                        "hint": hint,
                        "raw_ts": raw_ts or 0,
                        "date": eff_date or "Unknown",
                        "modified": modified or "Unknown",
                    }
                )
                lock_style = (
                    f"Custom Password (PBKDF2 {iters} iters, {salt_len}B salt, {key_len}B wrapped key)"
                    if key_len
                    else "Device Passcode / iCloud Keychain"
                )
                print(f"\n[Locked Note Target | Row ID: {pk}]")
                print(f"  • Note Title       : {title}")
                print(f"  • Original Hint    : '{hint if hint else 'No hint saved'}'")
                print(f"  • Note Timestamp   : {eff_date}")
                print(f"  • Last Modified    : {modified}")
                print(f"  • Encryption Type  : {lock_style}")

    timeline_query = """
    SELECT 
        n.Z_PK,
        n.ZTITLE1,
        COALESCE(n.ZCREATIONDATE1, n.ZCREATIONDATE3, n.ZMODIFICATIONDATE1) AS EffectiveTS,
        datetime(COALESCE(n.ZCREATIONDATE1, n.ZCREATIONDATE3, n.ZMODIFICATIONDATE1) + 978307200, 'unixepoch', 'localtime') AS EffectiveDate,
        d.ZDATA,
        n.ZISPASSWORDPROTECTED,
        n.ZPASSWORDHINT
    FROM ZICCLOUDSYNCINGOBJECT n
    LEFT JOIN ZICNOTEDATA d ON n.ZNOTEDATA = d.Z_PK
    WHERE n.ZTITLE1 IS NOT NULL
    ORDER BY EffectiveTS ASC;
    """
    all_notes = cur.execute(timeline_query).fetchall()

    print("\n" + "=" * 78)
    print(f" 🕰️  CONTEXT TIME-MACHINE (PROXIMITY WINDOW: ±{window_days} DAYS)")
    print("=" * 78)

    names_spotted: Set[str] = set()
    numbers_spotted: Set[str] = set()

    print(f"{'ID':<5} | {'Note Timestamp':<19} | {'Proximity':<13} | {'Title'}")
    print("-" * 78)

    for pk, title, raw_ts, eff_date, zdata, is_locked, hint in all_notes:
        proximity_tag = "🔒 LOCKED" if is_locked == 1 else ""
        if not proximity_tag and raw_ts and locked_targets:
            for t in locked_targets:
                t_ts = float(t["raw_ts"])  # type: ignore[arg-type]
                if t_ts and abs(raw_ts - t_ts) <= (window_days * SECONDS_PER_DAY):
                    days_diff = int(abs(raw_ts - t_ts) // SECONDS_PER_DAY)
                    proximity_tag = f"⭐ ±{days_diff}d match"
                    break

        c_str = str(eff_date) if eff_date else "Unknown Date"
        print(f"{pk:<5} | {c_str:<19} | {proximity_tag:<13} | {title[:37]}")

        body_preview = "" if is_locked == 1 else _extract_protobuf_preview(zdata)
        combined_text = f"{title} {body_preview}"
        names_spotted.update(re.findall(r"\b[A-Z][a-z]{2,15}\b", combined_text))
        numbers_spotted.update(re.findall(r"\b\d{4,8}\b", combined_text))

    print("\n💡 EXTRACTED MEMORY JOGGERS (FROM YOUR TIMELINE & UNLOCKED NOTE PREVIEWS):")
    if names_spotted:
        print(f"  • Names / Proper Nouns : {', '.join(sorted(list(names_spotted))[:35])}")
    if numbers_spotted:
        print(f"  • Numbers / Dates / PINs: {', '.join(sorted(list(numbers_spotted))[:25])}")

    if user_clue:
        print("\n" + "=" * 78)
        print(f" 🔎 CLUE CORRELATION REPORT FOR: '{user_clue}'")
        print("=" * 78)
        matches: List[Tuple[int, str, str]] = []
        for pk, title, _, eff_date, zdata, is_locked, hint in all_notes:
            body_preview = "" if is_locked == 1 else _extract_protobuf_preview(zdata)
            haystack = f"{title} {hint or ''} {body_preview}".lower()
            if user_clue.lower() in haystack:
                matches.append((pk, str(eff_date), title))

        if matches:
            print(f"[+] Found {len(matches)} note(s) referencing '{user_clue}':")
            for m_pk, m_dt, m_title in matches:
                print(f"    • Row {m_pk} ({m_dt}): {m_title}")
        else:
            print(f"[-] '{user_clue}' did not appear literally in unlocked titles/bodies.")

        print("\n📋 HUMAN RECALL CHECKLIST TO TEST IN THE APPLE NOTES PASSWORD BOX:")
        print(f"  1. Case Variants     : {user_clue.lower()}, {user_clue.capitalize()}, {user_clue.upper()}")
        print("  2. Era Combinations  : Pair your clue with the year the locked note was created")
        print("                         or any 4-digit PINs spotted in the Memory Joggers above.")
        print("  3. Title Shortening  : Try the first word of the locked note's title itself.")
