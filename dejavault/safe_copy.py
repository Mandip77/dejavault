"""
safe_copy.py
Handles cross-platform sandbox copying of live SQLite databases (plus WAL/SHM journals)
into isolated temporary directories and opens strict read-only connections.
"""

import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from types import TracebackType
from typing import Optional, Type

MACOS_NOTES_DEFAULT = os.path.expanduser(
    "~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
)
IOS_BACKUP_NOTES_HASH = "4f98687d8ab0d6d1a371110e6b7300f6e465bef2"


class SafeDatabaseCopy:
    """Context manager that clones a target SQLite DB to a temp folder in read-only mode."""

    def __init__(self, source_path: str, keep_temp: bool = False) -> None:
        self.source_path = os.path.expanduser(source_path)
        self.keep_temp = keep_temp
        self.temp_dir: Optional[str] = None
        self.safe_db_path: Optional[str] = None
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Cursor:
        if not os.path.exists(self.source_path):
            print(f"\n[!] Error: Database file not found at:\n    {self.source_path}")
            if platform.system() != "Darwin":
                print(
                    f"    Tip: On Windows/Linux, pass --db /path/to/{IOS_BACKUP_NOTES_HASH} "
                    "from an iOS backup or any app's .sqlite file."
                )
            sys.exit(1)

        self.temp_dir = tempfile.mkdtemp(prefix="dejavault_sandbox_")
        base_name = os.path.basename(self.source_path)
        self.safe_db_path = os.path.join(self.temp_dir, base_name)

        try:
            shutil.copy2(self.source_path, self.safe_db_path)
            # Always copy Write-Ahead Log (-wal) and Shared Memory (-shm) files if present
            for suffix in ("-wal", "-shm"):
                companion = self.source_path + suffix
                if os.path.exists(companion):
                    shutil.copy2(companion, self.safe_db_path + suffix)
        except PermissionError:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            print("\n[!] PERMISSION DENIED: OS blocked access to the database.")
            if platform.system() == "Darwin":
                print("    macOS TCC Fix (takes 10 seconds):")
                print("    1. Open System Settings -> Privacy & Security -> Full Disk Access")
                print("    2. Toggle ON your terminal app (Terminal, iTerm2, or VS Code)")
                print("    3. Quit (Cmd+Q) and reopen your terminal, then run dejavault again.\n")
            sys.exit(1)

        # Open in read-only URI mode so the sandbox copy is never mutated
        uri = f"file:{self.safe_db_path}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        return self.conn.cursor()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.conn:
            self.conn.close()
        if self.temp_dir and not self.keep_temp:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
