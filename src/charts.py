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

    # ── Main net worth line ────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df["year"],
        y=df["net_worth"],
        mode="lines",
        name="Net Worth",
        line=dict(color="#4A90D9", width=3),
        hovertemplate="<b>%{x}</b><br>Net Worth: $%{y:,.0f}<extra></extra>",
    ))

    # ── Account breakdown (stacked area) ──────────────────────────────────────
    for category, color in [
        ("taxable",  "rgba(74,144,217,0.4)"),
        ("trad_ira", "rgba(80,180,100,0.4)"),
        ("roth",     "rgba(255,160,50,0.4)"),
        ("cash",     "rgba(180,180,180,0.4)"),
    ]:
        if df[category].sum() > 0:
            fig.add_trace(go.Scatter(
                x=df["year"],
                y=df[category],
                mode="lines",
                name=category.replace("_", " ").title(),
                stackgroup="accounts",
                fillcolor=color,
                line=dict(width=0),
                hovertemplate=f"<b>%{{x}}</b><br>{category}: $%{{y:,.0f}}<extra></extra>",
            ))

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
            text="Net Worth Navigator — Household Projection",
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
