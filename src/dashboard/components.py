import pandas as pd
import plotly.graph_objects as go
import streamlit as st

TREND_DAYS = 14  

STYLE = """
    <style>
        div:has(> .st-key-top-days) { flex: 1 1 320px; }
        div:has(> .st-key-revenue-trend) { flex: 2.6 1 560px; }
    </style>
"""

def apply_styles() -> None:
    st.html(STYLE)

def money(value: float) -> str:
    return f"${value:,.2f}"

def card(label: str, body: str, caption: str | None = None) -> None:
    with st.container(border=True, height="stretch"):
        st.caption(label)
        st.markdown(body)
        if caption:
            st.caption(caption)

def top_days_table(top_days: list[dict]) -> None:
    frame = pd.DataFrame(top_days)
    frame.insert(0, "rank", range(1, len(frame) + 1))
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            "rank": st.column_config.NumberColumn("#", width="small"),
            "date": st.column_config.TextColumn("Date"),
            "revenue": st.column_config.ProgressColumn(
                "Revenue", format="dollar", min_value=0, max_value=float(frame["revenue"].max())
            ),
        },
    )

def revenue_chart(daily: pd.DataFrame, highlight: list[str]) -> None:
    rolling = daily["revenue"].rolling(TREND_DAYS, center=True, min_periods=1).mean()
    top = daily[daily["date"].dt.strftime("%Y-%m-%d").isin(highlight)]

    fig = go.Figure()
    fig.add_scatter(x=daily["date"], y=daily["revenue"], mode="lines", name="Daily revenue",
                    line={"width": 1, "color": "rgba(96, 165, 250, 0.55)"})
    fig.add_scatter(x=daily["date"], y=rolling.round(2), mode="lines", name=f"{TREND_DAYS}-day average",
                    line={"width": 2.5, "color": "#1d4ed8", "shape": "spline", "smoothing": 1.3})
    fig.add_scatter(x=top["date"], y=top["revenue"], mode="markers", name="Top 5 days",
                    marker={"size": 12, "symbol": "star", "color": "#f59e0b", "line": {"width": 1, "color": "#92400e"}})
    fig.update_layout(
        height=440,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0},
        yaxis={"tickprefix": "$", "title": None},
        xaxis={"title": None, "rangeslider": {"visible": True, "thickness": 0.06}},
    )
    st.plotly_chart(fig, width="stretch")
