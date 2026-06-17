"""
charts.py — Generate Plotly HTML chart from projection DataFrame.
"""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go


def build_chart(df: pd.DataFrame, output_path: Path) -> None:
    """
    Generate a self-contained interactive HTML chart from projection data.
    Writes to output_path.
    """
    fig = go.Figure()

    # ── Home equity band (non-liquid — distinct muted color) ──────────────────
    if df["home_equity"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["year"],
            y=df["home_equity"],
            mode="lines",
            name="Home Equity (non-liquid)",
            fill="tozeroy",
            fillcolor="rgba(160,120,80,0.20)",
            line=dict(color="rgba(160,120,80,0.55)", width=1.5, dash="dot"),
            hovertemplate="<b>%{x}</b><br>Home Equity: $%{y:,.0f}<extra></extra>",
        ))

    # ── Investable account breakdown (stacked area) ───────────────────────────
    for category, color, label in [
        ("cash",     "rgba(180,180,180,0.45)", "Cash"),
        ("taxable",  "rgba(74,144,217,0.45)",  "Taxable"),
        ("trad_ira", "rgba(80,180,100,0.45)",  "Traditional IRA / 401k"),
        ("roth",     "rgba(255,160,50,0.45)",  "Roth"),
    ]:
        if df[category].sum() > 0:
            fig.add_trace(go.Scatter(
                x=df["year"],
                y=df[category],
                mode="lines",
                name=label,
                stackgroup="investable",
                fillcolor=color,
                line=dict(width=0),
                hovertemplate=f"<b>%{{x}}</b><br>{label}: $%{{y:,.0f}}<extra></extra>",
            ))

    # ── Total net worth line (investable + home equity) ───────────────────────
    fig.add_trace(go.Scatter(
        x=df["year"],
        y=df["total_net_worth"],
        mode="lines",
        name="Total Net Worth",
        line=dict(color="#1a1a2e", width=2.5, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Total Net Worth: $%{y:,.0f}<extra></extra>",
    ))

    # ── Survivor period shading ────────────────────────────────────────────────
    survivor_years = df[df["survivor"] == True]["year"]
    if len(survivor_years) > 0:
        fig.add_vrect(
            x0=survivor_years.iloc[0] - 0.5,
            x1=df["year"].iloc[-1] + 0.5,
            fillcolor="rgba(100,100,100,0.06)",
            line_width=0,
            annotation_text="Survivor period",
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="rgba(100,100,100,0.7)",
        )

    # ── Event annotations ─────────────────────────────────────────────────────
    events_df = df[df["events_active"] != ""]
    for _, row in events_df.iterrows():
        fig.add_vline(
            x=row["year"],
            line_dash="dot",
            line_color="rgba(200,50,50,0.5)",
            annotation_text=row["events_active"],
            annotation_position="top right",
            annotation_font_size=10,
        )

    # ── Layout ─────────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="Net Worth Navigator — Household Projection<br><sup>Values shown are end-of-year estimates, anchored to live Monarch balances</sup>",
            font=dict(size=20),
        ),
        xaxis=dict(
            title="Year",
            tickmode="linear",
            dtick=5,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis=dict(
            title="Net Worth (USD)",
            tickformat="$,.0f",
            gridcolor="rgba(200,200,200,0.3)",
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=600,
        margin=dict(l=80, r=40, t=80, b=60),
    )

    # ── Write output ───────────────────────────────────────────────────────────
    fig.write_html(
        str(output_path),
        include_plotlyjs="cdn",
        full_html=True,
    )
    print(f"  Chart written: {output_path} ({output_path.stat().st_size // 1024}KB)")
