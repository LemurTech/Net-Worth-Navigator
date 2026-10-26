"""Regression tests for the CSV upload temp-file path (GitHub issue #4).

The upload endpoint used to write its scratch file to a hardcoded ``/tmp``.
On Windows a POSIX-style path is rooted but not absolute, so it resolves to
``<current drive>:\\tmp\\...`` and the write raises ``FileNotFoundError``
whenever that directory does not exist -- surfacing as an opaque
"Parse failed." even for the bundled sample CSV.
"""

import tempfile
import unittest
from pathlib import Path

import admin_app
from src.csv_importer import parse_csv

SAMPLE_CSV = (
    Path(__file__).resolve().parent.parent / "docs" / "assets" / "sample-accounts.csv"
)


class CsvUploadTempFileTests(unittest.TestCase):
    """_write_csv_upload_temp() -- platform-neutral scratch file handling."""

    def test_writes_content_under_the_system_temp_dir(self):
        payload = b"Date,Account,Balance\n2026-01-02,Checking,100.00\n"
        path = admin_app._write_csv_upload_temp(payload, "unit-test")
        try:
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(path.parent.resolve(), Path(tempfile.gettempdir()).resolve())
            self.assertTrue(path.name.startswith("csv_upload_unit-test_"))
            self.assertTrue(path.name.endswith(".csv"))
        finally:
            path.unlink(missing_ok=True)

    def test_missing_slug_falls_back_to_default(self):
        path = admin_app._write_csv_upload_temp(b"x", None)
        try:
            self.assertTrue(path.name.startswith("csv_upload_default_"))
        finally:
            path.unlink(missing_ok=True)

    def test_each_upload_gets_its_own_path(self):
        first = admin_app._write_csv_upload_temp(b"x", "dup")
        second = admin_app._write_csv_upload_temp(b"x", "dup")
        try:
            self.assertNotEqual(first, second)
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)

    def test_bundled_sample_parses_through_the_temp_file(self):
        """The documented sample must survive the temp-file round trip."""
        path = admin_app._write_csv_upload_temp(SAMPLE_CSV.read_bytes(), "sample")
        try:
            parsed = parse_csv(str(path))
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(parsed), 9)
        self.assertIn("Checking", {acct["name"] for acct in parsed})

    def test_no_hardcoded_posix_tmp_scratch_path(self):
        """Guard against reintroducing the POSIX-only scratch path."""
        source = Path(admin_app.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"/tmp/csv_upload', source)


if __name__ == "__main__":
    unittest.main()
