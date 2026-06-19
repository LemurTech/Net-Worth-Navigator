import tempfile
import unittest
from pathlib import Path

from src.config_loader import deep_merge, load_config, merge_tax_tables


class ConfigLoaderTests(unittest.TestCase):
    def test_deep_merge_preserves_nested_base_values(self):
        merged = deep_merge(
            {
                "taxes": {
                    "enabled": True,
                    "state": {"enabled": True, "name": "oregon"},
                }
            },
            {
                "taxes": {
                    "state": {"enabled": False},
                }
            },
        )
        self.assertEqual(merged["taxes"]["enabled"], True)
        self.assertEqual(merged["taxes"]["state"]["enabled"], False)
        self.assertEqual(merged["taxes"]["state"]["name"], "oregon")

    def test_merge_tax_tables_applies_shared_tax_reference_data(self):
        merged = merge_tax_tables(
            {
                "taxes": {
                    "enabled": True,
                    "table_set": "2025_us_federal_oregon",
                    "retirement_filing_status": "married_joint",
                }
            }
        )
        self.assertEqual(merged["taxes"]["enabled"], True)
        self.assertEqual(merged["taxes"]["year"], 2025)
        self.assertEqual(
            merged["taxes"]["standard_deduction"]["married_joint"],
            30000,
        )
        self.assertEqual(
            merged["taxes"]["state"]["standard_deduction"]["single"],
            2835,
        )
        self.assertEqual(
            merged["taxes"]["brackets"]["single"][0]["up_to"],
            11925,
        )

    def test_load_config_reads_root_config_and_merges_tax_table_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[simulation]",
                        "start_year = 2026",
                        "end_year = 2026",
                        "",
                        "[taxes]",
                        'enabled = true',
                        'table_set = "2025_us_federal_oregon"',
                        'pre_retirement_filing_status = "married_joint"',
                    ]
                ),
                encoding="utf-8",
            )
            loaded = load_config(config_path)

        self.assertEqual(loaded["simulation"]["start_year"], 2026)
        self.assertEqual(loaded["taxes"]["enabled"], True)
        self.assertEqual(loaded["taxes"]["state"]["name"], "oregon")

