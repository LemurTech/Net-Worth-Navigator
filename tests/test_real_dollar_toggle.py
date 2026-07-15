"""Tests for the real-dollar toggle dual-view feature."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pandas as pd
from src.charts import build_chart
from src.model import ProjectionResult


def _make_mock_figure():
    """Return a MagicMock that quacks like a Plotly Figure for to_html()."""
    fig = MagicMock()
    fig.to_html.return_value = "<div id='nwn-chart'></div><script>Plotly.newPlot(...)</script>"
    fig.to_plotly_json.return_value = {"data": [], "layout": {}}
    return fig


class TestRealDollarModelLayer:
    """Tests for the model-layer dual-data capture."""

    def test_nominal_yearly_df_is_none_when_real_dollar_basis_false(self):
        """When real_dollar_basis is false, nominal_yearly_df should be None."""
        result = ProjectionResult(
            mode="deterministic",
            yearly_df=pd.DataFrame(),
            summary={},
            simulation={"real_dollar_basis": False},
            nominal_yearly_df=None,
        )
        assert result.nominal_yearly_df is None

    def test_build_chart_no_nominal_when_mode_false(self):
        """build_chart should not emit nominal elements when real_dollar_basis is false."""
        config = {
            "display": {"projection_title": "Test"},
            "person1": {"name": "Alex", "dob": "1972-06-15"},
            "simulation": {"start_year": 2026, "end_year": 2030},
            "assumptions": {"inflation": 0.03, "stock_return": 0.10, "bond_return": 0.04},
            "spending": {"retirement_annual": 60000},
        }
        df = pd.DataFrame([
            {
                "year": 2026, "total_net_worth": 500000.0, "cash": 50000.0,
                "taxable": 100000.0, "trad_ira": 200000.0, "roth": 150000.0,
                "home_value": 400000.0, "mortgage": 100000.0, "home_equity": 300000.0,
                "net_worth": 500000.0, "person1_income": 80000.0, "person2_income": 0.0,
                "annual_spend": 60000.0, "annual_taxes": 12000.0, "annual_federal_taxes": 9000.0,
                "annual_state_taxes": 3000.0, "net_flow": 8000.0, "survivor": False,
                "events_active": "", "event_items": [], "freed_payments": 0.0,
                "required_outflows": 72000.0, "event_outflow_total": 0.0,
                "funding_shortfall": 0.0, "tax_phase": "pre_retirement", "tax_mode": "standard",
                "tax_filing_status": "joint", "taxable_income": 70000.0,
                "withdrawal_cash": 0.0, "withdrawal_taxable": 0.0, "withdrawal_trad_ira": 0.0,
                "withdrawal_roth": 0.0, "contribution_trad_ira": 0.0, "contribution_roth": 0.0,
                "contribution_total": 0.0, "contribution_employee_trad_ira": 0.0,
                "contribution_employee_roth": 0.0, "surplus_to_taxable": 0.0,
                "surplus_to_trad_ira": 0.0, "surplus_to_roth": 0.0,
                "employer_match_total": 0.0, "employer_match_person1": 0.0,
                "employer_match_person2": 0.0, "taxable_cost_basis": 50000.0,
                "taxable_unrealized_gain": 50000.0, "roth_contribution_basis": 150000.0,
                "roth_earnings": 0.0, "cash_reserve_target": 40000.0,
            },
        ])
        result = ProjectionResult(
            mode="deterministic",
            yearly_df=df,
            summary={},
            simulation={"real_dollar_basis": False},
            nominal_yearly_df=None,
        )
        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with patch("src.charts._build_figure",
                               return_value=_make_mock_figure()):
                        with tempfile.TemporaryDirectory() as tmp:
                            out = Path(tmp) / "test.html"
                            build_chart(result, out)
                            html = out.read_text(encoding="utf-8")

        # When real_dollar_basis is false: no nominal chart div, no toggle pill
        import re as _re
        assert 'id="nwn-chart-nominal"' not in html
        assert 'id="nwn-value-toggle"' not in html
        assert not _re.search(r'data-nominal[\s]*=', html), "no data-nominal HTML attributes"

    def test_build_chart_emits_nominal_elements_when_mode_true(self):
        """build_chart should emit nominal elements when real_dollar_basis is true."""
        config = {
            "display": {"projection_title": "Test"},
            "person1": {"name": "Alex", "dob": "1972-06-15"},
            "simulation": {"start_year": 2026, "end_year": 2030,
                           "real_dollar_basis": True},
            "assumptions": {"inflation": 0.03, "stock_return": 0.10, "bond_return": 0.04},
            "spending": {"retirement_annual": 60000},
        }
        df = pd.DataFrame([
            {
                "year": 2026, "total_net_worth": 500000.0, "cash": 50000.0,
                "taxable": 100000.0, "trad_ira": 200000.0, "roth": 150000.0,
                "home_value": 400000.0, "mortgage": 100000.0, "home_equity": 300000.0,
                "net_worth": 500000.0, "person1_income": 80000.0, "person2_income": 0.0,
                "annual_spend": 60000.0, "annual_taxes": 12000.0, "annual_federal_taxes": 9000.0,
                "annual_state_taxes": 3000.0, "net_flow": 8000.0, "survivor": False,
                "events_active": "", "event_items": [], "freed_payments": 0.0,
                "required_outflows": 72000.0, "event_outflow_total": 0.0,
                "funding_shortfall": 0.0, "tax_phase": "pre_retirement", "tax_mode": "standard",
                "tax_filing_status": "joint", "taxable_income": 70000.0,
                "withdrawal_cash": 0.0, "withdrawal_taxable": 0.0, "withdrawal_trad_ira": 0.0,
                "withdrawal_roth": 0.0, "contribution_trad_ira": 0.0, "contribution_roth": 0.0,
                "contribution_total": 0.0, "contribution_employee_trad_ira": 0.0,
                "contribution_employee_roth": 0.0, "surplus_to_taxable": 0.0,
                "surplus_to_trad_ira": 0.0, "surplus_to_roth": 0.0,
                "employer_match_total": 0.0, "employer_match_person1": 0.0,
                "employer_match_person2": 0.0, "taxable_cost_basis": 50000.0,
                "taxable_unrealized_gain": 50000.0, "roth_contribution_basis": 150000.0,
                "roth_earnings": 0.0, "cash_reserve_target": 40000.0,
            },
        ])
        nominal_df = df.copy()
        nominal_df["total_net_worth"] = 530000.0

        result = ProjectionResult(
            mode="deterministic",
            yearly_df=df,
            summary={},
            simulation={"real_dollar_basis": True},
            nominal_yearly_df=nominal_df,
        )
        with patch("src.charts.load_config", return_value=config):
            with patch("src.charts.resolve_runtime_config", side_effect=lambda c: c):
                with patch("src.charts._build_gantt_chart", return_value="<div>gantt</div>"):
                    with patch("src.charts._build_figure",
                               return_value=_make_mock_figure()):
                        with tempfile.TemporaryDirectory() as tmp:
                            out = Path(tmp) / "test.html"
                            build_chart(result, out)
                            html = out.read_text(encoding="utf-8")

        # When real_dollar_basis is true: nominal chart div and toggle pill present
        assert "nwn-chart-nominal" in html, "nominal chart div should be present"
        assert "nwn-value-toggle" in html, "toggle pill should be present"
        assert "data-nominal" in html, "data-nominal attributes on table cells"
        # Nominal figure stored as JSON
        assert "NWN_NOMINAL_FIGURE" in html
        # Subsidiary chart JSON variables (not old _SCRIPT names)
        assert "NWN_PORTFOLIO_FIGURE" in html
        assert "NWN_LIABILITIES_FIGURE" in html
        assert "NWN_CASH_RESERVE_FIGURE" in html
        # No old-style eval scripts
        assert "NWN_PORTFOLIO_SCRIPT" not in html
        assert "NWN_LIABILITIES_SCRIPT" not in html
        assert "NWN_CASH_RESERVE_SCRIPT" not in html
        # KPI strip and value-basis badge
        assert "nwn-view-real" in html
        assert "nwn-view-nominal" in html
        assert "\U0001f4b0 Real" in html
        assert "\U0001f4ca Nominal" in html
