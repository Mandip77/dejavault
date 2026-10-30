import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
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
        self.cursor: Optional[sqlite3.Cursor] = None

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

        # Open in read-only URI mode so the sandbox copy is never mutated.
        # Closing the cursor and connection before removing the temp directory avoids
        # Windows file-lock errors during cleanup.
        uri = f"file:{self.safe_db_path}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.cursor = self.conn.cursor()
        return self.cursor

    def _remove_temp_dir(self) -> None:
        if not self.temp_dir or self.keep_temp:
            return

        last_error: Optional[BaseException] = None
        for attempt in range(10):
            try:
                shutil.rmtree(self.temp_dir)
                return
            except (FileNotFoundError, PermissionError) as exc:
                last_error = exc
                time.sleep(0.1 * (attempt + 1))

        # Final best-effort cleanup; this avoids flaky Windows lock races after the
        # SQLite connection has been closed.
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        try:
            if self.cursor is not None:
                self.cursor.close()
                self.cursor = None
            if self.conn is not None:
                self.conn.close()
                self.conn = None
        finally:
            self._remove_temp_dir()
