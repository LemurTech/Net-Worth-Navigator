from pathlib import Path

from src.demo_setup_page import build_demo_setup_page


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_demo_setup_page_matches_live_setup_information_architecture(tmp_path):
    output = tmp_path / "setup.html"
    build_demo_setup_page(
        config_path=REPO_ROOT / "scenarios" / "sample-couples.toml",
        output_path=output,
        slug="sample-couples",
        scenario_options=[("sample-couples", "Sample Couples")],
    )

    html = output.read_text(encoding="utf-8")

    for label in (
        "Metadata",
        "Social Security",
        "Income &amp; Contributions",
        "Accounts",
        "Events",
        "Raw TOML",
    ):
        assert label in html
    assert "Claiming Age" in html
    assert "Retirement Year" in html
    assert "From Retire event" in html
    assert "Employer Match, Routing &amp; Ownership" in html
    assert "Liabilities" in html
    assert "Home Mortgage" in html
    assert "Surgery" in html
    assert "Advanced: Simulation &amp; Monte Carlo" in html
    assert "Read-only public demo" in html
    assert "fetch(" not in html
    assert "/api/" not in html
    assert "Save Event" not in html
    assert "Add Liability" not in html
