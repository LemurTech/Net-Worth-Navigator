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
    # Use add_vrect WITHOUT annotation_text to avoid the built-in label
    # (which Plotly places in the top-left and clashes with vline annotations).
    # Instead, add a separate paper-space annotation at the midpoint.
    survivor_years = df[df["survivor"] == True]["year"]
    if len(survivor_years) > 0:
        x0 = survivor_years.iloc[0] - 0.5
        x1 = df["year"].iloc[-1] + 0.5
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(100,100,100,0.06)",
            line_width=0,
        )
        # Standalone annotation placed in paper y-space (above plot area)
        # so it can never collide with data-space vline annotations
        fig.add_annotation(
            x=(survivor_years.iloc[0] + df["year"].iloc[-1]) / 2,
            y=1.0,
            xref="x",
            yref="paper",
            text="👤 Survivor period",
            showarrow=False,
            font=dict(size=10, color="rgba(100,100,100,0.75)"),
            bgcolor="rgba(255,255,255,0.6)",
            borderpad=2,
            yanchor="bottom",
        )

    # ── Event annotations — diagonal labels ───────────────────────────────────
    # textangle=-60 reads naturally on a tilt while still avoiding overlap.
    # -90 (fully vertical) is harder to read; -60 is the legibility sweet spot.
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
            annotation_textangle=-60,
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
            y=1.06,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=680,
        margin=dict(l=80, r=40, t=140, b=60),
    )

    # ── Write output ───────────────────────────────────────────────────────────
    fig.write_html(
        str(output_path),
        include_plotlyjs="cdn",
        full_html=True,
    )
    print(f"  Chart written: {output_path} ({output_path.stat().st_size // 1024}KB)")
