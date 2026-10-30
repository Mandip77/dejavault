"""Read-only and lifecycle checks using only a generated SQLite database."""

import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dejavault.safe_copy import SafeDatabaseCopy


class SafeDatabaseCopyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "synthetic.sqlite"
        with sqlite3.connect(self.source) as connection:
            connection.execute("CREATE TABLE sample (value TEXT)")
            connection.execute("INSERT INTO sample VALUES ('fictional row')")
        self.original_hash = self.digest(self.source)

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_copy_is_distinct_read_only_and_removed_on_exit(self):
        sandbox = SafeDatabaseCopy(str(self.source))
        # Also clean up if a regression leaves the directory behind.
        with sandbox as cursor:
            self.addCleanup(shutil.rmtree, sandbox.temp_dir, ignore_errors=True)
            copy = Path(sandbox.safe_db_path)
            self.assertNotEqual(copy, self.source)
            self.assertEqual(self.digest(copy), self.original_hash)
            self.assertEqual(cursor.execute("SELECT value FROM sample").fetchall(), [("fictional row",)])
            for statement in ("INSERT INTO sample VALUES ('changed')", "UPDATE sample SET value='changed'"):
                with self.subTest(statement=statement):
                    with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                        cursor.execute(statement)
            self.assertEqual(self.digest(self.source), self.original_hash)
            self.assertEqual(self.digest(copy), self.original_hash)
        self.assertFalse(Path(sandbox.temp_dir).exists())
        self.assertEqual(self.digest(self.source), self.original_hash)
        with self.assertRaises(sqlite3.ProgrammingError):
            cursor.execute("SELECT 1")

    def test_exception_propagates_and_still_closes_and_removes_copy(self):
        sandbox = SafeDatabaseCopy(str(self.source))
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with sandbox as cursor:
                self.addCleanup(shutil.rmtree, sandbox.temp_dir, ignore_errors=True)
                raise RuntimeError("synthetic failure")
        self.assertFalse(Path(sandbox.temp_dir).exists())
        self.assertEqual(self.digest(self.source), self.original_hash)
        with self.assertRaises(sqlite3.ProgrammingError):
            cursor.execute("SELECT 1")

    def test_keep_temp_retains_copy_but_closes_connection(self):
        sandbox = SafeDatabaseCopy(str(self.source), keep_temp=True)
        with sandbox as cursor:
            self.addCleanup(shutil.rmtree, sandbox.temp_dir, ignore_errors=True)
        self.assertTrue(Path(sandbox.temp_dir).is_dir())
        self.assertEqual(self.digest(Path(sandbox.safe_db_path)), self.original_hash)
        self.assertEqual(self.digest(self.source), self.original_hash)
        with self.assertRaises(sqlite3.ProgrammingError):
            cursor.execute("SELECT 1")
