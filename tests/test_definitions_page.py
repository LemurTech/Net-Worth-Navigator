import tempfile
import unittest
from pathlib import Path

from src.definitions_page import build_definitions_page_html, write_definitions_page


class DefinitionsPageTests(unittest.TestCase):
    def test_build_definitions_page_html_includes_key_sections_and_links(self):
        html = build_definitions_page_html(
            editor_url="/finances/config/",
            projection_url="/finances/projection.html",
        )

        self.assertIn("Definitions And Options", html)
        self.assertIn("Scenario And Display", html)
        self.assertIn("Market And Economic Assumptions", html)
        self.assertIn("Setup Panel Map", html)
        self.assertIn("[simulation].mode", html)
        self.assertIn("Timeline: `Retire` / `SocialSecurity` / `EndOfPlan` events", html)
        self.assertIn("[personX].roth_share", html)
        self.assertIn("<code>csv_import</code>", html)
        self.assertIn("not stored on the event", html)
        self.assertNotIn(
            "Fields: <code>person</code>, <code>year</code>, <code>monthly_benefit</code>",
            html,
        )
        self.assertIn("/finances/config/", html)
        self.assertIn("/finances/projection.html", html)

    def test_write_definitions_page_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "definitions.html"
            write_definitions_page(output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertIn("Net Worth Navigator Reference", html)
        self.assertIn("Accounts Metadata", html)


if __name__ == "__main__":
    unittest.main()
