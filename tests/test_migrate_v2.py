"""Regression tests for scripts/migrate_v2.py --strip-comments behavior."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate_v2


MIGRATED_WITH_COMMENTS = """# Household scenario
# documentation line that must survive for samples

[scenario]
name = "Strip Test"

[[events]]
enabled = true
type = "Retire"
label = "Retirement (T)"
person = "person1"
year = 2035
"""


class MigrateV2StripTests(unittest.TestCase):
    @staticmethod
    def _write(tmp: str, name: str, content: str) -> Path:
        path = Path(tmp) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_strip_comments_reports_and_removes(self):
        with TemporaryDirectory() as td:
            path = self._write(td, "myhousehold.toml", MIGRATED_WITH_COMMENTS)
            actions = migrate_v2.migrate_scenario(path, strip_comments=True)
            self.assertTrue(any("comments stripped" in a for a in actions), actions)
            self.assertNotIn("#", path.read_text(encoding="utf-8"))

    def test_strip_comments_skips_sample_files(self):
        with TemporaryDirectory() as td:
            path = self._write(td, "sample_scratch.toml", MIGRATED_WITH_COMMENTS)
            actions = migrate_v2.migrate_scenario(path, strip_comments=True)
            self.assertFalse(any("stripped" in a for a in actions), actions)
            self.assertIn("# documentation line", path.read_text(encoding="utf-8"))

    def test_strip_comments_skips_starter_files(self):
        with TemporaryDirectory() as td:
            path = self._write(td, "starter.toml", MIGRATED_WITH_COMMENTS)
            actions = migrate_v2.migrate_scenario(path, strip_comments=True)
            self.assertFalse(any("stripped" in a for a in actions), actions)
            self.assertIn("# documentation line", path.read_text(encoding="utf-8"))

    def test_dry_run_reports_without_writing(self):
        with TemporaryDirectory() as td:
            path = self._write(td, "myhousehold.toml", MIGRATED_WITH_COMMENTS)
            before = path.read_text(encoding="utf-8")
            actions = migrate_v2.migrate_scenario(path, strip_comments=True, dry_run=True)
            self.assertTrue(any("comments stripped" in a for a in actions), actions)
            self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_clean_file_does_not_claim_stripping(self):
        clean = MIGRATED_WITH_COMMENTS.replace(
            "# Household scenario\n# documentation line that must survive for samples\n\n", ""
        )
        with TemporaryDirectory() as td:
            path = self._write(td, "cleanhousehold.toml", clean)
            actions = migrate_v2.migrate_scenario(path, strip_comments=True)
            self.assertFalse(any("comments stripped" in a for a in actions), actions)
            self.assertNotIn("#", clean)


if __name__ == "__main__":
    unittest.main()
