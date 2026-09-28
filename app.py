"""
Veridi Logistics — Last Mile Delivery Audit dashboard.
Run locally:  py -3.13 -m streamlit run app.py
Deploy:       push this file + requirements.txt + the 3 summary CSVs to a public
              GitHub repo, then "New app" on share.streamlit.io pointing at app.py.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

NAVY, RED, DRED, TEAL, AMBER, GRAY, LIGHT = (
    "#1B2A41", "#D1495B", "#6B0F1A", "#2A9D8F", "#E9C46A", "#5C677D", "#F3F5F8",
)
PLOTLY_FONT = dict(family="Arial, sans-serif", color=NAVY, size=13)

st.set_page_config(page_title="Veridi Delivery Audit", page_icon="📦", layout="wide")

# ---------- light CSS polish (cards, spacing, hide default chrome) ----------
st.markdown(f"""
<style>
#MainMenu, footer {{visibility: hidden;}}
.block-container {{padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px;}}
h1 {{color:{NAVY}; font-weight:800;}}
h2, h3 {{color:{NAVY};}}
.kpi-card {{
    background:{LIGHT}; border-radius:12px; padding:18px 20px; height:100%;
}}
.kpi-label {{color:{GRAY}; font-size:0.85rem; font-weight:600; text-transform:uppercase; letter-spacing:.03em;}}
.kpi-value {{color:{NAVY}; font-size:2rem; font-weight:800; margin-top:4px;}}
.kpi-sub {{color:{GRAY}; font-size:0.8rem; margin-top:2px;}}
.section-gap {{margin-top: 2.2rem;}}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    orders = pd.read_csv("dashboard_orders.csv")
    state = pd.read_csv("state_summary.csv")
    cat = pd.read_csv("category_summary.csv")
    return orders, state, cat

try:
    orders, state, cat = load()
except FileNotFoundError:
    st.error(
        "Couldn't find dashboard_orders.csv / state_summary.csv / category_summary.csv. "
        "Run `py -3.13 veridi_audit.py` first to generate them, then reload this page."
    )
    st.stop()

# ---------- header ----------
st.title("📦 Veridi Logistics — Last Mile Delivery Audit")
st.caption("Are we failing specific regions, or is it a nationwide problem? · Olist e-commerce data")

# ---------- sidebar filter ----------
st.sidebar.header("Filters")
all_states = sorted(orders.customer_state.unique())
sel = st.sidebar.multiselect("Customer state", all_states, default=[])
st.sidebar.caption("Leave empty to see all of Brazil.")

o = orders[orders.customer_state.isin(sel)] if sel else orders
s = state[state.customer_state.isin(sel)] if sel else state
national_late = (orders.delivery_status != "On Time").mean() * 100

# ---------- KPI row ----------
late_pct = (o.delivery_status != "On Time").mean() * 100
super_pct = (o.delivery_status == "Super Late").mean() * 100
avg_score = o.review_score.mean()
delta = late_pct - national_late

