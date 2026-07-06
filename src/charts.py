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
    build_liabilities_table,
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

# Inline SVG info icon — avoids relying on an emoji font (ℹ️ / U+2139) being
# installed, which was rendering as a fallback glyph ("?") on some Windows
# browser/font configurations (reported in Brave and Edge). Shared by the
# KPI-strip tooltips and the tab-label tooltips.
_INFO_ICON_SVG = (
    "<svg class='help-info-icon' viewBox='0 0 16 16' width='14' height='14' "
    "aria-hidden='true' focusable='false'>"
    "<circle cx='8' cy='8' r='7' fill='none' stroke='currentColor' stroke-width='1.4'/>"
    "<circle cx='8' cy='4.6' r='1.1' fill='currentColor'/>"
    "<rect x='7.1' y='6.8' width='1.8' height='5.2' rx='0.6' fill='currentColor'/>"
    "</svg>"
)

# ── CSS + JS for the tabbed layout ────────────────────────────────────────────
_TABS_CSS = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0 16px 92px; background: #0b1220; color: #e5edf7;
         max-width: 100vw; overflow-x: hidden; }
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
  .zoom-presets { display: flex; align-items: center; gap: 6px;
                  margin: 6px 6px 0; padding: 4px 0; }
  .zoom-preset-label { font-size: 11px; color: #64748b; margin-right: 2px; }
  .zoom-preset-btn { padding: 2px 10px; border-radius: 5px; border: 1px solid #475569;
                     background: #1e293b; color: #94a3b8; cursor: pointer; font-size: 11px;
                     transition: all .15s; line-height: 1.5; }
  .zoom-preset-btn:hover { border-color: #7dd3fc; color: #e2e8f0; }
  .zoom-preset-btn.active { background: #0369a1; border-color: #0284c7; color: #fff; }
  .toolbar-link { display: inline-block; padding: 10px 14px; border-radius: 999px;
                  background: #111827; color: #f8fafc; border: 1px solid #475569;
                  text-decoration: none; font-size: 13px; transition: all .2s; }
  .toolbar-link:hover { border-color: #7dd3fc; }
  .help-mode-toggle { display: inline-flex; align-items: center; justify-content: center;
                      width: 36px; height: 36px; border-radius: 50%; margin-left: 10px;
                      background: #111827; border: 1px solid #475569; color: #94a3b8;
                      cursor: pointer; transition: all .2s; }
  .help-mode-toggle:hover { border-color: #7dd3fc; color: #7dd3fc; }
  .help-mode-toggle.active { background: #0369a1; border-color: #0284c7; color: #fff; }
  .help-icon { font-size: 18px; font-weight: 600; }
  .help-info-icon { display: none; cursor: help; margin-left: 6px; color: #7dd3fc;
                    vertical-align: middle; }
  body.help-mode-active .help-info-icon { display: inline-block; }
  .help-tooltip { position: relative; }
  .help-tooltip .tooltip-content { display: none; position: absolute; bottom: 100%; left: 50%;
                                   transform: translateX(-50%); margin-bottom: 8px; padding: 8px 12px;
                                   background: #1e293b; border: 1px solid #475569; border-radius: 6px;
                                   color: #e2e8f0; font-size: 12px; z-index: 1000;
                                   /* Always wrap with a width capped relative to the viewport, and use
                                      border-box so the cap includes padding/border — otherwise the
                                      rendered box overshoots max-width and can still clip off-screen.
                                      Fixed pixel breakpoints proved unreliable across real mobile widths. */
                                   white-space: normal; width: max-content; box-sizing: border-box;
                                   max-width: min(260px, calc(100vw - 32px));
                                   box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
  .help-tooltip .tooltip-content::after { content: ''; position: absolute; top: 100%; left: 50%;
                                          transform: translateX(-50%); border: 6px solid transparent;
                                          border-top-color: #475569; }
  /* Flip below the icon (JS-toggled) when there isn't room above — e.g. KPI boxes
     pinned near the top of the viewport. */
  .help-tooltip .tooltip-content.tooltip-below { bottom: auto; top: 100%;
                                                 margin-bottom: 0; margin-top: 8px; }
  .help-tooltip .tooltip-content.tooltip-below::after { top: auto; bottom: 100%;
                                                        border-top-color: transparent;
                                                        border-bottom-color: #475569; }
  /* Horizontal clamp (JS-toggled) when centering would push the popup past the
     left/right viewport edge — common for icons near the left/right screen edge
     on narrow mobile layouts. Overrides the centered left/transform above. */
  .help-tooltip .tooltip-content.tooltip-clamp-left { left: 0; transform: none; }
  .help-tooltip .tooltip-content.tooltip-clamp-left::after { left: 16px; transform: none; }
  .help-tooltip .tooltip-content.tooltip-clamp-right { left: auto; right: 0; transform: none; }
  .help-tooltip .tooltip-content.tooltip-clamp-right::after { left: auto; right: 16px; transform: none; }
  /* Hover reveals the tooltip on pointer devices; .tooltip-open (toggled by JS on
     tap) covers touch devices where :hover never fires. */
  body.help-mode-active .help-tooltip:hover .tooltip-content,
  body.help-mode-active .help-tooltip.tooltip-open .tooltip-content { display: block; }
  .welcome-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                     background: rgba(0, 0, 0, 0.85); z-index: 20000;
                     display: flex; align-items: center; justify-content: center;
                     animation: fadeIn 0.3s ease-out; }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  .welcome-content { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                     border: 2px solid #0284c7; border-radius: 12px; padding: 32px 40px;
                     max-width: 620px; width: 90vw; color: #e2e8f0; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }
  .welcome-content h2 { margin: 0 0 16px 0; color: #7dd3fc; font-size: 24px;
                        display: flex; align-items: center; gap: 12px; }
  .welcome-content h2::before { content: '👋'; font-size: 28px; }
  .welcome-content p { margin: 0 0 20px 0; line-height: 1.6; color: #cbd5e1; }
  .welcome-highlights { list-style: none; padding: 0; margin: 0 0 24px 0; }
  .welcome-highlights li { padding: 10px 0; border-bottom: 1px solid #334155;
                           display: flex; align-items: start; gap: 12px; }
  .welcome-highlights li:last-child { border-bottom: none; }
  .welcome-highlights li::before { content: '✓'; color: #10b981; font-weight: 700;
                                   font-size: 18px; flex-shrink: 0; }
  .welcome-actions { display: flex; gap: 12px; justify-content: flex-end; }
  .welcome-btn { padding: 10px 20px; border-radius: 6px; font-size: 14px;
                 font-weight: 600; cursor: pointer; transition: all 0.2s;
                 border: 1px solid transparent; }
  .welcome-btn-primary { background: #0284c7; color: #fff; border-color: #0369a1; }
  .welcome-btn-primary:hover { background: #0369a1; }
  .welcome-btn-secondary { background: transparent; color: #94a3b8;
                           border-color: #475569; }
  .welcome-btn-secondary:hover { border-color: #64748b; color: #cbd5e1; }
  .chart-wrap { background: #111827; border-radius: 8px; padding: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,.32); margin-bottom: 16px; }
  .modeling-note { margin: 10px 6px 4px; padding: 10px 12px; border-radius: 8px;
                   border: 1px solid #243142; background: #0f1725; color: #cbd5e1;
                   font-size: 12px; line-height: 1.45; }
  .modeling-note strong { color: #f8fafc; }
  .kpi-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
               border: 1px solid #243142; border-radius: 10px;
               background: #0f1725; margin: 4px 4px 12px; position: relative; }
  .kpi-box { padding: 14px 16px 16px; min-width: 0; }
  .kpi-box + .kpi-box { border-left: 1px solid #243142; }
  .kpi-box:first-child { border-radius: 10px 0 0 10px; }
  .kpi-box:last-child { border-radius: 0 10px 10px 0; }
  .kpi-label { font-size: 12px; line-height: 1.3; color: #9fb2c8; margin-bottom: 8px;
               letter-spacing: 0.01em; }
  .kpi-value { font-size: 29px; line-height: 1.05; font-weight: 700; color: #f8fafc;
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tabs { display: flex; gap: 4px; margin-bottom: 0; border-bottom: 2px solid #243142;
          overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .tab-btn { padding: 8px 18px; border: none; background: none; cursor: pointer;
             font-size: 14px; color: #93a4ba; border-bottom: 3px solid transparent;
             margin-bottom: -2px; transition: color .15s; flex: 0 0 auto;
             display: flex; align-items: center; }
  .tab-btn:hover { color: #e5edf7; }
  .tab-btn.active { color: #f8fafc; border-bottom-color: #7dd3fc; font-weight: 600; }
  .tab-panel { display: none; max-width: 100%; }
  .tab-panel.active { display: block; }
  /* Tab-label tooltips: .tabs needs overflow-x: auto for mobile horizontal
     scrolling, but setting overflow-x on any axis forces the browser to also
     compute overflow-y as auto (never "visible") on the same box — so a
     normal `position: absolute` tooltip (anchored via the KPI-strip pattern)
     would get silently clipped by .tabs' own scroll box. Tab tooltips use
     `position: fixed` instead, with JS computing exact viewport coordinates,
     so they escape the clipping entirely regardless of .tabs' overflow.
     `pointer-events: none` keeps the tooltip box itself out of the hover/hit
     path — tabs sit close together and a 260px-wide tooltip can visually
     overlap the NEXT tab's button, which would otherwise "steal" hover from
     it and make the previous tooltip appear stuck open. */
  .tab-btn .tooltip-content { position: fixed; bottom: auto; left: auto; transform: none;
                               pointer-events: none; }
  .tab-btn .tooltip-content::after { display: none; }
  .table-panel { position: relative; }
  .sticky-header-wrap { position: sticky; top: 0; z-index: 10;
                        background: #111827; border-bottom: 2px solid #2b3a4e; }
  .sticky-header-wrap .header-only { margin-bottom: 0; border-radius: 6px 6px 0 0; }
  .sticky-header-wrap th.rowlabel { position: sticky; left: 0; z-index: 2; }
  .table-scroll { overflow-x: auto; cursor: grab; }
  .table-scroll .body-only { margin-top: 0; border-radius: 0 0 6px 6px; }
  .header-scroll { overflow-x: scroll; scrollbar-width: none; }
  .header-scroll::-webkit-scrollbar { display: none; }
  .table-scroll.dragging, .table-scroll.dragging * { cursor: grabbing !important; user-select: none; }
  table.datatable { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 13px;
                    background: #111827; border-radius: 6px;
                    box-shadow: 0 8px 24px rgba(0,0,0,.28); overflow: hidden; }
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
  td.year-highlight, th.year-highlight { box-shadow: inset 0 0 0 2px rgba(125, 211, 252, 0.35); background: rgba(125, 211, 252, 0.08); }
  th[data-year] { cursor: pointer; touch-action: manipulation; }
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
    .kpi-box:first-child { border-radius: 10px 0 0 0; }
    .kpi-box:nth-child(2) { border-radius: 0 10px 0 0; border-left: 1px solid #243142; }
    .kpi-box:last-child { border-radius: 0 0 10px 0; }
    .kpi-box:nth-last-child(2):nth-child(odd) { border-radius: 0 0 0 10px; }
    .kpi-value { font-size: 24px; }
    .assumptions-grid { grid-template-columns: 1fr; }
  }
  /* Liabilities tab — payoff callout and note */
  .payoff-cell { text-align: right; font-weight: 600; color: #34d399; white-space: nowrap; }
  .liabilities-note { margin: 10px 6px 4px; padding: 10px 12px; border-radius: 8px;
                      border: 1px solid #243142; background: #0f1725; color: #cbd5e1;
                      font-size: 12px; line-height: 1.45; }
  .liabilities-note strong { color: #f8fafc; }
  tr.liability-type-mortgage th.rowlabel { color: #fca5a5; }
  tr.liability-type-auto th.rowlabel { color: #fcd34d; }
  tr.liability-type-other th.rowlabel { color: #93c5fd; }
  /* Setup status warning for placeholder/sample scenarios */
  .setup-status-warning { margin: 4px 4px 8px; padding: 12px 16px; border-radius: 10px;
                          background: rgba(251, 146, 60, 0.12); border: 1px solid rgba(251, 146, 60, 0.3);
                          color: #fde68a; font-size: 13px; line-height: 1.5; }
  .setup-status-warning strong { color: #fcd34d; }
  .setup-status-warning a { color: #60a5fa; text-decoration: none; border-bottom: 1px solid transparent; }
  .setup-status-warning a:hover { border-bottom-color: #60a5fa; }
  .sample-guide-card { margin: 4px 4px 12px; padding: 20px 24px; border-radius: 10px;
                       background: linear-gradient(135deg, rgba(14, 116, 144, 0.15) 0%, rgba(6, 78, 59, 0.12) 100%);
                       border: 1px solid rgba(45, 212, 191, 0.25); color: #cbd5e1; }
  .sample-guide-card h3 { margin: 0 0 12px 0; color: #5eead4; font-size: 18px; display: flex;
                          align-items: center; gap: 8px; }
  .sample-guide-card p { margin: 0 0 12px 0; line-height: 1.6; color: #cbd5e1; }
  .sample-highlights { list-style: none; padding: 0; margin: 0 0 16px 0; }
  .sample-highlights li { padding: 8px 0; border-bottom: 1px solid rgba(71, 85, 105, 0.4);
                          display: flex; align-items: start; gap: 10px; }
  .sample-highlights li:last-child { border-bottom: none; }
  .sample-highlights li::before { content: '▸'; color: #5eead4; font-size: 16px;
                                  flex-shrink: 0; margin-top: 2px; }
  .sample-guide-tip { background: rgba(14, 165, 233, 0.08); border-left: 3px solid #0ea5e9;
                      padding: 10px 12px; border-radius: 4px; margin: 16px 0 20px 0; }
  .sample-guide-actions { display: flex; gap: 12px; flex-wrap: wrap; }
  .sample-guide-btn { display: inline-block; padding: 10px 18px; border-radius: 6px;
                      font-size: 13px; font-weight: 600; text-decoration: none;
                      transition: all 0.2s; border: 1px solid rgba(100, 116, 139, 0.5);
                      background: rgba(30, 41, 59, 0.6); color: #cbd5e1; }
  .sample-guide-btn:hover { border-color: #5eead4; background: rgba(30, 41, 59, 0.9); }
  .sample-guide-btn-primary { background: rgba(14, 116, 144, 0.3); border-color: #14b8a6;
                              color: #5eead4; }
  .sample-guide-btn-primary:hover { background: rgba(14, 116, 144, 0.5); }
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
      'margin.b': 104,
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
      'margin.b': 100,
      'xaxis.tickvals': chart._halFullTickvals,
      'xaxis.ticktext': chart._halFullTicktext
    });

    // Hide age-labels-on-axis annotations sooner than full compact mode
    var hideAges = window.innerWidth < 1000;
    if (chart.layout && chart.layout.annotations) {
      var ageUpdates = {};
      chart.layout.annotations.forEach(function(a, i) {
        if (a.text && a.text.indexOf('(') === 0) {
          ageUpdates['annotations[' + i + '].visible'] = !hideAges;
        }
      });
      if (Object.keys(ageUpdates).length > 0) {
        Plotly.relayout(chart, ageUpdates);
      }
    }
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

  var simulation = document.getElementById('nwn-simulation');
  if (simulation) {
    Plotly.relayout(simulation, compact ? {
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
      'margin.t': 70,
      'margin.b': 56
    });

  }

  var cashflow = document.getElementById('nwn-cashflow');
  if (cashflow) {
    Plotly.relayout(cashflow, compact ? {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': -0.30,
      'legend.yanchor': 'top',
      'legend.font.size': 10,
      'title.font.size': 14,
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
    Plotly.Plots.resize(cashflow);
  }

  var liabilities = document.getElementById('nwn-liabilities');
  if (liabilities) {
    Plotly.relayout(liabilities, compact ? {
      'legend.orientation': 'h',
      'legend.x': 0.5,
      'legend.xanchor': 'center',
      'legend.y': -0.30,
      'legend.yanchor': 'top',
      'legend.font.size': 10,
      'title.font.size': 14,
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
    Plotly.Plots.resize(liabilities);
  }
}

function switchTab(id, evt) {
  // Guard: the info icon lives inside the clickable tab button (so tab labels
  // can show tooltips); a click on the icon bubbles up and would otherwise
  // also fire this tab switch before the document-level tap-toggle handler
  // ever sees it. Bail out here (without stopping propagation) so the tap
  // toggle for the tooltip still works normally.
  if (evt && evt.target && evt.target.closest && evt.target.closest('.help-info-icon')) {
    return;
  }
  // Switching tabs must also close any pinned (tap-toggled) tooltip. Tab
  // tooltips are `position: fixed` (viewport-anchored, not scoped to the
  // panel), so without this a tooltip left open via tap-toggle on one tab
  // stays floating on screen after switching to a different tab.
  document.querySelectorAll('.help-tooltip.tooltip-open').forEach(function(t) {
    t.classList.remove('tooltip-open');
  });
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
    var visiblePositions = {};

    chart.layout.annotations.forEach(function(annotation, idx) {
      if (!annotation || Number(annotation.textangle) !== -90) return;
      var isKey = isKeyEventText(annotation.text);
      var visible = showAll || (keepKey && isKey);
      updates['annotations[' + idx + '].visible'] = visible;
      if (visible) {
        visiblePositions[annotation.x] = true;
      }
    });

    // Sync vertical-line shapes (vlines) to match annotation visibility
    if (chart.layout.shapes) {
      chart.layout.shapes.forEach(function(shape, idx) {
        if (!shape || shape.type !== 'line' || shape.x0 === undefined || shape.x0 !== shape.x1) return;
        updates['shapes[' + idx + '].visible'] = !!visiblePositions[shape.x0];
      });
    }

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
  // On mobile screens, default to key-events-only (uncheck "Show all")
  if (showAllEventLabelsToggle && window.innerWidth < 768) {
    showAllEventLabelsToggle.checked = false;
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

  document.querySelectorAll('.body-scroll').forEach(function(scrollEl) {
    var ticking = false;
    var isDragging = false;
    var dragStartX = 0;
    var dragStartScrollLeft = 0;

    function syncHeaderScroll() {
      var scrollX = scrollEl.scrollLeft;
      var panel = scrollEl.closest('.table-panel');
      if (panel) {
        var headerScroll = panel.querySelector('.header-scroll');
        if (headerScroll) {
          headerScroll.scrollLeft = scrollX;
          // Pin the rowlabel in place — transform counters the scroll,
          // box-shadow fills the gap where the cell was before translation
          var headerLabel = headerScroll.querySelector('th.rowlabel');
          if (headerLabel) {
            headerLabel.style.transform = 'translateX(' + scrollX + 'px)';
            headerLabel.style.boxShadow = scrollX + 'px 0 0 0 #182233';
          }
        }
      }
    }

    function syncLabels() {
      var scrollX = scrollEl.scrollLeft;
      scrollEl.querySelectorAll('td.rowlabel, th.rowlabel, tr.section th').forEach(function(cell) {
        cell.style.transform = 'translateX(' + scrollX + 'px)';
      });
      syncHeaderScroll();
      ticking = false;
    }

    // Clamp scrollLeft to prevent native scrollbar overshoot past content
    var _clamping = false;
    scrollEl.addEventListener('scroll', function() {
      if (_clamping) return;
      var maxScroll = Math.max(0, scrollEl.scrollWidth - scrollEl.clientWidth);
      if (scrollEl.scrollLeft > maxScroll) {
        _clamping = true;
        scrollEl.scrollLeft = maxScroll;
        _clamping = false;
      }
    });

    // Use rAF to sync label shift to the browser paint cycle — eliminates jitter
    scrollEl.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(syncLabels);
        ticking = true;
      }
    });

    // Redirect vertical wheel to horizontal scroll only when the table has overflow
    scrollEl.addEventListener('wheel', function(e) {
      if (e.deltaY !== 0) {
        var canScroll = scrollEl.scrollWidth > scrollEl.clientWidth;
        if (!canScroll) return;  // table fits — let page scroll normally
        var atLeft = scrollEl.scrollLeft <= 0;
        var atRight = scrollEl.scrollLeft >= scrollEl.scrollWidth - scrollEl.clientWidth - 1;
        // At an edge — only consume the wheel if it would scroll toward content
        if ((e.deltaY < 0 && atLeft) || (e.deltaY > 0 && atRight)) return;
        e.preventDefault();
        scrollEl.scrollLeft += e.deltaY * 5;
      }
    }, { passive: false });

    // Click-and-drag panning on the table body — faster and more natural than the scrollbar thumb
    scrollEl.addEventListener('mousedown', function(e) {
      if (e.button !== 0) return;
      isDragging = true;
      dragStartX = e.clientX;
      dragStartScrollLeft = scrollEl.scrollLeft;
      scrollEl.classList.add('dragging');
      e.preventDefault();
    });

    window.addEventListener('mousemove', function(e) {
      if (!isDragging) return;
      var dx = e.clientX - dragStartX;
      scrollEl.scrollLeft = dragStartScrollLeft - (dx * 1.5);
    });

    window.addEventListener('mouseup', function() {
      if (!isDragging) return;
      isDragging = false;
      scrollEl.classList.remove('dragging');
    });
  });

  // Click a year header to highlight that column across all tables
  // Uses event delegation — works on desktop and mobile regardless of
  // when elements are added to the DOM or what scroll containers they're in.
  var _lastYearClick = { col: null, time: 0 };

  function clearAllHighlights() {
    document.querySelectorAll('.year-highlight').forEach(function(cell) {
      cell.classList.remove('year-highlight');
    });
  }

  // Click on year header → toggle column highlight
  document.addEventListener('click', function(e) {
    var th = e.target.closest('th[data-year]');
    if (!th) return;
    var col = th.getAttribute('data-col');
    if (!col) return;

    // Double-click / double-tap → deselect all
    var now = Date.now();
    if (col === _lastYearClick.col && now - _lastYearClick.time < 500) {
      clearAllHighlights();
      _lastYearClick = { col: null, time: 0 };
      return;
    }
    _lastYearClick = { col: col, time: now };

    var active = th.classList.toggle('year-highlight');
    document.querySelectorAll('[data-col="' + col + '"]').forEach(function(cell) {
      cell.classList.toggle('year-highlight', active);
    });
  });

  // Click on rowlabel header ("Account") → deselect all
  document.addEventListener('click', function(e) {
    var th = e.target.closest('th.rowlabel[data-col="0"]');
    if (!th) return;
    clearAllHighlights();
  });

  // Escape key → deselect all
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') clearAllHighlights();
  });
  
  // Help mode toggle
  var helpModeBtn = document.getElementById('help-mode-toggle');
  if (helpModeBtn) {
    // Restore help mode state from localStorage
    var helpModeActive = localStorage.getItem('nwn-help-mode') === 'true';
    if (helpModeActive) {
      document.body.classList.add('help-mode-active');
      helpModeBtn.classList.add('active');
    }
    
    helpModeBtn.addEventListener('click', function() {
      var isActive = document.body.classList.toggle('help-mode-active');
      helpModeBtn.classList.toggle('active', isActive);
      localStorage.setItem('nwn-help-mode', isActive ? 'true' : 'false');
    });
  }
  
  // Listen for help mode messages from parent (shell page iframe communication)
  window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'toggle-help-mode') {
      var isActive = event.data.active;
      document.body.classList.toggle('help-mode-active', isActive);
      if (helpModeBtn) {
        helpModeBtn.classList.toggle('active', isActive);
      }
    }
  });

  // Tap-to-toggle tooltips — CSS :hover never fires on touch devices, so tapping
  // an info icon toggles a .tooltip-open class instead. Tapping elsewhere closes it.
  document.addEventListener('click', function(e) {
    var icon = e.target.closest('.help-info-icon');
    if (icon) {
      var tooltip = icon.closest('.help-tooltip');
      if (!tooltip) return;
      var wasOpen = tooltip.classList.contains('tooltip-open');
      document.querySelectorAll('.help-tooltip.tooltip-open').forEach(function(t) {
        t.classList.remove('tooltip-open');
      });
      if (!wasOpen) {
        tooltip.classList.add('tooltip-open');
        positionTooltip(tooltip);
      }
      e.stopPropagation();
      return;
    }
    if (!e.target.closest('.help-tooltip')) {
      document.querySelectorAll('.help-tooltip.tooltip-open').forEach(function(t) {
        t.classList.remove('tooltip-open');
      });
    }
  });

  // Flip the tooltip below its icon when there isn't room above, and clamp it
  // horizontally when centering would push it past the left/right edge. This
  // must use LOCAL coordinates (plain getBoundingClientRect(), no parent/frame
  // compensation): when this page is embedded in the shell's iframe, the iframe
  // clips its own painted content to its own box regardless of how much visual
  // room the parent page has above/beside it — so "is there room" is answered
  // relative to this document's own viewport, not the outer browser window.
  function positionTooltip(tooltip) {
    var content = tooltip.querySelector('.tooltip-content');
    if (!content) return;
    // Anchor is `tooltip` itself (.help-tooltip, position:relative is the CSS
    // anchor for the absolutely-positioned .tooltip-content) — not the icon,
    // which sits at an offset within it.
    var rect = tooltip.getBoundingClientRect();

    // Tab-label tooltips are `position: fixed` (see CSS comment on
    // `.tab-btn .tooltip-content`) because `.tabs` needs `overflow-x: auto`
    // for mobile scrolling, and that forces `overflow-y` to also clip
    // (never `visible`) on the same box — a normal absolutely-positioned
    // tooltip anchored inside `.tabs` would be cut off. Fixed tooltips are
    // NOT positioned by the CSS bottom/left/transform rules (those are
    // relative-to-anchor, meaningless for `position: fixed`, which is
    // relative to the viewport) — compute and set explicit pixel
    // coordinates here instead.
    var isFixed = getComputedStyle(content).position === 'fixed';
    if (isFixed) {
      var tooltipHeight = content.offsetHeight || 40;
      var tooltipWidth = content.offsetWidth || 260;
      var showBelow = rect.top < tooltipHeight + 16;
      var top = showBelow ? rect.bottom + 8 : rect.top - tooltipHeight - 8;
      var left = rect.left + rect.width / 2 - tooltipWidth / 2;
      left = Math.max(8, Math.min(left, window.innerWidth - tooltipWidth - 8));
      content.style.top = top + 'px';
      content.style.left = left + 'px';
      return;
    }

    var estimatedTooltipHeight = content.offsetHeight || 90;
    content.classList.toggle('tooltip-below', rect.top < estimatedTooltipHeight + 16);

    var estimatedTooltipWidth = content.offsetWidth || 260;
    var anchorCenter = rect.left + rect.width / 2;
    var halfWidth = estimatedTooltipWidth / 2;
    content.classList.remove('tooltip-clamp-left', 'tooltip-clamp-right');
    if (anchorCenter - halfWidth < 8) {
      content.classList.add('tooltip-clamp-left');
    } else if (anchorCenter + halfWidth > window.innerWidth - 8) {
      content.classList.add('tooltip-clamp-right');
    }
  }

  document.querySelectorAll('.help-tooltip').forEach(function(tooltip) {
    tooltip.addEventListener('mouseenter', function() { positionTooltip(tooltip); });
  });

  // Fixed-position tooltips (tab labels) are pinned to viewport coordinates
  // computed once when they open, so without this they visibly detach from
  // their anchor as soon as the page scrolls underneath them. Reposition
  // whichever fixed tab tooltip is currently visible (hover on desktop, or
  // `.tooltip-open` tap-toggle on touch) on every scroll — capture phase so
  // it also fires for scrollable ancestors, not just the window (e.g. a
  // table's own horizontal/vertical scroll container).
  function repositionVisibleFixedTooltips() {
    document.querySelectorAll('.tab-btn.help-tooltip').forEach(function(tooltip) {
      if (tooltip.matches(':hover') || tooltip.classList.contains('tooltip-open')) {
        positionTooltip(tooltip);
      }
    });
  }
  window.addEventListener('scroll', repositionVisibleFixedTooltips, true);
  window.addEventListener('resize', repositionVisibleFixedTooltips);
  
  // First-time welcome overlay — only shown directly here on standalone loads.
  // When embedded in the shell page's iframe, position:fixed centers within the
  // iframe's own (often much taller than viewport) box rather than what's visible
  // on screen, so delegate display to the parent shell instead (see postMessage below).
  var hasSeenWelcome = localStorage.getItem('nwn-welcome-seen') === 'true';
  if (!hasSeenWelcome) {
    if (document.body.classList.contains('embedded') && window.parent !== window) {
      window.parent.postMessage({ type: 'show-welcome-overlay' }, '*');
    } else {
      showWelcomeOverlay();
    }
  }
  
  function showWelcomeOverlay() {
    var overlay = document.createElement('div');
    overlay.className = 'welcome-overlay';
    
    var content = document.createElement('div');
    content.className = 'welcome-content';
    
    content.innerHTML = `
      <h2>Welcome to Your Retirement Projection!</h2>
      <p>Here's a quick tour of the key features:</p>
      <ul class="welcome-highlights">
        <li><strong>Your chart shows net worth over time</strong> — Hover over any point to see details</li>
        <li><strong>Click year columns in tables</strong> to highlight that year across all data</li>
        <li><strong>Switch tabs below</strong> to explore detailed breakdowns (Accounts, Cash Flow, Tax, etc.)</li>
        <li><strong>Need help?</strong> Click the <strong>?</strong> button to enable contextual tooltips</li>
      </ul>
      <div class="welcome-actions">
        <button class="welcome-btn welcome-btn-secondary" id="welcome-later">Remind me later</button>
        <button class="welcome-btn welcome-btn-primary" id="welcome-dismiss">Got it, don't show again</button>
      </div>
    `;
    
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    
    document.getElementById('welcome-dismiss').addEventListener('click', function() {
      localStorage.setItem('nwn-welcome-seen', 'true');
      document.body.removeChild(overlay);
    });
    
    document.getElementById('welcome-later').addEventListener('click', function() {
      document.body.removeChild(overlay);
    });
    
    // Close on background click
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
      }
    });
  }

  // ── Zoom preset buttons ─────────────────────────────────────────
  var _fullYearRange = null;
  function _captureFullRange() {
    if (_fullYearRange !== null) return;
    var chart = document.getElementById('nwn-chart');
    if (!chart || !chart.layout || !chart.layout.xaxis || typeof Plotly === 'undefined') return;
    var tv = chart.layout.xaxis.tickvals;
    if (tv && tv.length >= 2) {
      _fullYearRange = [Math.min.apply(null, tv), Math.max.apply(null, tv)];
    }
  }
  _captureFullRange();
  window.zoomToYears = function zoomToYears(chartId, btn, rangeYears) {
    var chart = document.getElementById(chartId);
    if (!chart || !chart.layout || !chart.layout.xaxis || typeof Plotly === 'undefined') return;

    // Ensure full range is captured
    _captureFullRange();
    if (_fullYearRange === null) return;

    // Deactivate all preset buttons in this container, activate the clicked one
    var container = btn.closest('.zoom-presets');
    if (container) {
      container.querySelectorAll('.zoom-preset-btn').forEach(function(b) { b.classList.remove('active'); });
    }
    btn.classList.add('active');

    if (rangeYears === null) {
      // Full range — reset
      Plotly.relayout(chart, {'xaxis.range': _fullYearRange});
    } else {
      var startYear = _fullYearRange[0];
      var endYear = Math.min(startYear + rangeYears - 1, _fullYearRange[1]);
      Plotly.relayout(chart, {'xaxis.range': [startYear - 0.5, endYear + 0.5]});
    }
  };

  // ── Clamp zoom-out to full data range ────────────────────────────
  var _nwnChart = document.getElementById('nwn-chart');
  if (_nwnChart && typeof Plotly !== 'undefined') {
    _nwnChart.on('plotly_relayout', function(eventData) {
      // Skip events that don't have a manual range (autorange, full reset)
      if (_fullYearRange === null) return;
      if (!_nwnChart.layout || !_nwnChart.layout.xaxis) return;
      if (_nwnChart.layout.xaxis.autorange) return;
      var r = _nwnChart.layout.xaxis.range;
      if (!r || r.length < 2) return;
      var clamped = false;
      var lo = r[0], hi = r[1];
      if (lo < _fullYearRange[0]) { lo = _fullYearRange[0]; clamped = true; }
      if (hi > _fullYearRange[1]) { hi = _fullYearRange[1]; clamped = true; }
      if (clamped) {
        _nwnChart._halClamping = true;
        Plotly.relayout(_nwnChart, {'xaxis.range': [lo, hi]});
      }
    });
  }
});
</script>
"""

# ── Sticky header wrapper ────────────────────────────────────────────────────

import re as _re


def _wrap_table_with_sticky_header(
    table_html: str,
    label_width: int = 210,
    year_width: int = 130,
) -> str:
    """Split a datatable into sticky header + scrollable body.

    Extracts <thead> and <tbody>, counts year columns, and generates
    matching <colgroup> width declarations so ``table-layout: fixed``
    keeps both header and body tables aligned identically.

    Returns the full HTML with the table portion wrapped in
    .sticky-header-wrap + .table-scroll, preserving any non-table
    content that appears before or after the <table> element.
    """
    # Find the <table> element boundaries — use the first </table> after
    # the opening tag (some callers emit multiple tables, e.g. tax table
    # plus a summary card table).
    table_start = table_html.find("<table")
    if table_start == -1:
        return f'<div class="table-scroll">{table_html}</div>'

    table_end = table_html.find("</table>", table_start)
    if table_end == -1:
        return f'<div class="table-scroll">{table_html}</div>'

    prefix = table_html[:table_start]
    table_part = table_html[table_start : table_end + len("</table>")]
    suffix = table_html[table_end + len("</table>") :]

    # Extract thead and tbody
    thead_m = _re.search(r"<thead>(.*?)</thead>", table_part, _re.DOTALL)
    tbody_m = _re.search(r"<tbody>(.*?)</tbody>", table_part, _re.DOTALL)
    if not thead_m or not tbody_m:
        return f'{prefix}<div class="table-scroll">{table_part}</div>{suffix}'

    thead_inner = thead_m.group(1)
    tbody_inner = tbody_m.group(1)

    # Count year columns (every <th> with a data-year attribute)
    n_year_cols = len(_re.findall(r"<th[^>]*data-year", thead_inner))
    if n_year_cols == 0:
        n_year_cols = 10  # safety fallback

    # Build colgroup
    col_parts = [f'<col style="width:{label_width}px;">']
    col_parts.extend(
        [f'<col style="width:{year_width}px;">' for _ in range(n_year_cols)]
    )
    colgroup = f"<colgroup>{''.join(col_parts)}</colgroup>"

    total_width = label_width + n_year_cols * year_width

    sticky = (
        f'<div class="sticky-header-wrap">'
        f'<div class="table-scroll header-scroll">'
        f'<table class="datatable header-only"'
        f' style="table-layout:fixed;min-width:{total_width}px;margin-bottom:0;"'
        f">{colgroup}<thead>{thead_inner}</thead></table>"
        f"</div>"
        f"</div>"
        f'<div class="table-scroll body-scroll">'
        f'<table class="datatable body-only"'
        f' style="table-layout:fixed;min-width:{total_width}px;"'
        f">{colgroup}<tbody>{tbody_inner}</tbody></table>"
        f"</div>"
    )

    return prefix + sticky + suffix


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
    "ContributionChange": "rgba(129, 140, 248, 0.82)",
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
        ticktext.append(str(year))
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
            ("Probability of Success", _format_percent(float(summary.get("probability_of_success", summary.get("success_rate", 0.0))))),
            (
                "Probability of Spending Shortfall",
                _format_percent(float(summary.get("probability_of_spending_shortfall", 0.0))),
            ),
            (
                "Median Terminal Net Worth",
                _format_compact_currency(float(summary.get("median_terminal_net_worth", summary.get("terminal_total_net_worth_p50", last_row["total_net_worth"])))),
            ),
            (
                "Worst-Decile Terminal Net Worth",
                _format_compact_currency(float(summary.get("worst_decile_terminal_net_worth", summary.get("terminal_total_net_worth_p10", last_row["total_net_worth"])))),
            ),
        ]
    elif projection_result.mode == "historical":
        summary = projection_result.summary
        cards = [
            ("Probability of Success", _format_percent(float(summary.get("probability_of_success", summary.get("success_rate", 0.0))))),
            (
                "Probability of Spending Shortfall",
                _format_percent(float(summary.get("probability_of_spending_shortfall", 0.0))),
            ),
            (
                "Median Terminal Net Worth",
                _format_compact_currency(float(summary.get("median_terminal_net_worth", summary.get("terminal_total_net_worth_p50", last_row["total_net_worth"])))),
            ),
            (
                "Worst-Decile Terminal Net Worth",
                _format_compact_currency(float(summary.get("worst_decile_terminal_net_worth", summary.get("terminal_total_net_worth_p10", last_row["total_net_worth"])))),
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

    # Build tooltip tuples: (label, value, tooltip_text)
    tooltip_map = {
        "Net Worth (EOY)": "Your household's total assets minus liabilities at the start of the projection.",
        "Net Worth at Retirement": "Your projected net worth in the year you retire (when wages stop).",
        "Retirement Age": "The age of the first person to retire in your household.",
        "Net Worth at End": f"Your projected net worth at the end of the plan (year {config.get('simulation', {}).get('end_year', 'end of plan')}).",
        "Probability of Success": "The percentage of Monte Carlo simulations where your net worth stayed above zero throughout the plan.",
        "Probability of Spending Shortfall": "The percentage of simulations where spending had to be reduced to avoid running out of money.",
        "Median Terminal Net Worth": "The middle (50th percentile) ending net worth across all Monte Carlo simulations.",
        "Worst-Decile Terminal Net Worth": "The 10th percentile ending net worth — 90% of simulations ended with more than this amount."
    }
    
    # Inline SVG info icon — see module-level _INFO_ICON_SVG for rationale.
    info_icon_svg = _INFO_ICON_SVG

    boxes = "".join(
        f"<div class='kpi-box help-tooltip'>"
        f"<div class='kpi-label'>{label}"
        f"{info_icon_svg}"
        f"<span class='tooltip-content'>{tooltip_map.get(label, '')}</span>"
        f"</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"</div>"
        for label, value in cards
    )
    return f"<div class='kpi-strip'>{boxes}</div>"


def _build_cashflow_chart(df: pd.DataFrame, config: dict | None = None) -> str:
    """Annual Cash Flow chart: income, spending, and net flow per year.
    Modeled after the Compare page's cash flow graph for single-scenario display."""
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"

    income = df["person1_income"].fillna(0) + df["person2_income"].fillna(0) + df["freed_payments"].fillna(0)
    spending = df["annual_spend"].abs()
    net_flow = income - spending

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["year"], y=income, mode="lines", name="Total Income",
        line=dict(color="#34d399", width=1.8),
        hovertemplate="Income: %{y:$,.0f}<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        x=df["year"], y=spending, mode="lines", name="Total Spending",
        line=dict(color="#f87171", width=1.8, dash="dash"),
        opacity=0.70,
        hovertemplate="Spending: %{y:$,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=df["year"], y=net_flow, mode="lines", name="Net Flow",
        fill="tozeroy", fillcolor="rgba(52, 211, 153, 0.10)",
        line=dict(color="#e5edf7", width=2.2),
        hovertemplate="Net Flow: %{y:$,.0f}<extra></extra>",
    ))

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Annual Cash Flow (Income vs Spending)", font=dict(size=16)),
        xaxis=dict(
            title="Year", tickmode="linear", dtick=2,
            ticklabelstandoff=6, gridcolor=grid, zerolinecolor=grid, color=font_color,
        ),
        yaxis=dict(
            title="Amount (USD)", tickformat="$,.0f",
            ticklabelstandoff=6, automargin=True,
            fixedrange=True,
            gridcolor=grid, color=font_color,
            zeroline=True, zerolinecolor="rgba(148,163,184,0.35)", zerolinewidth=1,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#7dd3fc", font_color="#f8fafc"),
        plot_bgcolor=plot_bg, paper_bgcolor=paper_bg,
        height=420,
        margin=dict(l=76, r=24, t=78, b=48),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="nwn-cashflow",
                       config=dict(scrollZoom=True))


def _build_liabilities_chart(df: pd.DataFrame, config: dict | None = None) -> str:
    """Debt payoff trajectory chart: one line per liability, declining to zero."""
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"

    liab_colors = ["#f87171", "#fbbf24", "#60a5fa", "#a78bfa", "#34d399", "#f472b6"]
    fig = go.Figure()
    years = df["year"].astype(int).tolist()

    if config is None:
        config = {}
    liability_configs = config.get("liabilities", [])

    for idx, lib in enumerate(liability_configs):
        name = lib["name"]
        slug = name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
        col = f"liability_{slug}_balance"
        if col not in df.columns:
            continue

        balances = df[col].fillna(0).tolist()

        # Find payoff year and cap trace there so the line
        # stops instead of continuing flat at $0
        payoff_year = None
        payoff_idx = None
        for i, (y, bal) in enumerate(zip(years, balances)):
            if bal <= 0 and payoff_year is None:
                payoff_year = y
                payoff_idx = i
            if payoff_idx is not None and i > payoff_idx:
                balances[i] = None  # null beyond payoff → line stops

        color = liab_colors[idx % len(liab_colors)]

        fig.add_trace(go.Scatter(
            x=years, y=balances,
            mode="lines",
            name=name,
            line=dict(color=color, width=2.4),
            fill="tozeroy",
            fillcolor=f"rgba{_hex_to_rgba(color, 0.08)}",
            hovertemplate=f"{name}: %{{y:$,.0f}}<extra></extra>",
        ))

        if payoff_year:
            fig.add_annotation(
                x=payoff_year,
                y=0,
                text=f"✓ {name} paid off",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowcolor=color,
                ax=0,
                ay=-48,
                font=dict(size=11, color=color),
                bgcolor="rgba(17,24,39,0.85)",
                borderpad=3,
                bordercolor=color,
            )

    # Horizontal zero line
    fig.add_hline(
        y=0,
        line=dict(color="rgba(148,163,184,0.35)", width=1, dash="dash"),
    )

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Debt Payoff Trajectory", font=dict(size=16)),
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
            title="Remaining Balance (USD)",
            tickformat="$,.0f",
            ticklabelstandoff=6,
            automargin=True,
            fixedrange=True,
            gridcolor=grid,
            color=font_color,
            zeroline=True,
            zerolinecolor="rgba(148,163,184,0.35)",
            zerolinewidth=1,
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#7dd3fc", font_color="#f8fafc"),
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        height=420,
        margin=dict(l=76, r=24, t=78, b=48),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="nwn-liabilities",
                       config=dict(scrollZoom=True))


def _build_cash_reserve_chart(df: pd.DataFrame, config: dict | None = None) -> str:
    """Cash balance vs phase-appropriate target chart."""
    paper_bg = "#111827"
    plot_bg = "#0f1725"
    grid = "rgba(148,163,184,0.14)"
    font_color = "#e5edf7"

    years = df["year"].astype(int).tolist()
    cash_balances = df["cash"].fillna(0).tolist()

    # Phase-aware cash targets
    wp = config.get("withdrawal_policy", {})
    targets = {
        "pre_retirement": float(wp.get("accumulation_cash_target", 40000)),
        "retirement": float(wp.get("retirement_cash_target", 50000)),
        "survivor": float(wp.get("survivor_cash_target", 30000)),
    }
    phase_map = config.get("tax_phase", {})

    # Build per-year target from tax_phase column
    cash_target = []
    phase_labels: list[tuple[int, str]] = []
    prev_phase = None
    for i, row in df.iterrows():
        phase = str(row.get("tax_phase", "pre_retirement")).strip().lower()
        if phase not in targets:
            phase = "pre_retirement"
        cash_target.append(targets[phase])
        if phase != prev_phase:
            phase_labels.append((int(row["year"]), phase))
            prev_phase = phase

    fig = go.Figure()

    # Cash balance trace
    fig.add_trace(go.Scatter(
        x=years, y=cash_balances,
        mode="lines",
        name="Cash Balance",
        line=dict(color="#7dd3fc", width=2.4),
        fill="tozeroy",
        fillcolor="rgba(125,211,252,0.06)",
        hovertemplate="Cash Balance: %{y:$,.0f}<extra></extra>",
    ))

    # Target stepped line
    fig.add_trace(go.Scatter(
        x=years, y=cash_target,
        mode="lines",
        name="Cash Target",
        line=dict(color="#fbbf24", width=1.8, dash="dash"),
        hovertemplate="Target: %{y:$,.0f}<extra></extra>",
    ))

    # Highlight below-target years with a third trace
    below_years = []
    below_balances = []
    for y, bal, tgt in zip(years, cash_balances, cash_target):
        if bal < tgt:
            below_years.append(y)
            below_balances.append(bal)
        else:
            below_years.append(y)
            below_balances.append(None)

    fig.add_trace(go.Scatter(
        x=years, y=below_balances,
        mode="lines",
        name="Below Target",
        line=dict(color="#f87171", width=2.4),
        fill="tozeroy",
        fillcolor="rgba(248,113,113,0.10)",
        connectgaps=False,
        hovertemplate="Cash Balance: %{y:$,.0f} ⚠ below target<extra></extra>",
    ))

    # Phase boundary annotations
    phase_label_map = {"pre_retirement": "Accumulation", "retirement": "Retirement", "survivor": "Survivor"}
    for yr, phase in phase_labels:
        lbl = phase_label_map.get(phase, phase)
        fig.add_vline(
            x=yr,
            line=dict(color="rgba(148,163,184,0.25)", width=1, dash="dot"),
            annotation_text=lbl,
            annotation_position="top right",
            annotation_font=dict(size=11, color="#9fb2c8"),
        )

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Cash Reserve vs Target", font=dict(size=16)),
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
            title="Cash (USD)",
            tickformat="$,.0f",
            ticklabelstandoff=6,
            automargin=True,
            fixedrange=True,
            gridcolor=grid,
            color=font_color,
            zeroline=True,
            zerolinecolor="rgba(148,163,184,0.35)",
            zerolinewidth=1,
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#7dd3fc", font_color="#f8fafc"),
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        height=420,
        margin=dict(l=76, r=24, t=78, b=48),
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id="nwn-cash-reserve",
                       config=dict(scrollZoom=True))


def _build_cash_reserve_summary(df: pd.DataFrame, config: dict | None = None) -> str:
    """Compact summary card for Cash Reserve tab."""
    wp = config.get("withdrawal_policy", {}) if config else {}
    targets = {
        "pre_retirement": float(wp.get("accumulation_cash_target", 40000)),
        "retirement": float(wp.get("retirement_cash_target", 50000)),
        "survivor": float(wp.get("survivor_cash_target", 30000)),
    }
    phase_label_map = {"pre_retirement": "Accumulation", "retirement": "Retirement", "survivor": "Survivor"}

    rows_html = []
    for phase in ["pre_retirement", "retirement", "survivor"]:
        phase_df = df[df["tax_phase"].str.strip().str.lower() == phase]
        if phase_df.empty:
            continue
        tgt = targets[phase]
        cash_vals = phase_df["cash"].fillna(0)
        min_cash = cash_vals.min()
        years_below = int((cash_vals < tgt).sum())
        label = phase_label_map.get(phase, phase)
        yr_start = int(phase_df["year"].min())
        yr_end = int(phase_df["year"].max())
        status = "✅" if years_below == 0 else f"⚠️ {years_below}y below"
        status_class = "status-ok" if years_below == 0 else "status-warn"

        rows_html.append(
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid rgba(36,49,66,0.4)'><strong>{label}</strong><br><span style='font-size:11px;color:var(--muted)'>{yr_start}–{yr_end}</span></td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid rgba(36,49,66,0.4);text-align:right;font-variant-numeric:tabular-nums'>${tgt:,.0f}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid rgba(36,49,66,0.4);text-align:right;font-variant-numeric:tabular-nums'>${min_cash:,.0f}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid rgba(36,49,66,0.4);text-align:center' class='{status_class}'>{status}</td>"
            f"</tr>"
        )

    return f"""<div class="card" style="margin-top:14px;padding:16px">
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead>
      <tr>
        <th style="padding:8px 12px;border-bottom:1px solid var(--border);text-align:left;font-weight:600;color:var(--muted)">Phase</th>
        <th style="padding:8px 12px;border-bottom:1px solid var(--border);text-align:right;font-weight:600;color:var(--muted)">Target</th>
        <th style="padding:8px 12px;border-bottom:1px solid var(--border);text-align:right;font-weight:600;color:var(--muted)">Minimum</th>
        <th style="padding:8px 12px;border-bottom:1px solid var(--border);text-align:center;font-weight:600;color:var(--muted)">Status</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
  <style>
    .status-ok {{ color: #22c55e; }}
    .status-warn {{ color: #fbbf24; }}
  </style>
</div>"""


def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
    """Convert '#f87171' to (248, 113, 113) for rgba()."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
                hovertemplate="P90 portfolio: $%{y:,.0f}<extra></extra>",
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
                hovertemplate="P75 portfolio: $%{y:,.0f}<extra></extra>",
            ))
        if median is not None:
            fig.add_trace(go.Scatter(
                x=years, y=median,
                mode="lines", name="Median portfolio",
                line=dict(color="#e5edf7", width=2.6),
                hovertemplate="Median portfolio: $%{y:,.0f}<extra></extra>",
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
                fixedrange=True,
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
            config=dict(scrollZoom=True),
        )
        portfolio_note = (
            "<div class='modeling-note'><strong>Portfolio range note:</strong> "
            "Bands show stochastic portfolio ranges by year. The table below reflects the median simulated path.</div>"
        )
        portfolio_table_html = _wrap_table_with_sticky_header(build_portfolio_table(df, config=config))
        return (
            f"<div class='gantt-wrap'>{portfolio_div}</div>"
            f"{portfolio_note}"
            f"<div class='table-panel portfolio-table-panel'>{portfolio_table_html}</div>"
        )

    portfolio_series = [
        ("taxable",     "#60a5fa", "Taxable / Brokerage"),
    ]
    if {"trad_ira_person1", "trad_ira_person2"}.issubset(df.columns):
        portfolio_series.extend([
            ("trad_ira_person1", "#10b981", f"Trad IRA / 401k — {person1_name}"),
            ("trad_ira_person2", "#34d399", f"Trad IRA / 401k — {person2_name}"),
        ])
    else:
        portfolio_series.append(("trad_ira", "#10b981", "Trad IRA / 401k"))

    if {"roth_person1", "roth_person2"}.issubset(df.columns):
        portfolio_series.extend([
            ("roth_person1", "#f59e0b", f"Roth — {person1_name}"),
            ("roth_person2", "#fbbf24", f"Roth — {person2_name}"),
        ])
    else:
        portfolio_series.append(("roth", "#f59e0b", "Roth"))

    for category, color, label in portfolio_series:
        if category in df.columns:
            # Always plot — a $0 flat line means the account is unfunded,
            # not that the portfolio collapsed. Individual non-stacked lines
            # eliminate the "stacked area touching zero" visual confusion.
            fig.add_trace(go.Scatter(
                x=df["year"], y=df[category],
                mode="lines", name=label,
                line=dict(color=color, width=2.0),
                hovertemplate=f"{label}: $%{{y:,.0f}}<extra></extra>",
            ))

    portfolio_total = df[["taxable", "trad_ira", "roth"]].sum(axis=1)
    fig.add_trace(go.Scatter(
        x=df["year"], y=portfolio_total,
        mode="lines", name="Total Investable Portfolio",
        line=dict(color="#f8fafc", width=2.2, dash="dash"),
        hovertemplate="Total Investable Portfolio: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        font=dict(color=font_color),
        title=dict(text="Retirement & Investment Accounts", font=dict(size=16)),
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
            title="Account Balance (USD)",
            tickformat="$,.0f",
            ticklabelstandoff=6,
            automargin=True,
            fixedrange=True,
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
        config=dict(scrollZoom=True),
    )

    portfolio_note = (
        "<div class='modeling-note'><strong>What this chart shows:</strong> "
        "Individual projected balances for taxable brokerage, traditional IRA/401(k), and Roth. "
        "<strong>Cash and home equity are excluded.</strong> "
        "A flat line at $0 (e.g. Taxable) means that account is unfunded in this scenario — "
        "it does not mean the overall portfolio collapsed.</div>"
    )

    taxable_hidden_note = ""
    if not (df["taxable"] != 0).any():
        taxable_hidden_note = (
            "<div class='modeling-note'><strong>Note:</strong> "
            "Taxable/Brokerage is $0 throughout — "
            "all investable surplus routes directly into retirement accounts in this scenario.</div>"
        )

    portfolio_table_html = _wrap_table_with_sticky_header(build_portfolio_table(df, config=config))
    return (
        f"<div class='gantt-wrap'>{portfolio_div}</div>"
        f"{portfolio_note}"
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
            fixedrange=True,
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
        config=dict(scrollZoom=True),
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
        hovertemplate="Success through year: %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["cumulative_failure_rate"],
        mode="lines", name="Cumulative failure rate",
        line=dict(color="#f87171", width=2.2),
        hovertemplate="Cumulative failure rate: %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["current_failure_trigger_rate"],
        mode="lines", name="Current-year pressure trigger",
        line=dict(color="#fbbf24", width=2.0, dash="dot"),
        hovertemplate="Current-year pressure trigger: %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=outcomes_df["year"],
        y=outcomes_df["temporary_pressure_rate"],
        mode="lines", name="Temporary pressure only",
        line=dict(color="#60a5fa", width=2.0, dash="dash"),
        hovertemplate="Temporary pressure only: %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(
        hovermode="x unified",
        font=dict(color="#e5edf7"),
        title=dict(text=f"{mode_label} Outcome Timing", font=dict(size=16)),
        xaxis=dict(title="Year", tickmode="linear", dtick=2, gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.14)", color="#e5edf7"),
        yaxis=dict(title="Probability", tickformat=".0%", gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.14)", color="#e5edf7", range=[0, 1], fixedrange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        plot_bgcolor="#0f1725",
        paper_bgcolor="#111827",
        height=420,
        margin=dict(l=64, r=24, t=70, b=56),
    )
    chart_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id="nwn-simulation",
                             config=dict(scrollZoom=True))
    table_html = _wrap_table_with_sticky_header(build_simulation_outcomes_table(outcomes_df, summary=summary))
    summary_html = (
        "<div class='assumptions-note'>"
        f"{mode_label} outcome detail for the current rendered result path. "
        f"<strong>Probability of Success:</strong> {_fmt_pct_text(summary.get('probability_of_success', summary.get('success_rate', 0.0)))} | "
        f"<strong>Probability of Spending Shortfall:</strong> {_fmt_pct_text(summary.get('probability_of_spending_shortfall', 0.0))} | "
        f"<strong>Failure mode:</strong> {escape(str(summary.get('failure_mode', '—')))} | "
        f"<strong>Median first failure year:</strong> {escape(str(summary.get('first_failure_year_p50', 'No failure')))} | "
        f"<strong>Peak temporary pressure:</strong> {_fmt_pct_text(summary.get('peak_temporary_pressure_rate', 0.0))}"
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
        config=dict(scrollZoom=True, displaylogo=False),
    )
    kpi_html = _build_kpi_summary(config, projection_result)
    tax_note_html = _build_tax_semantics_note()

    # Build table HTML
    accounts_html  = _wrap_table_with_sticky_header(build_accounts_table(df, config=config))
    cashflow_html  = _wrap_table_with_sticky_header(build_cashflow_table(df, config=config))
    cashflow_chart_html = _build_cashflow_chart(df, config=config)
    tax_html       = _wrap_table_with_sticky_header(build_tax_table(df))
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

    # Liabilities tab: debt payoff chart + amortization table
    liabilities_chart_html = _build_liabilities_chart(df, config=config)
    liabilities_table_html = build_liabilities_table(df, config=config)
    liabilities_html = (
        "<div class='gantt-wrap'>" + liabilities_chart_html + "</div>"
        + liabilities_table_html
    )

    # Cash Reserve tab: cash balance vs target chart + summary card
    cash_reserve_chart_html = _build_cash_reserve_chart(df, config=config)
    cash_reserve_summary_html = _build_cash_reserve_summary(df, config=config)
    cash_reserve_html = (
        "<div class='gantt-wrap'>" + cash_reserve_chart_html + "</div>"
        + cash_reserve_summary_html
    )

    scenario_slug = getattr(scenario, "slug", None)
    edit_config_href = f"/finances/config/?scenario={scenario_slug}" if scenario_slug else "/finances/config/"

    # Tab-label tooltips — explain what each tab shows. Rendered via the same
    # help-mode SVG icon as the KPI strip, but the tooltip itself is CSS
    # `position: fixed` (see `.tab-btn .tooltip-content` in _TABS_CSS) because
    # `.tabs` needs `overflow-x: auto` for mobile scrolling, which forces
    # `overflow-y` on the same box to clip too — an absolutely-positioned
    # tooltip anchored inside `.tabs` would otherwise get cut off.
    _TAB_TOOLTIPS = {
        "accounts": "Year-by-year account balances broken out by type (cash, brokerage, retirement accounts, home equity).",
        "cashflow": "Annual income (take-home + freed mortgage payments + events) vs spending, and the resulting net surplus or deficit.",
        "tax": "Modeled federal and state tax by year, based on filing status, deductions, and taxable income sources.",
        "simulation": "Monte Carlo or historical simulation outcomes — probability of success, and the range of terminal net worth across simulated paths.",
        "portfolio": "Investment balances over time (taxable, traditional, Roth) excluding cash and home equity.",
        "gantt": "Timeline of enabled life events and when they occur across the plan.",
        "liabilities": "Debt balances, payoff schedules, and amortization detail for mortgages and other liabilities.",
        "cash-reserve": "Cash balance vs your target cash reserve by year, and how many years fall below target.",
        "assumptions": "Full list of modeling assumptions in effect for this scenario (income, contributions, tax, withdrawal policy, etc.).",
        "scenario-parameters": "Key scenario parameters at a glance, with support for highlighting differences vs another scenario.",
    }

    def _tab_button_html(tab_id: str, label: str, *, active: bool = False) -> str:
        tooltip_text = _TAB_TOOLTIPS.get(tab_id, "")
        active_cls = " active" if active else ""
        tooltip_span = (
            f"{_INFO_ICON_SVG}<span class='tooltip-content'>{tooltip_text}</span>"
            if tooltip_text
            else ""
        )
        return (
            f"<button class='tab-btn help-tooltip{active_cls}' id='btn-{tab_id}' "
            f"onclick=\"switchTab('{tab_id}', event)\">{label}{tooltip_span}</button>"
        )

    # Conditional simulation tab button (avoid backslash in f-string)
    simulation_tab_html = (
        _tab_button_html("simulation", "Simulation")
        if simulation_html
        else ""
    )
    
    # Setup status warning for placeholder/starter data
    setup_warning_html = ""
    if config:
        # Check for common placeholder indicators
        has_placeholder_data = (
            scenario_slug in ("starter", "sample") or  # Using template scenarios
            config.get("scenario", {}).get("name") == "Your Household Name" or  # Unchanged starter template
            config.get("scenario", {}).get("description", "").startswith("A household scenario") or  # Default description
            any(  # Check for placeholder person names
                person_cfg.get("name") in ("Person 1", "Person 2", "Alex", "Sam", "Your Name")
                for key, person_cfg in config.items()
                if key.startswith("person") and isinstance(person_cfg, dict)
            )
        )
        
        if has_placeholder_data:
            setup_warning_html = f"""
    <div class="setup-status-warning">
      <strong>⚠️ Setup Incomplete</strong> — This projection uses placeholder or sample data.
      <a href="{edit_config_href}">Edit your scenario</a> to enter real household values, or
      <a href="/finances/config/setup">use the Setup Panel</a> to create a new scenario from scratch.
    </div>
"""
    
    # About This Sample card (only for the sample scenario)
    sample_guide_html = ""
    if scenario_slug == "sample":
        sample_guide_html = """
    <div class="sample-guide-card">
      <h3>📘 About This Sample</h3>
      <p>This is a <strong>single-person reference demo</strong> showing Net Worth Navigator's features with realistic synthetic data:</p>
      <ul class="sample-highlights">
        <li><strong>Alex (b. 1972)</strong> — employed single professional</li>
        <li><strong>Retirement in late 60s</strong> — contributes to 401(k) with employer match</li>
        <li><strong>Home mortgage + auto loan</strong> — both pay down over time</li>
        <li><strong>Recurring events</strong> — biennial travel, annual home maintenance, vehicle replacements</li>
        <li><strong>Later-life planning</strong> — part-time consulting income, care support costs</li>
      </ul>
      <p class="sample-guide-tip"><strong>💡 Tip:</strong> Click year columns in tables to highlight that year across all data. Try switching between projection modes (deterministic, historical, Monte Carlo) using the Simulation tab.</p>
      <div class="sample-guide-actions">
        <a href="/finances/config/?scenario=sample" target="_top" class="sample-guide-btn">View Sample Config</a>
        <a href="/finances/config/setup" target="_top" class="sample-guide-btn sample-guide-btn-primary">Create Your Own</a>
      </div>
    </div>
"""

    # Assemble full page
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Net Worth Navigator</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111827'/%3E%3Cg fill='none' stroke='%237dd3fc' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6,22 10,18 15,20 20,12 26,7'/%3E%3C/g%3E%3Cg fill='%2338bdf8' opacity='0.35'%3E%3Crect x='5' y='23' width='3' height='5' rx='0.8'/%3E%3Crect x='9' y='21' width='3' height='7' rx='0.8'/%3E%3Crect x='14' y='22' width='3' height='6' rx='0.8'/%3E%3Crect x='19' y='16' width='3' height='12' rx='0.8'/%3E%3Crect x='24' y='14' width='3' height='14' rx='0.8'/%3E%3C/g%3E%3C/svg%3E">
  {_TABS_CSS}
</head>
<body>
  <div class="page-toolbar">
    <a class="toolbar-link" href="{edit_config_href}">Edit Config</a>
    <button class="help-mode-toggle" id="help-mode-toggle" title="Toggle help mode">
      <span class="help-icon">?</span>
    </button>
  </div>
  <div class="chart-wrap">
    {setup_warning_html}
    {sample_guide_html}
    {kpi_html}
    {chart_div}
    <div class="event-label-controls" id="event-label-controls">
      <label><input type="checkbox" id="event-labels-show-all" checked> Show all event labels</label>
      <label><input type="checkbox" id="event-labels-keep-key" checked> Keep key labels when hidden</label>
    </div>
    <div class="zoom-presets" id="zoom-presets">
      <span class="zoom-preset-label">Zoom:</span>
      <button class="zoom-preset-btn active" data-range="full" onclick="zoomToYears('nwn-chart', this, null)">Full</button>
      <button class="zoom-preset-btn" data-range="10" onclick="zoomToYears('nwn-chart', this, 10)">10yr</button>
      <button class="zoom-preset-btn" data-range="25" onclick="zoomToYears('nwn-chart', this, 25)">25yr</button>
      <button class="zoom-preset-btn" data-range="50" onclick="zoomToYears('nwn-chart', this, 50)">50yr</button>
    </div>
    {tax_note_html}
  </div>

  <div class="tabs">
    {_tab_button_html("accounts", "Accounts", active=True)}
    {_tab_button_html("cashflow", "Cash Flow")}
    {_tab_button_html("tax", "Tax")}
    {simulation_tab_html}
    {_tab_button_html("portfolio", "Portfolio")}
    {_tab_button_html("gantt", "Gantt")}
    {_tab_button_html("liabilities", "Liabilities")}
    {_tab_button_html("cash-reserve", "Cash Reserve")}
    {_tab_button_html("assumptions", "Assumptions")}
    {_tab_button_html("scenario-parameters", "Scenario Parameters")}
  </div>

  <div class="tab-panel table-panel active" id="panel-accounts">
    {accounts_html}
  </div>
  <div class="tab-panel" id="panel-cashflow">
    <div class="gantt-wrap">{cashflow_chart_html}</div>
    <div class="modeling-note"><strong>What this shows:</strong> Total household income (take-home + freed mortgage payments) vs total spending for each year. Net flow above zero is surplus; below zero is deficit funded by portfolio withdrawals.</div>
    <div class="table-panel portfolio-table-panel">{cashflow_html}</div>
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
  <div class="tab-panel" id="panel-liabilities">
    {liabilities_html}
  </div>
  <div class="tab-panel gantt-panel" id="panel-cash-reserve">
    {cash_reserve_html}
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
                hovertemplate="P90 net worth: $%{y:,.0f}<extra></extra>",
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
                hovertemplate="P75 net worth: $%{y:,.0f}<extra></extra>",
            ))
        if total_median is not None:
            fig.add_trace(go.Scatter(
                x=years, y=total_median,
                mode="lines", name="Median total net worth",
                line=dict(color="#f8fafc", width=2.8),
                hovertemplate="Median total net worth: $%{y:,.0f}<extra></extra>",
            ))
        if (df["home_equity"] != 0).any():
            fig.add_trace(go.Scatter(
                x=df["year"], y=df["home_equity"],
                mode="lines", name="Median home equity",
                line=dict(color="rgba(237,194,148,0.88)", width=1.8, dash="dot"),
                hovertemplate="Median home equity: $%{y:,.0f}<extra></extra>",
            ))
    else:

        # ── Home equity band (non-liquid) ──────────────────────────────────────────
        if (df["home_equity"] != 0).any():
            fig.add_trace(go.Scatter(
                x=df["year"], y=df["home_equity"],
                mode="lines", name="Home Equity (non-liquid)",
                fill="tozeroy", fillcolor="rgba(217,168,120,0.30)",
                line=dict(color="rgba(237,194,148,0.88)", width=1.8, dash="dot"),
                hovertemplate="Home Equity: $%{y:,.0f}<extra></extra>",
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
                    hovertemplate=f"{label}: $%{{y:,.0f}}<extra></extra>",
                ))

        # ── Total net worth line ───────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["total_net_worth"],
            mode="lines", name="Total Net Worth",
            line=dict(color="#f8fafc", width=2.5, dash="dash"),
            hovertemplate="Total Net Worth: $%{y:,.0f}<extra></extra>",
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

    # ── Age labels below x-axis (separate from tick text so hover stays clean) ─
    for year in tickvals:
        age_label = _age_label_for_year(config, year)
        if age_label:
            fig.add_annotation(
                x=year, y=-0.085, xref="x", yref="paper",
                text=age_label, showarrow=False,
                font=dict(size=10, color="rgba(226,232,240,0.70)"),
            )

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
        xaxis=dict(title=dict(text="Year", standoff=28), tickmode="array", tickvals=tickvals, ticktext=ticktext,
                   ticklabelstandoff=6,
                   gridcolor=grid,
                   zerolinecolor=grid,
                   color=font_color),
        yaxis=dict(title="Net Worth (USD)", tickformat="$,.0f",
                   ticklabelstandoff=6,
                   automargin=True,
                   fixedrange=True,
                   gridcolor=grid,
                   zerolinecolor=grid,
                   color=font_color),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#0f1725", bordercolor="#334155", font_color="#f8fafc"),
        plot_bgcolor=plot_bg, paper_bgcolor=paper_bg,
        height=680,
        margin=dict(l=80, r=40, t=140, b=100),
    )

    return fig


def _wrap_event_annotation(label: str, per_line: int = 2) -> str:
    """Wrap comma-separated event labels into groups to reduce annotation overflow."""
    parts = [part.strip() for part in str(label).split(",") if part.strip()]
    if len(parts) <= per_line:
        return label
    groups = [parts[i:i + per_line] for i in range(0, len(parts), per_line)]
    return "<br>".join(", ".join(group) for group in groups)

