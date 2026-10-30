"""Exercise the real analyzer queries with fictional, in-memory Notes rows."""

import contextlib
import datetime
import gzip
import io
import sqlite3
import unittest
import zlib

from dejavault.analyzers.apple_notes import (
    _extract_protobuf_preview,
    run_apple_notes_analysis,
)


class AppleNotesTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript("""
            CREATE TABLE ZICCLOUDSYNCINGOBJECT (
                Z_PK INTEGER PRIMARY KEY, ZTITLE1 TEXT, ZPASSWORDHINT TEXT,
                ZCRYPTOITERATIONCOUNT INTEGER, ZCREATIONDATE1 REAL,
                ZCREATIONDATE3 REAL, ZMODIFICATIONDATE1 REAL, ZCRYPTOSALT BLOB,
                ZCRYPTOWRAPPEDKEY BLOB, ZISPASSWORDPROTECTED INTEGER, ZNOTEDATA INTEGER
            );
            CREATE TABLE ZICNOTEDATA (Z_PK INTEGER PRIMARY KEY, ZDATA BLOB);
        """)

    def note(self, pk, title, created=None, legacy=None, modified=None, locked=False, body=None):
        self.connection.execute(
            "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, NULL, NULL, ?, ?, ?, NULL, NULL, ?, ?)",
            (pk, title, created, legacy, modified, int(locked), pk),
        )
        self.connection.execute("INSERT INTO ZICNOTEDATA VALUES (?, ?)", (pk, body))

    def analyze(self, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_apple_notes_analysis(self.connection.cursor(), **kwargs)
        return output.getvalue()

    @staticmethod
    def timeline(output, pk):
        return next(line.split("|") for line in output.splitlines()
                    if line.split("|")[0].strip() == str(pk))

    def test_creation_fallback_order_and_coredata_date_conversion(self):
        cases = [(1234567, 2234567, 3234567, 1234567),
                 (None, 2234567, 3234567, 2234567),
                 (None, None, 3234567, 3234567)]
        for pk, (created, legacy, modified, expected) in enumerate(cases, 1):
            self.note(pk, "Fictional note {}".format(pk), created, legacy, modified, locked=True)
        output = self.analyze()
        for pk, (_, _, _, expected) in enumerate(cases, 1):
            with self.subTest(pk=pk):
                date = datetime.datetime.fromtimestamp(expected + 978307200).strftime("%Y-%m-%d %H:%M:%S")
                self.assertEqual(self.timeline(output, pk)[1].strip(), date)
                section = output.split("[Locked Note Target | Row ID: {}]".format(pk))[1].split("[Locked Note Target")[0]
                self.assertIn("Note Timestamp   : " + date, section)

    def test_proximity_window_includes_both_boundaries_but_not_the_next_second(self):
        timestamp = 200000000
        self.note(1, "Fictional locked reference", created=timestamp, locked=True)
        offsets = [0, -86400, 86400, -86401, 86401]
        for pk, offset in enumerate(offsets, 2):
            self.note(pk, "Fictional neighbor {}".format(pk), legacy=timestamp + offset)
        output = self.analyze(window_days=1)
        self.assertIn("LOCKED", self.timeline(output, 1)[2])
        for pk, offset in enumerate(offsets, 2):
            with self.subTest(offset=offset):
                self.assertEqual("match" in self.timeline(output, pk)[2], abs(offset) <= 86400)

    def test_locked_payload_is_not_used_as_a_preview(self):
        self.note(1, "Fictional locked", created=200000000, locked=True,
                  body=gzip.compress(b"Hiddenmarker 43219876"))
        self.note(2, "Fictional unlocked", created=200000001,
                  body=gzip.compress(b"Visiblemarker 87651234"))
        output = self.analyze(user_clue="Hiddenmarker")
        joggers = output.split("EXTRACTED MEMORY JOGGERS", 1)[1].split("CLUE CORRELATION", 1)[0]
        self.assertIn("Visiblemarker", joggers)
        self.assertIn("87651234", joggers)
        self.assertNotIn("Hiddenmarker", joggers)
        self.assertNotIn("43219876", joggers)
        self.assertIn("did not appear literally", output)


class PreviewTests(unittest.TestCase):
    def test_gzip_preview_normalizes_controls_and_whitespace(self):
        payload = gzip.compress(b"\x00Fictional\x01 text\t with\n spaces\x0c")
        self.assertEqual(_extract_protobuf_preview(payload), "Fictional text with spaces")

    def test_preview_is_capped_at_200_characters(self):
        self.assertEqual(_extract_protobuf_preview(gzip.compress(b"x" * 240)), "x" * 200)

    def test_absent_invalid_and_wrong_compression_inputs_have_no_preview(self):
        for data in (None, b"", b"not compressed", zlib.compress(b"raw zlib")):
            with self.subTest(data=data):
                self.assertEqual(_extract_protobuf_preview(data), "")