k1, k2, k3, k4 = st.columns(4)
kpis = [
    (k1, "Delivered orders", f"{len(o):,}", None),
    (k2, "% Late", f"{late_pct:.1f}%", f"{delta:+.1f} pts vs national" if sel else "national rate"),
    (k3, "% Super Late (>5d)", f"{super_pct:.1f}%", "more than 5 days late"),
    (k4, "Avg review score", f"{avg_score:.2f} / 5", None),
]
for col, label, value, sub in kpis:
    with col:
        st.markdown(
            f"""<div class="kpi-card"><div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub or ""}</div></div>""",
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

# ---------- tabs ----------
tab_geo, tab_sentiment, tab_promise, tab_category = st.tabs(
    ["🗺️ Geography", "⭐ Sentiment", "📐 Promise Accuracy", "📦 Categories"]
)

with tab_geo:
    c1, c2 = st.columns([3, 2])
    with c1:
        s_sorted = s.sort_values("late_pct", ascending=False)
        fig = px.bar(
            s_sorted, x="customer_state", y="late_pct",
            color="late_pct", color_continuous_scale=[LIGHT, RED, DRED],
            labels={"late_pct": "% late", "customer_state": "State"},
        )
        fig.add_hline(y=national_late, line_dash="dash", line_color=GRAY,
                       annotation_text=f"National {national_late:.1f}%", annotation_position="top right")
        fig.update_layout(title="% of orders late by state", font=PLOTLY_FONT,
                           coloraxis_showscale=False, plot_bgcolor="white", height=430,
                           margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.scatter(
            s, x="km_from_SP", y="late_pct", size="orders", color="late_pct",
            color_continuous_scale=[TEAL, AMBER, RED], hover_name="customer_state",
            labels={"km_from_SP": "km from Sao Paulo", "late_pct": "% late"},
        )
        fig2.update_layout(title="Remoteness vs % late", font=PLOTLY_FONT,
                            coloraxis_showscale=False, plot_bgcolor="white", height=430,
                            margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.caption("Northeast states (AL, BA, CE, MA, PB, PE, PI, RN, SE) run well above the national rate; "
               "distance from the assumed Sao Paulo hub only weakly explains the pattern.")

with tab_sentiment:
    c1, c2 = st.columns([2, 3])
    with c1:
        sc = (o.groupby("delivery_status").review_score.mean()
                .reindex(["On Time", "Late", "Super Late"]).reset_index())
        fig3 = go.Figure(go.Bar(
            x=sc.delivery_status, y=sc.review_score,
            marker_color=[TEAL, AMBER, RED], text=sc.review_score.round(2), textposition="outside",
        ))
        fig3.update_layout(title="Average review score by delivery status", font=PLOTLY_FONT,
                            yaxis=dict(range=[0, 5], title="Avg score (1-5)"), plot_bgcolor="white",
                            height=420, margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig3, use_container_width=True)
    with c2:
        b = o.dropna(subset=["review_score"]).copy()
        b["days_late"] = (-b.Days_Difference).clip(-15, 20).round()
        curve = b.groupby("days_late").review_score.mean().reset_index()
        fig4 = px.line(curve, x="days_late", y="review_score", markers=True,
                        labels={"days_late": "Days late (negative = early)", "review_score": "Avg score"})
        fig4.update_traces(line_color=NAVY, marker_color=RED)
        fig4.add_vline(x=0, line_dash="dash", line_color=GRAY)
        fig4.update_layout(title="Review score vs delay length", font=PLOTLY_FONT,
                            plot_bgcolor="white", height=420, margin=dict(t=50, l=10, r=10, b=10))
        st.plotly_chart(fig4, use_container_width=True)
    st.caption("Score drops sharply once a delivery is more than a few days late — the >5-day group averages under 2 stars.")

with tab_promise:
    top_gap = s.sort_values("late_pct", ascending=False).head(10)
    g = top_gap.melt(id_vars="customer_state",
                      value_vars=["promised_median", "actual_median", "recommended_promise_days"],
                      var_name="metric", value_name="days")
    label_map = {"promised_median": "Promised (median)", "actual_median": "Actual (median)",
                 "recommended_promise_days": "Safe promise (P90 actual)"}
    g["metric"] = g.metric.map(label_map)
    fig5 = px.bar(g, x="customer_state", y="days", color="metric", barmode="group",
                  color_discrete_map={"Promised (median)": NAVY, "Actual (median)": RED,
                                      "Safe promise (P90 actual)": TEAL})
    fig5.update_layout(title="Promised vs actual vs safe delivery time — top 10 latest states",
                        font=PLOTLY_FONT, plot_bgcolor="white", height=460, legend_title="",
                        legend=dict(orientation="h", y=-0.2), margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig5, use_container_width=True)
    st.caption("Candidate's Choice: extending the promise only where the 90th-percentile actual time "
               "exceeds it (never shortening a generous one) cuts the national late rate from "
               f"{national_late:.1f}% toward roughly 5.6%, without any change to shipping operations.")

with tab_category:
    top_cat = cat.sort_values("late_pct", ascending=False).head(15)
    fig6 = px.bar(top_cat, y="category_en", x="late_pct", orientation="h",
                  color="late_pct", color_continuous_scale=[LIGHT, RED, DRED],
                  labels={"late_pct": "% late", "category_en": ""})
    fig6.update_layout(title="Top 15 product categories by % late (min. 200 orders)", font=PLOTLY_FONT,
                        coloraxis_showscale=False, plot_bgcolor="white", height=500,
                        yaxis=dict(autorange="reversed"), margin=dict(t=50, l=10, r=10, b=10))
    st.plotly_chart(fig6, use_container_width=True)
    st.caption("Category names translated from Portuguese via product_category_name_translation.csv.")

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
st.caption("Veridi Logistics · Last Mile Delivery Audit · Data: Olist Brazilian E-Commerce dataset")