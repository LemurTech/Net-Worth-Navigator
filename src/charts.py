"""
charts.py — Generate Plotly HTML chart + tabbed data tables.

Produces a single self-contained HTML file:
  - Top: Plotly projection chart (with Plotly CDN JS)
  - Below: three CSS tabs — Accounts, Cash Flow (Gantt in V2)
"""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

from src.tables import build_accounts_table, build_cashflow_table

# ── CSS + JS for the tabbed layout ────────────────────────────────────────────
_TABS_CSS = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0 16px 32px; background: #fafafa; color: #222; }
  .chart-wrap { background: white; border-radius: 8px; padding: 8px;
                box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 16px; }
  .tabs { display: flex; gap: 4px; margin-bottom: 0; border-bottom: 2px solid #e0e0e0; }
  .tab-btn { padding: 8px 18px; border: none; background: none; cursor: pointer;
             font-size: 14px; color: #555; border-bottom: 3px solid transparent;
             margin-bottom: -2px; transition: color .15s; }
  .tab-btn:hover { color: #1a1a2e; }
  .tab-btn.active { color: #1a1a2e; border-bottom-color: #4A90D9; font-weight: 600; }
  .tab-panel { display: none; overflow-x: auto; }
  .tab-panel.active { display: block; }
  table.datatable { border-collapse: collapse; width: 100%; font-size: 13px;
                    background: white; border-radius: 6px;
                    box-shadow: 0 1px 4px rgba(0,0,0,.07); }
  table.datatable th, table.datatable td { padding: 6px 10px; text-align: right;
                                           border-bottom: 1px solid #f0f0f0; white-space: nowrap; }
  table.datatable th.rowlabel, table.datatable td.rowlabel { text-align: left;
      min-width: 190px; font-weight: normal; }
  table.datatable thead tr th { background: #f5f5f5; font-weight: 600;
                                 border-bottom: 2px solid #ddd; }
  table.datatable tr.section th { background: #eef2f7; font-weight: 700;
                                   font-size: 12px; text-transform: uppercase;
                                   letter-spacing: .04em; color: #444;
                                   padding: 5px 10px; text-align: left; }
  table.datatable tr.total td, table.datatable tr.total th { font-weight: 700;
      background: #f9f9f9; border-top: 1px solid #ccc; }
  table.datatable tr.sep td, table.datatable tr.sep th { border-top: 2px solid #ccc; }
  table.datatable td.neg { color: #c0392b; }
  table.datatable td.zero { color: #bbb; text-align: right; }
  table.datatable tr.indent td.rowlabel { padding-left: 24px; }
  table.datatable tr:hover td, table.datatable tr:hover th { background: #f0f6ff; }
</style>
"""

_TABS_JS = """
<script>
function switchTab(id) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('btn-' + id).classList.add('active');
  document.getElementById('panel-' + id).classList.add('active');
}
</script>
"""


def build_chart(df: pd.DataFrame, output_path: Path) -> None:
    """
    Generate the Plotly chart figure, build HTML tables, and write
    a single self-contained tabbed HTML page to output_path.
    """
    fig = _build_figure(df)

    # Export figure as a standalone div (no full HTML, no duplicate Plotly JS)
    chart_div = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        div_id="nwn-chart",
    )

    # Build table HTML
    accounts_html  = build_accounts_table(df)
    cashflow_html  = build_cashflow_table(df)

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
  <div class="chart-wrap">
    {chart_div}
  </div>

  <div class="tabs">
    <button class="tab-btn active" id="btn-accounts"
            onclick="switchTab('accounts')">Accounts</button>
    <button class="tab-btn" id="btn-cashflow"
            onclick="switchTab('cashflow')">Cash Flow</button>
  </div>

  <div class="tab-panel active" id="panel-accounts">
    {accounts_html}
  </div>
  <div class="tab-panel" id="panel-cashflow">
    {cashflow_html}
  </div>

  {_TABS_JS}
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    size_kb = output_path.stat().st_size // 1024
    print(f"  Chart written: {output_path} ({size_kb}KB)")


# ── Figure builder ─────────────────────────────────────────────────────────────

def _build_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    # ── Home equity band (non-liquid) ──────────────────────────────────────────
    if df["home_equity"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["home_equity"],
            mode="lines", name="Home Equity (non-liquid)",
            fill="tozeroy", fillcolor="rgba(160,120,80,0.20)",
            line=dict(color="rgba(160,120,80,0.55)", width=1.5, dash="dot"),
            hovertemplate="<b>%{x}</b><br>Home Equity: $%{y:,.0f}<extra></extra>",
        ))

    # ── Investable stacked area ────────────────────────────────────────────────
    for category, color, label in [
        ("cash",     "rgba(180,180,180,0.45)", "Cash"),
        ("taxable",  "rgba(74,144,217,0.45)",  "Taxable"),
        ("trad_ira", "rgba(80,180,100,0.45)",  "Traditional IRA / 401k"),
        ("roth",     "rgba(255,160,50,0.45)",  "Roth"),
    ]:
        if df[category].sum() > 0:
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
        line=dict(color="#1a1a2e", width=2.5, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Total Net Worth: $%{y:,.0f}<extra></extra>",
    ))

    # ── Survivor period shading ────────────────────────────────────────────────
    survivor_years = df[df["survivor"] == True]["year"]
    if len(survivor_years) > 0:
        x0 = survivor_years.iloc[0] - 0.5
        x1 = df["year"].iloc[-1] + 0.5
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(100,100,100,0.06)", line_width=0)
        fig.add_annotation(
            x=(survivor_years.iloc[0] + df["year"].iloc[-1]) / 2,
            y=1.0, xref="x", yref="paper",
            text="👤 Survivor period", showarrow=False,
            font=dict(size=10, color="rgba(100,100,100,0.75)"),
            bgcolor="rgba(255,255,255,0.6)", borderpad=2, yanchor="bottom",
        )

    # ── Event annotations — vertical, right of line ────────────────────────────
    events_df = df[df["events_active"] != ""].copy()
    for _, row in events_df.iterrows():
        label  = row["events_active"]
        is_eop = "⚰️" in label
        fig.add_vline(
            x=row["year"],
            line_dash="dash" if is_eop else "dot",
            line_color="rgba(80,80,80,0.55)" if is_eop else "rgba(60,100,180,0.55)",
            annotation_text=label,
            annotation_position="top right",
            annotation_textangle=-90,
            annotation_font_size=11,
            annotation_bgcolor="rgba(255,255,255,0.88)",
            annotation_borderpad=3,
        )

    # ── Layout ─────────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                "Net Worth Navigator — Household Projection"
                "<br><sup>Values shown are end-of-year estimates, "
                "anchored to live Monarch balances</sup>"
            ),
            font=dict(size=20),
        ),
        xaxis=dict(title="Year", tickmode="linear", dtick=5,
                   gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(title="Net Worth (USD)", tickformat="$,.0f",
                   gridcolor="rgba(200,200,200,0.3)"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
        plot_bgcolor="white", paper_bgcolor="white",
        height=680,
        margin=dict(l=80, r=40, t=140, b=60),
    )

    return fig

