"""
cli.py
Command-line entry point for DejaVault.
"""

import argparse
import platform
import sys

from . import __version__
from .analyzers import run_apple_notes_analysis, run_universal_sqlite_analysis
from .safe_copy import IOS_BACKUP_NOTES_HASH, MACOS_NOTES_DEFAULT, SafeDatabaseCopy

BANNER = rf"""
==============================================================================
  ____       _     __     __          _ _   
 |  _ \  ___(_) __ \ \   / /_ _ _   _| | |_ 
 | | | |/ _ \ |/ _` \ \ / / _` | | | | | __|
 | |_| |  __/ | (_| |\ V / (_| | |_| | | |_ 
 |____/ \___|_|\__,_| \_/ \__,_|\__,_|_|\__|  v{__version__}

 Unlock your memory to unlock your vault: SQLite Forensics & Context CLI
==============================================================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dejavault",
        description="Read-only SQLite forensics & context time-machine to recover forgotten password clues.",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help="Path to target SQLite database (or iOS backup file). Defaults to macOS Apple Notes.",
        default=None,
    )
    parser.add_argument(
        "--clue",
        metavar="KEYWORD",
        help="Optional word, name, or hint you vaguely remember to correlate across the database.",
        default="",
    )
    parser.add_argument(
        "--window",
        metavar="DAYS",
        type=int,
        default=180,
        help="Proximity window in days (+/-) around locked notes to highlight (default: 120).",
    )
    parser.add_argument(
        "--universal",
        action="store_true",
        help="Force Universal SQLite Heuristic Scanner mode even on Apple Notes databases.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Do not delete the temporary sandboxed database copy on exit.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(BANNER)

    # Resolve target database path
    if args.db:
        target_db = args.db
    elif platform.system() == "Darwin":
        target_db = MACOS_NOTES_DEFAULT
        print(f"[*] Auto-detected macOS: targeting local Apple Notes database.")
    else:
        print("[!] Non-macOS platform detected and no --db path was provided.")
        print("    Usage examples:")
        print("      dejavault --db /path/to/app_database.sqlite")
        print(f"      dejavault --db /path/to/ios_backup/{IOS_BACKUP_NOTES_HASH}")
        sys.exit(1)

    clue = args.clue.strip()
    if not clue and sys.stdin.isatty():
        try:
            clue = input(
                "\n[?] Enter a vague clue/keyword you remember (or press Enter to run full scan): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Aborted by user.")
            sys.exit(0)

    with SafeDatabaseCopy(target_db, keep_temp=args.keep_temp) as cur:
        tables = {
            r[0]
            for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        }

        if "ZICCLOUDSYNCINGOBJECT" in tables and not args.universal:
            run_apple_notes_analysis(cur, window_days=args.window, user_clue=clue)
        else:
            run_universal_sqlite_analysis(cur, user_clue=clue)

    if not args.keep_temp:
        print("\n[+] Sandbox cleanup complete: temporary working copy securely removed.\n")


if __name__ == "__main__":
    main()
