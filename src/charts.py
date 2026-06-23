"""
charts.py — Generate Plotly HTML chart + tabbed data tables.

Produces a single self-contained HTML file:
  - Top: Plotly projection chart (with Plotly CDN JS)
  - Below: three CSS tabs — Accounts, Cash Flow, Gantt
"""

from html import escape
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

from src.tables import (
    build_accounts_table,
    build_cashflow_table,
    build_simulation_outcomes_table,
    build_tax_table,
    build_portfolio_table,
    build_assumptions_summary,
    build_scenario_parameters_summary,
)
from src.model import (
    EVENT_ICONS,
    LIABILITY_ICONS,
    ProjectionResult,
    get_event_icon,
    load_config,
    resolve_runtime_config,
)

# ── CSS + JS for the tabbed layout ────────────────────────────────────────────
_TABS_CSS = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0 16px 92px; background: #0b1220; color: #e5edf7; }
  body.embedded { padding: 0 0 40px; background: transparent; }
  body.embedded .page-toolbar { display: none; }
  body.embedded .chart-wrap { background: #111827; box-shadow: none; padding: 0; margin: 0 0 8px; border-radius: 10px; overflow: hidden; }
  body.embedded .event-label-controls { margin: 8px 8px 6px; border-radius: 8px; }
  body.embedded .chart-wrap > div[id^="nwn-chart"] { padding: 0 8px 8px; }
  body.embedded .kpi-strip { margin: 0; border-radius: 0; border-left: none; border-right: none; border-top: none; }
  body.embedded .modeling-note { margin: 0 8px 8px; border-radius: 0 0 8px 8px; }
  body.embedded .tabs { margin-top: 8px; }
  body.embedded .gantt-wrap,
  body.embedded .assumptions-wrap,
  body.embedded table.datatable { box-shadow: none; }
  .page-toolbar { position: fixed; right: 18px; bottom: 18px; z-index: 40;
                  display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
  .event-label-controls { display: flex; flex-wrap: wrap; gap: 14px;
                         padding: 8px 10px; border-radius: 10px; border: 1px solid #243142;
                         background: rgba(17,24,39,0.82);
                         font-size: 12px; color: #cbd5e1; margin: 0 6px 8px; }
  .event-label-controls label { display: inline-flex; align-items: center; gap: 7px; cursor: pointer; }
  .event-label-controls input[type='checkbox'] { accent-color: #38bdf8; }
  .toolbar-link { display: inline-block; padding: 10px 14px; border-radius: 999px;
                  border: 1px solid #243142; background: rgba(17,24,39,0.94); color: #e5edf7;
                  text-decoration: none; font-size: 14px; box-shadow: 0 10px 28px rgba(0,0,0,.35); }
  .toolbar-link:hover { border-color: #7dd3fc; }
  .chart-wrap { background: #111827; border-radius: 8px; padding: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,.32); margin-bottom: 16px; }
  .modeling-note { margin: 10px 6px 4px; padding: 10px 12px; border-radius: 8px;
                   border: 1px solid #243142; background: #0f1725; color: #cbd5e1;
                   font-size: 12px; line-height: 1.45; }
  .modeling-note strong { color: #f8fafc; }
  .kpi-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
               border: 1px solid #243142; border-radius: 10px; overflow: hidden;
               background: #0f1725; margin: 4px 4px 12px; }
  .kpi-box { padding: 14px 16px 16px; min-width: 0; }
  .kpi-box + .kpi-box { border-left: 1px solid #243142; }
  .kpi-label { font-size: 12px; line-height: 1.3; color: #9fb2c8; margin-bottom: 8px;
               letter-spacing: 0.01em; }
  .kpi-value { font-size: 29px; line-height: 1.05; font-weight: 700; color: #f8fafc;
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tabs { display: flex; gap: 4px; margin-bottom: 0; border-bottom: 2px solid #243142; }
  .tab-btn { padding: 8px 18px; border: none; background: none; cursor: pointer;
             font-size: 14px; color: #93a4ba; border-bottom: 3px solid transparent;
             margin-bottom: -2px; transition: color .15s; }
  .tab-btn:hover { color: #e5edf7; }
  .tab-btn.active { color: #f8fafc; border-bottom-color: #7dd3fc; font-weight: 600; }
  .tab-panel { display: none; max-width: 100%; }
  .tab-panel.active { display: block; }
  .table-panel { overflow-x: auto; cursor: grab; }
  .table-panel.dragging, .table-panel.dragging * { cursor: grabbing !important; user-select: none; }
  table.datatable { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 13px;
                    background: #111827; border-radius: 6px;
                    box-shadow: 0 8px 24px rgba(0,0,0,.28); }
  table.datatable th, table.datatable td { padding: 6px 10px; text-align: right;
                                           border-bottom: 1px solid #1f2a3a; white-space: nowrap; }
  table.datatable th.rowlabel, table.datatable td.rowlabel { text-align: left;
      min-width: 190px; font-weight: normal; background: #111827; color: #e5edf7; }
  table.datatable thead tr th { background: #182233; font-weight: 600;
                                 border-bottom: 2px solid #2b3a4e; color: #f8fafc; }
  table.datatable thead tr th.rowlabel { background: #182233; }
  table.datatable tr.section th { background: #162030; font-weight: 700;
                                    font-size: 12px; text-transform: uppercase;
                                    letter-spacing: .04em; color: #9fb2c8;
                                   padding: 5px 10px; text-align: left; }
  table.datatable tr.total td, table.datatable tr.total th { font-weight: 700;
      background: #0f1725; border-top: 1px solid #314155; color: #f8fafc; }
  table.datatable tr.sep td, table.datatable tr.sep th { border-top: 2px solid #314155; }
  table.datatable td.neg { color: #f87171; }
  table.datatable td.zero { color: #64748b; text-align: right; }
  table.datatable tr.indent td.rowlabel { padding-left: 24px; }
  table.datatable tr:hover td, table.datatable tr:hover th { background: #162234; }
  .gantt-wrap { background: #111827; border-radius: 6px; padding: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,.28); }
  .portfolio-table-panel { margin-top: 12px; }
  .gantt-empty { color: #93a4ba; padding: 16px; }
  .assumptions-wrap { background: #111827; border-radius: 6px; padding: 12px;
                      box-shadow: 0 8px 24px rgba(0,0,0,.28); }
  .assumptions-note { margin: 2px 2px 12px; color: #9fb2c8; font-size: 12px; }
  .scenario-diff-toolbar { margin: 2px 2px 12px; color: #cbd5e1; font-size: 12px; }
  .scenario-diff-toolbar label { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
  .scenario-diff-toolbar input[type='checkbox'] { accent-color: #14b8a6; }
  .assumptions-note code { color: #e5edf7; background: #0b1220; padding: 1px 5px; border-radius: 4px; }
  .assumptions-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .assumption-card { background: #0f1725; border: 1px solid #243142; border-radius: 10px; overflow: hidden; }
  .assumption-card.filtered-empty { display: none; }
  .assumption-card-wide { grid-column: 1 / -1; }
  .assumption-card h3 { margin: 0; padding: 12px 14px; border-bottom: 1px solid #243142;
                        font-size: 14px; color: #f8fafc; }
  .assumption-subtitle { margin: 0; padding: 10px 14px 0; color: #9fb2c8; font-size: 12px; }
  table.assumptions-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
  table.assumptions-table th, table.assumptions-table td { padding: 9px 14px; border-bottom: 1px solid #1f2a3a; }
  table.assumptions-table thead th { text-align: left; color: #f8fafc; background: #182233; font-weight: 600; }
  table.assumptions-table tbody th { text-align: left; color: #cbd5e1; width: 52%; font-weight: 500; }
  table.assumptions-table tbody td { text-align: left; color: #f8fafc; }
  table.assumptions-table tbody tr:last-child th,
  table.assumptions-table tbody tr:last-child td { border-bottom: none; }
  table.assumptions-table tbody tr.param-diff th,
  table.assumptions-table tbody tr.param-diff td {
    background: rgba(45, 212, 191, 0.12);
    box-shadow: inset 3px 0 0 rgba(45, 212, 191, 0.65);
  }
  table.assumptions-table tbody tr.param-diff th { color: #d1fae5; }
  #panel-scenario-parameters.show-diffs-only table.assumptions-table:not(.always-visible-table) tbody tr:not(.param-diff) {
    display: none;
  }
  #panel-assumptions.show-diffs-only table.assumptions-table tbody tr:not(.param-diff) {
    display: none;
  }
  table.assumptions-people tbody td:first-child { font-weight: 600; }
  @media (max-width: 900px) {
    .kpi-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .kpi-value { font-size: 24px; }
    .assumptions-grid { grid-template-columns: 1fr; }
  }
</style>
"""

_TABS_JS = """
<script>
function resizePlotlyInPanel(panelId) {
  var panel = document.getElementById('panel-' + panelId);
  if (!panel || typeof Plotly === 'undefined') return;
  panel.querySelectorAll('.plotly-graph-div').forEach(function(el) {
    requestAnimationFrame(function() {
      Plotly.Plots.resize(el);
    });
  });
}

function applyResponsiveChartLayout() {
  if (typeof Plotly === 'undefined') return;
  var compact = window.innerWidth <= 900;

  var chart = document.getElementById('nwn-chart');
  if (chart) {
    var fullTickvals = (chart._halFullTickvals || (chart.layout && chart.layout.xaxis && chart.layout.xaxis.tickvals) || []).slice();
    var fullTicktext = (chart._halFullTicktext || (chart.layout && chart.layout.xaxis && chart.layout.xaxis.ticktext) || []).slice();
    if (!chart._halFullTickvals) {
      chart._halFullTickvals = fullTickvals.slice();
    }
    if (!chart._halFullTicktext) {
      chart._halFullTicktext = fullTicktext.slice();
    }
    var compactTicktext = chart._halCompactTicktext || fullTicktext.map(function(label) {
      return String(label).split('<br>')[0];
    });
    chart._halCompactTicktext = compactTicktext.slice();

    Plotly.relayout(chart, compact ? {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': -0.24,
      'legend.yanchor': 'top',
      'legend.font.size': 11,
      'title.font.size': 17,
      'margin.t': 132,
      'margin.b': 92,
      'xaxis.tickvals': chart._halFullTickvals,
      'xaxis.ticktext': chart._halCompactTicktext
    } : {
      'legend.orientation': 'h',
      'legend.x': 1,
      'legend.xanchor': 'right',
      'legend.y': 1.06,
      'legend.yanchor': 'bottom',
      'legend.font.size': 12,
      'title.font.size': 20,
      'margin.t': 140,
      'margin.b': 88,
      'xaxis.tickvals': chart._halFullTickvals,
      'xaxis.ticktext': chart._halFullTicktext
    });
  }

  var portfolio = document.getElementById('nwn-portfolio');
  if (portfolio) {
    Plotly.relayout(portfolio, compact ? {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': -0.30,
      'legend.yanchor': 'top',
      'legend.font.size': 10,
      'title.font.size': 15,
      'margin.t': 72,
      'margin.b': 136
    } : {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': 1.01,
      'legend.yanchor': 'bottom',
      'legend.font.size': 12,
      'title.font.size': 16,
      'margin.t': 78,
      'margin.b': 48
    });
  }

  var gantt = document.getElementById('nwn-gantt');
  if (gantt) {
    Plotly.relayout(gantt, compact ? {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': -0.20,
      'legend.yanchor': 'top',
      'legend.font.size': 10,
      'title.font.size': 16,
      'margin.t': 78,
      'margin.b': 118
    } : {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': 1.01,
      'legend.yanchor': 'bottom',
      'legend.font.size': 12,
      'title.font.size': 18,
      'margin.t': 85,
      'margin.b': 60
    });
  }
}

function switchTab(id) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('btn-' + id).classList.add('active');
  document.getElementById('panel-' + id).classList.add('active');
  resizePlotlyInPanel(id);
}

// Freeze first column + improved horizontal table navigation
document.addEventListener('DOMContentLoaded', function() {
  var params = new URLSearchParams(window.location.search);
  if (params.get('embed') === '1') {
    document.body.classList.add('embedded');
  }

  setTimeout(function() {
    var activeBtn = document.querySelector('.tab-btn.active');
    if (activeBtn) {
      resizePlotlyInPanel(activeBtn.id.replace('btn-', ''));
    }
    applyResponsiveChartLayout();
  }, 0);

  window.addEventListener('resize', function() {
    applyResponsiveChartLayout();
  });

  function isKeyEventText(text) {
    var value = String(text || '');
    return value.indexOf('🎉') !== -1 || value.indexOf('🏛️') !== -1 || value.indexOf('💀') !== -1;
  }

  function applyEventLabelVisibility() {
    var chart = document.getElementById('nwn-chart');
    var showAllToggle = document.getElementById('event-labels-show-all');
    var keepKeyToggle = document.getElementById('event-labels-keep-key');
    if (!chart || !chart.layout || !Array.isArray(chart.layout.annotations) || !showAllToggle || !keepKeyToggle || typeof Plotly === 'undefined') return;

    var showAll = !!showAllToggle.checked;
    var keepKey = !!keepKeyToggle.checked;
    keepKeyToggle.disabled = showAll;

    var updates = {};
    chart.layout.annotations.forEach(function(annotation, idx) {
      if (!annotation || Number(annotation.textangle) !== -90) return;
      var isKey = isKeyEventText(annotation.text);
      var visible = showAll || (keepKey && isKey);
      updates['annotations[' + idx + '].visible'] = visible;
    });

    if (Object.keys(updates).length > 0) {
      Plotly.relayout(chart, updates);
    }
  }

  var showAllEventLabelsToggle = document.getElementById('event-labels-show-all');
  var keepKeyEventLabelsToggle = document.getElementById('event-labels-keep-key');
  if (showAllEventLabelsToggle) {
    showAllEventLabelsToggle.addEventListener('change', applyEventLabelVisibility);
  }
  if (keepKeyEventLabelsToggle) {
    keepKeyEventLabelsToggle.addEventListener('change', applyEventLabelVisibility);
  }
  applyEventLabelVisibility();

  function updateScenarioDiffVisibility() {
    var panel = document.getElementById('panel-scenario-parameters');
    var toggle = document.getElementById('scenario-diff-only-toggle');
    if (!panel || !toggle) return;

    var showOnlyDiffs = !!toggle.checked;
    panel.classList.toggle('show-diffs-only', showOnlyDiffs);
    panel.querySelectorAll('.assumption-card').forEach(function(card) {
      if (!showOnlyDiffs) {
        card.classList.remove('filtered-empty');
        return;
      }
      var hasDiffRow = !!card.querySelector('tr.param-diff');
      var keepVisible = card.classList.contains('keep-visible-in-diff');
      card.classList.toggle('filtered-empty', !(hasDiffRow || keepVisible));
    });
  }

  var diffToggle = document.getElementById('scenario-diff-only-toggle');
  if (diffToggle) {
    diffToggle.addEventListener('change', updateScenarioDiffVisibility);
    updateScenarioDiffVisibility();
  }

  function updateAssumptionsDiffVisibility() {
    var panel = document.getElementById('panel-assumptions');
    var toggle = document.getElementById('assumptions-diff-only-toggle');
    if (!panel || !toggle) return;

    var showOnlyDiffs = !!toggle.checked;
    panel.classList.toggle('show-diffs-only', showOnlyDiffs);
    panel.querySelectorAll('.assumption-card').forEach(function(card) {
      if (!showOnlyDiffs) {
        card.classList.remove('filtered-empty');
        return;
      }
      var hasDiffRow = !!card.querySelector('tr.param-diff');
      var keepVisible = card.classList.contains('keep-visible-in-diff');
      card.classList.toggle('filtered-empty', !(hasDiffRow || keepVisible));
    });
  }

  var assumptionsDiffToggle = document.getElementById('assumptions-diff-only-toggle');
  if (assumptionsDiffToggle) {
    assumptionsDiffToggle.addEventListener('change', updateAssumptionsDiffVisibility);
    updateAssumptionsDiffVisibility();
  }

  document.querySelectorAll('.table-panel').forEach(function(panel) {
    var ticking = false;
    var isDragging = false;
    var dragStartX = 0;
    var dragStartScrollLeft = 0;

    function syncLabels() {
      var scrollX = panel.scrollLeft;
      panel.querySelectorAll('td.rowlabel, th.rowlabel, tr.section th').forEach(function(cell) {
        cell.style.transform = 'translateX(' + scrollX + 'px)';
      });
      ticking = false;
    }

    // Use rAF to sync label shift to the browser paint cycle — eliminates jitter
    panel.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(syncLabels);
        ticking = true;
      }
    });

    // Redirect vertical wheel to horizontal scroll so mouse wheel works over the table
    panel.addEventListener('wheel', function(e) {
      if (e.deltaY !== 0) {
        e.preventDefault();
        panel.scrollLeft += e.deltaY * 5;
      }
    }, { passive: false });

    // Click-and-drag panning on the table body — faster and more natural than the scrollbar thumb
    panel.addEventListener('mousedown', function(e) {
      if (e.button !== 0) return;
      isDragging = true;
      dragStartX = e.clientX;
      dragStartScrollLeft = panel.scrollLeft;
      panel.classList.add('dragging');
      e.preventDefault();
    });

    window.addEventListener('mousemove', function(e) {
      if (!isDragging) return;
      var dx = e.clientX - dragStartX;
      panel.scrollLeft = dragStartScrollLeft - (dx * 1.5);
    });

    window.addEventListener('mouseup', function() {
      if (!isDragging) return;
      isDragging = false;
      panel.classList.remove('dragging');
    });
  });
});
</script>
"""

EVENT_TYPE_COLORS = {
    "EndOfPlan": "rgba(120,120,120,0.75)",
    "Retire": "rgba(74,144,217,0.75)",
    "SocialSecurity": "rgba(62,90,164,0.78)",
    "Expense": "rgba(214,77,77,0.80)",
    "Income": "rgba(79,164,98,0.78)",
    "BuyHome": "rgba(160,120,80,0.78)",
    "SellHome": "rgba(107,142,95,0.82)",
    "NewJob": "rgba(52,152,219,0.78)",
    "CareerBreak": "rgba(243,156,18,0.78)",
    "Education": "rgba(155,89,182,0.78)",
    "Marriage": "rgba(214,103,137,0.78)",
    "SpendingShift": "rgba(45, 212, 191, 0.82)",
    "LiabilityPayoff": "rgba(90,160,120,0.82)",
}

INVESTABLE_SERIES = [
    ("taxable",  "rgba(96,165,250,0.42)",  "Taxable"),
    ("trad_ira", "rgba(74,222,128,0.36)",  "Traditional IRA / 401k"),
    ("roth",     "rgba(251,191,36,0.38)",  "Roth"),
]


def _point_span(year: int) -> tuple[float, float]:
    return year - 0.4, year + 0.4


def _inclusive_span(start_year: int, end_year: int) -> tuple[float, float]:
    return start_year - 0.45, end_year + 0.45


def _person_display(config: dict, person_key: str | None) -> str:
    if not person_key:
        return ""
    return config.get(person_key, {}).get("name", person_key.title())


def _person_keys(config: dict) -> list[str]:
    preferred = [
        key for key in ("person1", "person2")
        if isinstance(config.get(key), dict)
        and any(field in config[key] for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    extras = [
        key for key, value in config.items()
        if key not in preferred
        and isinstance(value, dict)
        and any(field in value for field in ("dob", "life_expectancy", "retirement_year", "ss_start_age"))
    ]
    return preferred + extras


def _format_compact_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    amount = abs(float(value))
    if amount >= 1_000_000:
        scaled = f"{amount / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{sign}${scaled}M"
    if amount >= 1_000:
        scaled = f"{amount / 1_000:.0f}"
        return f"{sign}${scaled}K"
    return f"{sign}${amount:,.0f}"


def _format_percent(value: float) -> str:
    return f"{float(value) * 100.0:.1f}%"


def _first_retirement_event(config: dict) -> dict | None:
    events = [
        e for e in config.get("events", [])
        if e.get("enabled", False) and e.get("type") == "Retire" and e.get("person")
    ]
    if not events:
        return None
    return min(events, key=lambda e: int(e["year"]))


def _retirement_age(config: dict, event: dict | None) -> int | None:
    if not event:
        return None
    person = config.get(event.get("person"), {})
    dob = person.get("dob")
    if not dob:
        return None
    try:
        birth_year = int(str(dob).split("-", 1)[0])
        return int(event["year"]) - birth_year
    except (TypeError, ValueError, KeyError):
        return None


def _age_label_for_year(config: dict, year: int) -> str:
    ages = []
    for person_key in _person_keys(config):
        dob = config.get(person_key, {}).get("dob")
        if not dob:
            continue
        try:
            birth_year = int(str(dob).split("-", 1)[0])
        except (TypeError, ValueError):
            continue
        ages.append(str(int(year) - birth_year))

    if not ages:
        return ""
    if len(ages) == 1:
        return f"({ages[0]})"
    return f"({'/'.join(ages)})"


def _xaxis_tick_spec(config: dict, years: list[int]) -> tuple[list[int], list[str]]:
    if not years:
        return [], []

    tickvals = list(range(int(years[0]), int(years[-1]) + 1, 2))
    if len(years) == 1:
        tickvals = [int(years[0])]

    ticktext = []
    for year in tickvals:
        age_label = _age_label_for_year(config, year)
        ticktext.append(f"{year}<br>{age_label}" if age_label else str(year))
    return tickvals, ticktext


def _build_kpi_summary(
    config: dict,
    projection: pd.DataFrame | ProjectionResult,
) -> str:
    projection_result = _coerce_projection_result(projection)
    df = projection_result.yearly_df
    first_row = df.iloc[0]
    last_row = df.iloc[-1]
    first_retire = _first_retirement_event(config)
    retirement_year = int(first_retire["year"]) if first_retire else None
    retirement_row = None
    if retirement_year is not None:
        match = df[df["year"] == retirement_year]
        if not match.empty:
            retirement_row = match.iloc[0]

    if projection_result.mode == "monte_carlo":
        summary = projection_result.summary
        cards = [
            ("Monte Carlo Success Rate", _format_percent(float(summary.get("success_rate", 0.0)))),
            (
                "Median Net Worth at Retirement",
                _format_compact_currency(float(summary.get("retirement_total_net_worth_p50", retirement_row["total_net_worth"] if retirement_row is not None else 0.0)))
                if retirement_row is not None or summary.get("retirement_total_net_worth_p50") is not None
                else "—",
            ),
            (
                "Median First Failure Year",
                str(summary.get("first_failure_year_p50")) if summary.get("first_failure_year_p50") is not None else "No failure",
            ),
            (
                "Median Net Worth at End",
                _format_compact_currency(float(summary.get("terminal_total_net_worth_p50", last_row["total_net_worth"]))),
            ),
        ]
    elif projection_result.mode == "historical":
        summary = projection_result.summary
        cards = [
            ("Historical Success Rate", _format_percent(float(summary.get("success_rate", 0.0)))),
            (
                "Median Net Worth at Retirement",
                _format_compact_currency(float(summary.get("retirement_total_net_worth_p50", retirement_row["total_net_worth"] if retirement_row is not None else 0.0)))
                if retirement_row is not None or summary.get("retirement_total_net_worth_p50") is not None
                else "—",
            ),
            (
                "Median First Failure Year",
                str(summary.get("first_failure_year_p50")) if summary.get("first_failure_year_p50") is not None else "No failure",
            ),
            (
                "Median Net Worth at End",
                _format_compact_currency(float(summary.get("terminal_total_net_worth_p50", last_row["total_net_worth"]))),
            ),
        ]
    else:
        cards = [
            ("Net Worth (EOY)", _format_compact_currency(first_row["total_net_worth"])),
            (
                "Net Worth at Retirement",
                _format_compact_currency(retirement_row["total_net_worth"]) if retirement_row is not None else "—",
            ),
            (
                "Retirement Age",
                str(_retirement_age(config, first_retire)) if _retirement_age(config, first_retire) is not None else "—",
            ),
            ("Net Worth at End", _format_compact_currency(last_row["total_net_worth"])),
        ]

    boxes = "".join(
        f"<div class='kpi-box'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div></div>"
        for label, value in cards
    )
    return f"<div class='kpi-strip'>{boxes}</div>"


def _build_portfolio_chart(
    df: pd.DataFrame,
    config: dict | None = None,
    projection_result: ProjectionResult | None = None,
) -> str:
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"
    person1_name = str((config or {}).get("person1", {}).get("name", "")).strip() or "Person 1"
    person2_name = str((config or {}).get("person2", {}).get("name", "")).strip() or "Person 2"

    fig = go.Figure()
    if (
        projection_result is not None
        and projection_result.mode == "monte_carlo"
        and projection_result.band_df is not None
        and not projection_result.band_df.empty
    ):
        bands = projection_result.band_df
        years = bands["year"]
        inner_low = bands.get("net_worth_p25")
        inner_high = bands.get("net_worth_p75")
        outer_low = bands.get("net_worth_p10")
        outer_high = bands.get("net_worth_p90")
        median = bands.get("net_worth_p50")

        if outer_low is not None and outer_high is not None:
            fig.add_trace(go.Scatter(
                x=years, y=outer_low, mode="lines", line=dict(width=0),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=years, y=outer_high, mode="lines",
                fill="tonexty", fillcolor="rgba(56,189,248,0.16)",
                line=dict(width=0), name="P10-P90 range",
                hovertemplate="<b>%{x}</b><br>P90 portfolio: $%{y:,.0f}<extra></extra>",
            ))
        if inner_low is not None and inner_high is not None:
            fig.add_trace(go.Scatter(
                x=years, y=inner_low, mode="lines", line=dict(width=0),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=years, y=inner_high, mode="lines",
                fill="tonexty", fillcolor="rgba(125,211,252,0.28)",
                line=dict(width=0), name="P25-P75 range",
                hovertemplate="<b>%{x}</b><br>P75 portfolio: $%{y:,.0f}<extra></extra>",
            ))
        if median is not None:
            fig.add_trace(go.Scatter(
                x=years, y=median,
                mode="lines", name="Median portfolio",
                line=dict(color="#e5edf7", width=2.6),
                hovertemplate="<b>%{x}</b><br>Median portfolio: $%{y:,.0f}<extra></extra>",
            ))

        fig.update_layout(
            font=dict(color=font_color),
            title=dict(text="Projected Investment Portfolio Range", font=dict(size=16)),
            xaxis=dict(
                title="Year",
                tickmode="linear",
                dtick=2,
                ticklabelstandoff=6,
                gridcolor=grid,
                zerolinecolor=grid,
                color=font_color,
            ),
            yaxis=dict(
                title="Portfolio Value (USD)",
                tickformat="$,.0f",
                ticklabelstandoff=6,
                automargin=True,
                gridcolor=grid,
                zerolinecolor=grid,
                color=font_color,
            ),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
            hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
            plot_bgcolor=plot_bg,
            paper_bgcolor=paper_bg,
            height=420,
            margin=dict(l=76, r=24, t=78, b=48),
        )

        portfolio_div = fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id="nwn-portfolio",
        )
        portfolio_note = (
            "<div class='modeling-note'><strong>Portfolio range note:</strong> "
            "Bands show stochastic portfolio ranges by year. The table below reflects the median simulated path.</div>"
        )
        portfolio_table_html = build_portfolio_table(df, config=config)
        return (
            f"<div class='gantt-wrap'>{portfolio_div}</div>"
            f"{portfolio_note}"
            f"<div class='table-panel portfolio-table-panel'>{portfolio_table_html}</div>"
        )

    portfolio_series = [
        ("taxable", "rgba(96,165,250,0.42)", "Taxable"),
    ]
    if {"trad_ira_person1", "trad_ira_person2"}.issubset(df.columns):
        portfolio_series.extend([
            ("trad_ira_person1", "rgba(16,185,129,0.36)", f"Traditional IRA / 401k — {person1_name}"),
            ("trad_ira_person2", "rgba(74,222,128,0.32)", f"Traditional IRA / 401k — {person2_name}"),
        ])
    else:
        portfolio_series.append(("trad_ira", "rgba(74,222,128,0.36)", "Traditional IRA / 401k"))

    if {"roth_person1", "roth_person2"}.issubset(df.columns):
        portfolio_series.extend([
            ("roth_person1", "rgba(245,158,11,0.38)", f"Roth — {person1_name}"),
            ("roth_person2", "rgba(251,191,36,0.36)", f"Roth — {person2_name}"),
        ])
    else:
        portfolio_series.append(("roth", "rgba(251,191,36,0.38)", "Roth"))

    for category, color, label in portfolio_series:
        if category in df.columns and (df[category] != 0).any():
            fig.add_trace(go.Scatter(
                x=df["year"], y=df[category],
                mode="lines", name=label,
                stackgroup="portfolio", fillcolor=color, line=dict(width=0),
                hovertemplate=f"<b>%{{x}}</b><br>{label}: $%{{y:,.0f}}<extra></extra>",
            ))

    portfolio_total = df[["taxable", "trad_ira", "roth"]].sum(axis=1)
    fig.add_trace(go.Scatter(
        x=df["year"], y=portfolio_total,
        mode="lines", name="Total Investable Portfolio",
        line=dict(color="#f8fafc", width=2.2, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Total Investable Portfolio: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Projected Investment Portfolio", font=dict(size=16)),
        xaxis=dict(
            title="Year",
            tickmode="linear",
            dtick=2,
            ticklabelstandoff=6,
            gridcolor=grid,
            zerolinecolor=grid,
            color=font_color,
        ),
        yaxis=dict(
            title="Portfolio Value (USD)",
            tickformat="$,.0f",
            ticklabelstandoff=6,
            automargin=True,
            gridcolor=grid,
            zerolinecolor=grid,
            color=font_color,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        height=420,
        margin=dict(l=76, r=24, t=78, b=48),
    )

    portfolio_div = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id="nwn-portfolio",
    )

    taxable_hidden_note = ""
    if not (df["taxable"] != 0).any():
        taxable_hidden_note = (
            "<div class='modeling-note'><strong>Portfolio display note:</strong> "
            "Taxable/Brokerage is hidden in this chart because its projected value is "
            "$0 in every year of this scenario.</div>"
        )

    portfolio_table_html = build_portfolio_table(df, config=config)
    return (
        f"<div class='gantt-wrap'>{portfolio_div}</div>"
        f"{taxable_hidden_note}"
        f"<div class='table-panel portfolio-table-panel'>{portfolio_table_html}</div>"
    )


def _survivor_visual_year_range(df: pd.DataFrame) -> tuple[int, int] | None:
    survivor_years = df[df["survivor"] == True]["year"]
    if len(survivor_years) == 0:
        return None
    start_year = int(survivor_years.iloc[0]) - 1
    end_year = int(df["year"].iloc[-1])
    return start_year, end_year


def _coerce_projection_result(
    projection: pd.DataFrame | ProjectionResult,
) -> ProjectionResult:
    if isinstance(projection, ProjectionResult):
        return projection
    return ProjectionResult(
        mode="deterministic",
        yearly_df=projection,
        summary={},
        simulation={"mode": "deterministic"},
    )


def _build_gantt_chart(config: dict, df: pd.DataFrame) -> str:
    sim = config["simulation"]
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"
    events = [e for e in config.get("events", []) if e.get("enabled", False)]
    if not events:
        return "<div class='gantt-wrap'><div class='gantt-empty'>No enabled events to display.</div></div>"

    sim_end = sim["end_year"]
    eop_years = {
        e.get("person"): e["year"]
        for e in events
        if e["type"] == "EndOfPlan" and e.get("person")
    }
    retirement_years = {
        person_key: config.get(person_key, {}).get("retirement_year", sim_end)
        for person_key in _person_keys(config)
    }

    items: list[dict] = []

    def add_item(event: dict, start_year: int, end_year: int | None = None):
        person_name = _person_display(config, event.get("person"))
        icon = get_event_icon(event)
        row_label = f"{icon} {event['label']}"
        if end_year is None:
            start_x, end_x = _point_span(start_year)
            years_label = f"{start_year}"
        else:
            start_x, end_x = _inclusive_span(start_year, end_year)
            years_label = f"{start_year}–{end_year}"
        items.append({
            "row": row_label,
            "type": event["type"],
            "label": event["label"],
            "person": person_name or "Household",
            "start_x": start_x,
            "end_x": end_x,
            "start_year": start_year,
            "years_label": years_label,
            "sort_start": start_year,
        })

    for event in events:
        etype = event["type"]
        person = event.get("person")

        if etype in {"EndOfPlan", "Expense", "BuyHome", "SellHome", "Marriage"}:
            add_item(event, event["year"])
        elif etype in {"CareerBreak", "Education"}:
            add_item(event, event["start_year"], event["end_year"])
        elif etype == "Income":
            if event.get("end_year") and event["end_year"] > event["year"]:
                add_item(event, event["year"], event["end_year"])
            else:
                add_item(event, event["year"])
        elif etype == "Retire":
            add_item(event, event["year"], eop_years.get(person, sim_end))
        elif etype == "SocialSecurity":
            add_item(event, event["year"], eop_years.get(person, sim_end))
        elif etype == "NewJob":
            retirement_year = retirement_years.get(person, sim_end)
            final_year = min(eop_years.get(person, sim_end), retirement_year - 1)
            if final_year >= event["year"]:
                add_item(event, event["year"], final_year)
            else:
                add_item(event, event["year"])
        elif etype == "SpendingShift":
            end_year = int(event.get("end_year", sim_end))
            if end_year > event["year"]:
                add_item(event, event["year"], end_year)
            else:
                add_item(event, event["year"])

    # Add liability payoff milestones derived from the projection output
    seen_payoff_labels = set()
    for _, row in df.iterrows():
        labels = row.get("events_active", "")
        if not labels:
            continue
        for label in labels.split(", "):
            if "paid off" not in label or label in seen_payoff_labels:
                continue
            seen_payoff_labels.add(label)
            display_label = label.split(" ", 1)[1] if " " in label else label
            payoff_icon = label.split(" ", 1)[0] if " " in label else LIABILITY_ICONS.get("other", "✅")
            start_x, end_x = _point_span(int(row["year"]))
            items.append({
                "row": f"{payoff_icon} {display_label}",
                "type": "LiabilityPayoff",
                "legend_name": "Liability Payoff",
                "label": display_label,
                "person": "Household",
                "start_x": start_x,
                "end_x": end_x,
                "start_year": int(row["year"]),
                "years_label": str(int(row["year"])),
                "sort_start": int(row["year"]),
            })

    items.sort(key=lambda i: (i["sort_start"], i["person"], i["label"]))
    if not items:
        return "<div class='gantt-wrap'><div class='gantt-empty'>No enabled events to display.</div></div>"

    fig = go.Figure()
    shown_types = set()
    row_order = [item["row"] for item in items]

    for item in items:
        duration = item["end_x"] - item["start_x"]
        legend_name = item.get("legend_name", item["type"])
        fig.add_trace(go.Bar(
            x=[duration],
            base=[item["start_x"]],
            y=[item["row"]],
            orientation="h",
            width=0.21,
            name=legend_name,
            showlegend=legend_name not in shown_types,
            marker=dict(color=EVENT_TYPE_COLORS.get(item["type"], "rgba(120,120,120,0.75)")),
            hovertemplate=(
                f"<b>{item['label']}</b><br>"
                f"Type: {legend_name}<br>"
                f"Person: {item['person']}<br>"
                f"Timing: {item['years_label']}<extra></extra>"
            ),
        ))
        shown_types.add(legend_name)

    survivor_years = df[df["survivor"] == True]["year"]
    survivor_visual_range = _survivor_visual_year_range(df)
    if len(survivor_years) > 0 and survivor_visual_range is not None:
        x0, x1 = survivor_visual_range
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(148,163,184,0.10)",
            line_width=0,
            layer="below",
        )
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=1.0,
            xref="x",
            yref="paper",
            text="👤 Survivor period",
            showarrow=False,
            font=dict(size=10, color="rgba(226,232,240,0.84)"),
            bgcolor="rgba(15,23,37,0.82)",
            borderpad=2,
            yanchor="bottom",
        )

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Event Timeline", font=dict(size=16)),
        barmode="overlay",
        xaxis=dict(
            title="Year",
            tickmode="linear",
            dtick=2,
            ticklabelstandoff=6,
            range=[sim["start_year"] - 0.5, sim_end + 0.5],
            gridcolor=grid,
            zerolinecolor=grid,
            color=font_color,
        ),
        yaxis=dict(
            title="",
            autorange="reversed",
            categoryorder="array",
            categoryarray=row_order,
            automargin=True,
            tickfont=dict(size=12, color=font_color),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        barcornerradius=4,
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        hovermode="closest",
        height=max(180, 6 * len(items) + 36),
        margin=dict(l=104, r=20, t=70, b=36),
    )

    gantt_div = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id="nwn-gantt",
    )
    return f"<div class='gantt-wrap'>{gantt_div}</div>"


def _build_tax_semantics_note() -> str:
    return (
        "<div class='modeling-note'><strong>Tax modeling note:</strong> "
        "Employment income is currently modeled as net cash. "
        "The taxes shown here cover modeled taxable retirement/event inflows "
        "(for example Social Security, taxable income events, and taxable withdrawals), "
        "not a full household tax return.</div>"
    )


def _fmt_pct_text(value) -> str:
    try:
        pct = float(value) * 100.0
    except (TypeError, ValueError):
        return "—"
    text = f"{pct:.1f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _build_simulation_results_panel(projection_result: ProjectionResult) -> str:
    summary = projection_result.summary or {}
    outcomes_df = projection_result.outcomes_df
    if outcomes_df is None or outcomes_df.empty:
        return "<div class='assumptions-wrap'><div class='assumptions-note'>No stochastic simulation outcomes available.</div></div>"

    mode_label = "Monte Carlo" if projection_result.mode == "monte_carlo" else "Historical sequence"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["success_through_year_rate"],
        mode="lines", name="Success through year",
        line=dict(color="#22c55e", width=2.5),
        hovertemplate="<b>%{x}</b><br>Success through year: %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["cumulative_failure_rate"],
        mode="lines", name="Cumulative failure rate",
        line=dict(color="#f87171", width=2.2),
        hovertemplate="<b>%{x}</b><br>Cumulative failure rate: %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["current_failure_trigger_rate"],
        mode="lines", name="Current-year trigger rate",
        line=dict(color="#fbbf24", width=2.0, dash="dot"),
        hovertemplate="<b>%{x}</b><br>Current-year trigger rate: %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(
        font=dict(color="#e5edf7"),
        title=dict(text=f"{mode_label} Outcome Timing", font=dict(size=16)),
        xaxis=dict(title="Year", tickmode="linear", dtick=2, gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.14)", color="#e5edf7"),
        yaxis=dict(title="Probability", tickformat=".0%", gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.14)", color="#e5edf7", range=[0, 1]),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        plot_bgcolor="#0f1725",
        paper_bgcolor="#111827",
        height=420,
        margin=dict(l=64, r=24, t=70, b=56),
    )
    chart_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id="nwn-simulation")
    table_html = build_simulation_outcomes_table(outcomes_df, summary=summary)
    summary_html = (
        "<div class='assumptions-note'>"
        f"{mode_label} outcome detail for the current rendered result path. "
        f"<strong>Success rate:</strong> {_fmt_pct_text(summary.get('success_rate', 0.0))} | "
        f"<strong>Failure mode:</strong> {escape(str(summary.get('failure_mode', '—')))} | "
        f"<strong>Median first failure year:</strong> {escape(str(summary.get('first_failure_year_p50', 'No failure')))}"
        "</div>"
    )
    return (
        "<div class='assumptions-wrap'>"
        f"{summary_html}"
        f"<div class='gantt-wrap'>{chart_html}</div>"
        f"<div class='table-panel portfolio-table-panel'>{table_html}</div>"
        "</div>"
    )


def build_chart(
    projection: pd.DataFrame | ProjectionResult,
    output_path: Path,
    config: dict | None = None,
    scenario=None,
    baseline_config: dict | None = None,
) -> None:
    """
    Generate the Plotly chart figure, build HTML tables, and write
    a single self-contained tabbed HTML page to output_path.
    """
    projection_result = _coerce_projection_result(projection)
    df = projection_result.yearly_df
    config = resolve_runtime_config(config or load_config())
    baseline_config = resolve_runtime_config(baseline_config) if baseline_config is not None else None
    fig = _build_figure(df, config, projection_result=projection_result)

    # Export figure as a standalone div (no full HTML, no duplicate Plotly JS)
    chart_div = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        div_id="nwn-chart",
    )
    kpi_html = _build_kpi_summary(config, projection_result)
    tax_note_html = _build_tax_semantics_note()

    # Build table HTML
    accounts_html  = build_accounts_table(df, config=config)
    cashflow_html  = build_cashflow_table(df, config=config)
    tax_html       = build_tax_table(df)
    simulation_html = (
        _build_simulation_results_panel(projection_result)
        if projection_result.mode in {"monte_carlo", "historical"}
        else ""
    )
    portfolio_html = _build_portfolio_chart(df, config=config, projection_result=projection_result)
    gantt_html     = _build_gantt_chart(config, df)
    assumptions_html = build_assumptions_summary(
        config,
        scenario=scenario,
        baseline_config=baseline_config,
    )
    scenario_params_html = build_scenario_parameters_summary(
        config,
        scenario=scenario,
        baseline_config=baseline_config,
        projection_df=df,
        projection_result=projection_result,
    )

    scenario_slug = getattr(scenario, "slug", None)
    edit_config_href = f"/finances/config/?scenario={scenario_slug}" if scenario_slug else "/finances/config/"

    # Assemble full page
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Net Worth Navigator</title>
  {_TABS_CSS}
</head>
<body>
  <div class="page-toolbar">
    <a class="toolbar-link" href="{edit_config_href}">Edit Config</a>
  </div>
  <div class="chart-wrap">
    {kpi_html}
    {chart_div}
    <div class="event-label-controls" id="event-label-controls">
      <label><input type="checkbox" id="event-labels-show-all" checked> Show all event labels</label>
      <label><input type="checkbox" id="event-labels-keep-key" checked> Keep key labels when hidden</label>
    </div>
    {tax_note_html}
  </div>

  <div class="tabs">
    <button class="tab-btn active" id="btn-accounts"
            onclick="switchTab('accounts')">Accounts</button>
    <button class="tab-btn" id="btn-cashflow"
            onclick="switchTab('cashflow')">Cash Flow</button>
    <button class="tab-btn" id="btn-tax"
            onclick="switchTab('tax')">Tax</button>
    {'<button class="tab-btn" id="btn-simulation" onclick="switchTab(\'simulation\')">Simulation</button>' if simulation_html else ''}
    <button class="tab-btn" id="btn-portfolio"
            onclick="switchTab('portfolio')">Portfolio</button>
    <button class="tab-btn" id="btn-gantt"
            onclick="switchTab('gantt')">Gantt</button>
    <button class="tab-btn" id="btn-assumptions"
            onclick="switchTab('assumptions')">Assumptions</button>
    <button class="tab-btn" id="btn-scenario-parameters"
            onclick="switchTab('scenario-parameters')">Scenario Parameters</button>
  </div>

  <div class="tab-panel table-panel active" id="panel-accounts">
    {accounts_html}
  </div>
  <div class="tab-panel table-panel" id="panel-cashflow">
    {cashflow_html}
  </div>
  <div class="tab-panel table-panel" id="panel-tax">
    {tax_html}
  </div>
  {'<div class="tab-panel assumptions-panel" id="panel-simulation">' + simulation_html + '</div>' if simulation_html else ''}
  <div class="tab-panel gantt-panel" id="panel-portfolio">
    {portfolio_html}
  </div>
  <div class="tab-panel gantt-panel" id="panel-gantt">
    {gantt_html}
  </div>
  <div class="tab-panel assumptions-panel" id="panel-assumptions">
    {assumptions_html}
  </div>
  <div class="tab-panel assumptions-panel" id="panel-scenario-parameters">
    {scenario_params_html}
  </div>

  {_TABS_JS}
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    size_kb = output_path.stat().st_size // 1024
    print(f"  Chart written: {output_path} ({size_kb}KB)")


# ── Figure builder ─────────────────────────────────────────────────────────────

def _build_figure(
    df: pd.DataFrame,
    config: dict,
    projection_result: ProjectionResult | None = None,
) -> go.Figure:
    fig = go.Figure()
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"
    tickvals, ticktext = _xaxis_tick_spec(config, df["year"].astype(int).tolist())

    if (
        projection_result is not None
        and projection_result.mode == "monte_carlo"
        and projection_result.band_df is not None
        and not projection_result.band_df.empty
    ):
        bands = projection_result.band_df
        years = bands["year"]
        total_outer_low = bands.get("total_net_worth_p10")
        total_outer_high = bands.get("total_net_worth_p90")
        total_inner_low = bands.get("total_net_worth_p25")
        total_inner_high = bands.get("total_net_worth_p75")
        total_median = bands.get("total_net_worth_p50")

        if total_outer_low is not None and total_outer_high is not None:
            fig.add_trace(go.Scatter(
                x=years, y=total_outer_low, mode="lines", line=dict(width=0),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=years, y=total_outer_high, mode="lines",
                fill="tonexty", fillcolor="rgba(45,212,191,0.14)",
                line=dict(width=0), name="P10-P90 range",
                hovertemplate="<b>%{x}</b><br>P90 net worth: $%{y:,.0f}<extra></extra>",
            ))
        if total_inner_low is not None and total_inner_high is not None:
            fig.add_trace(go.Scatter(
                x=years, y=total_inner_low, mode="lines", line=dict(width=0),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=years, y=total_inner_high, mode="lines",
                fill="tonexty", fillcolor="rgba(45,212,191,0.28)",
                line=dict(width=0), name="P25-P75 range",
                hovertemplate="<b>%{x}</b><br>P75 net worth: $%{y:,.0f}<extra></extra>",
            ))
        if total_median is not None:
            fig.add_trace(go.Scatter(
                x=years, y=total_median,
                mode="lines", name="Median total net worth",
                line=dict(color="#f8fafc", width=2.8),
                hovertemplate="<b>%{x}</b><br>Median total net worth: $%{y:,.0f}<extra></extra>",
            ))
        if (df["home_equity"] != 0).any():
            fig.add_trace(go.Scatter(
                x=df["year"], y=df["home_equity"],
                mode="lines", name="Median home equity",
                line=dict(color="rgba(237,194,148,0.88)", width=1.8, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Median home equity: $%{y:,.0f}<extra></extra>",
            ))
    else:

        # ── Home equity band (non-liquid) ──────────────────────────────────────────
        if (df["home_equity"] != 0).any():
            fig.add_trace(go.Scatter(
                x=df["year"], y=df["home_equity"],
                mode="lines", name="Home Equity (non-liquid)",
                fill="tozeroy", fillcolor="rgba(217,168,120,0.30)",
                line=dict(color="rgba(237,194,148,0.88)", width=1.8, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Home Equity: $%{y:,.0f}<extra></extra>",
            ))

        # ── Investable stacked area ────────────────────────────────────────────────
        for category, color, label in [
            ("cash",     "rgba(191,219,254,0.42)", "Cash"),
            ("taxable",  "rgba(96,165,250,0.42)",  "Taxable"),
            ("trad_ira", "rgba(74,222,128,0.36)",  "Traditional IRA / 401k"),
            ("roth",     "rgba(251,191,36,0.38)",  "Roth"),
        ]:
            if (df[category] != 0).any():
                fig.add_trace(go.Scatter(
                    x=df["year"], y=df[category],
                    mode="lines", name=label,
                    stackgroup="investable", fillcolor=color, line=dict(width=0),
                    hovertemplate=f"<b>%{{x}}</b><br>{label}: $%{{y:,.0f}}<extra></extra>",
                ))

        # ── Total net worth line ───────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["total_net_worth"],
            mode="lines", name="Total Net Worth",
            line=dict(color="#f8fafc", width=2.5, dash="dash"),
            hovertemplate="<b>%{x}</b><br>Total Net Worth: $%{y:,.0f}<extra></extra>",
        ))

    # ── Survivor period shading ────────────────────────────────────────────────
    survivor_years = df[df["survivor"] == True]["year"]
    survivor_visual_range = _survivor_visual_year_range(df)
    if len(survivor_years) > 0 and survivor_visual_range is not None:
        x0, x1 = survivor_visual_range
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(148,163,184,0.10)", line_width=0)
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=1.0, xref="x", yref="paper",
            text="👤 Survivor period", showarrow=False,
            font=dict(size=10, color="rgba(226,232,240,0.84)"),
            bgcolor="rgba(15,23,37,0.82)", borderpad=2, yanchor="bottom",
        )

    # ── Event annotations — vertical, right of line ────────────────────────────
    events_df = df[df["events_active"] != ""].copy()
    for _, row in events_df.iterrows():
        raw_label = str(row["events_active"])
        label = _wrap_event_annotation(raw_label, per_line=2)
        is_eop = "💀" in raw_label
        fig.add_vline(
            x=row["year"],
            line_dash="dash" if is_eop else "dot",
            line_color="rgba(203,213,225,0.46)" if is_eop else "rgba(125,211,252,0.45)",
            annotation_text=label,
            annotation_position="top right",
            annotation_textangle=-90,
            annotation_font_size=11,
            annotation_bgcolor="rgba(15,23,37,0.60)",
            annotation_borderpad=3,
            annotation_align="right",
            annotation_xanchor="left",
            annotation_yanchor="top",
            annotation_xshift=-2,
        )

    title_text = config.get("display", {}).get("projection_title", "Household Projection")

    # ── Layout ─────────────────────────────────────────────────────────────────
    fig.update_layout(
        font=dict(color=font_color),
        title=dict(
            text=(
                f"{title_text}"
                "<br><sup>Values shown are end-of-year estimates, "
                "anchored to live Monarch balances</sup>"
            ),
            font=dict(size=20),
        ),
        xaxis=dict(title="Year", tickmode="array", tickvals=tickvals, ticktext=ticktext,
                   ticklabelstandoff=6,
                   gridcolor=grid,
                   zerolinecolor=grid,
                   color=font_color),
        yaxis=dict(title="Net Worth (USD)", tickformat="$,.0f",
                   ticklabelstandoff=6,
                   automargin=True,
                   gridcolor=grid,
                   zerolinecolor=grid,
                   color=font_color),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        plot_bgcolor=plot_bg, paper_bgcolor=paper_bg,
        height=680,
        margin=dict(l=80, r=40, t=140, b=88),
    )

    return fig


def _wrap_event_annotation(label: str, per_line: int = 2) -> str:
    """Wrap comma-separated event labels into groups to reduce annotation overflow."""
    parts = [part.strip() for part in str(label).split(",") if part.strip()]
    if len(parts) <= per_line:
        return label
    groups = [parts[i:i + per_line] for i in range(0, len(parts), per_line)]
    return "<br>".join(", ".join(group) for group in groups)

