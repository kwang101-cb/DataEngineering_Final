"""
BRFSS 2024 Chronic Disease Analytics — Databricks App (Streamlit).

Restructured around three core business questions:
  Q1. Which behavioral risk factors most strongly predict chronic disease diagnoses?
  Q2. How do risk profiles vary by state, income bracket, and age group?
  Q3. Where are populations engaging in high-risk behaviors but not accessing preventive care?
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

# ─── Configuration ───────────────────────────────────────────────────────────

GOLD = "data_engineering.gold"
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID") or os.getenv("WAREHOUSE_ID")

st.set_page_config(
    page_title="BRFSS 2024 Health Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Theme ───────────────────────────────────────────────────────────────────

DBX_RED    = "#FF3621"
DBX_NAVY   = "#1B3139"
DBX_GREEN  = "#00A972"
DBX_BLUE   = "#0073E6"
DBX_AMBER  = "#FF9900"
DBX_PURPLE = "#7C4DFF"
DBX_BG     = "#F9F7F4"
DBX_GRID   = "#E5E5E5"
DBX_COLORS = [DBX_RED, DBX_NAVY, DBX_GREEN, DBX_BLUE, DBX_AMBER, DBX_PURPLE, "#9C27B0", "#00897B"]

pio.templates["databricks"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, system-ui, -apple-system, sans-serif", size=13, color=DBX_NAVY),
        paper_bgcolor="white", plot_bgcolor=DBX_BG, colorway=DBX_COLORS,
        title=dict(font=dict(size=20, color=DBX_NAVY), x=0, xanchor="left"),
        xaxis=dict(gridcolor=DBX_GRID, linecolor=DBX_NAVY, zerolinecolor=DBX_GRID),
        yaxis=dict(gridcolor=DBX_GRID, linecolor=DBX_NAVY, zerolinecolor=DBX_GRID),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor=DBX_GRID, borderwidth=1),
        margin=dict(t=60, b=40, l=60, r=20),
        hoverlabel=dict(bgcolor="white", bordercolor=DBX_NAVY, font=dict(family="Inter, sans-serif")),
    )
)
pio.templates.default = "databricks"

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="stMetricValue"] { color: #1B3139; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #5C6970; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; }
    h1 { color: #1B3139; font-weight: 800; }
    h2 { color: #1B3139; font-weight: 700; padding-top: 1rem; }
    h3 { color: #1B3139; font-weight: 600; }
    .stSelectbox label { color: #5C6970; font-size: 0.85rem; }
    section[data-testid="stSidebar"] { background-color: #1B3139; }
    section[data-testid="stSidebar"] * { color: #F5F5F5; }
    .question-box {
        background: linear-gradient(135deg, #1B3139 0%, #2d4a55 100%);
        border-left: 4px solid #FF3621;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
        color: white;
    }
    .question-box h2 { color: white !important; margin: 0 0 0.3rem 0; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .question-box p { color: #c8d8dc; margin: 0; font-size: 1.05rem; line-height: 1.5; }
    .insight-box {
        background: #fff8f0;
        border-left: 4px solid #FF9900;
        border-radius: 6px;
        padding: 0.9rem 1.2rem;
        margin: 1rem 0;
    }
    .insight-box strong { color: #1B3139; }
    .deliverable-badge {
        display: inline-block;
        background: #FF3621;
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        margin-bottom: 0.8rem;
    }
    </style>
""", unsafe_allow_html=True)

# ─── DB connection ────────────────────────────────────────────────────────────

@st.cache_resource
def _connection():
    cfg = Config()
    if not WAREHOUSE_ID:
        st.error("No `DATABRICKS_WAREHOUSE_ID` env var set.")
        st.stop()
    return sql.connect(
        server_hostname=cfg.host.replace("https://", "").rstrip("/"),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )

@st.cache_data(ttl=3600, show_spinner="Querying warehouse…")
def q(sql_text: str, **params: Any) -> pd.DataFrame:
    formatted = sql_text.format(GOLD=GOLD, **params)
    with _connection().cursor() as cur:
        cur.execute(formatted)
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns:
        if df[c].dtype == object:
            non_null = df[c].dropna()
            if len(non_null) and isinstance(non_null.iloc[0], Decimal):
                df[c] = df[c].astype(float)
    return df

def kpi(col, label, value, delta=None):
    with col:
        st.metric(label, value, delta)

def style_axis_percent(fig, axis="x"):
    if axis == "x":
        fig.update_xaxes(ticksuffix="%")
    else:
        fig.update_yaxes(ticksuffix="%")
    return fig

def question_box(number, question):
    st.markdown(f"""
        <div class="question-box">
            <h2>Business Question {number}</h2>
            <p>{question}</p>
        </div>
    """, unsafe_allow_html=True)

def insight_box(text):
    st.markdown(f'<div class="insight-box">{text}</div>', unsafe_allow_html=True)

def deliverable_badge(name):
    st.markdown(f'<div class="deliverable-badge">Deliverable: {name}</div>', unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.markdown("# BRFSS 2024")
st.sidebar.caption("Behavioral Risk Factor Surveillance System")
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")

PAGES = {
    "Overview":           "Population summary & chronic disease landscape",
    "Risk Predictors":    "Q1 · Which behaviors most strongly predict disease?",
    "State Benchmarking": "Q2 · How do risk profiles vary by state, income & age?",
    "Care Gap Report":    "Q3 · Where are high-risk groups not accessing care?",
}

page = st.sidebar.radio("View", list(PAGES.keys()), label_visibility="collapsed")
st.sidebar.caption(PAGES[page])
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Source**\n`{GOLD}.*`")
st.sidebar.markdown(f"**Warehouse**\n`{WAREHOUSE_ID or 'unset'}`")
st.sidebar.markdown("---")
st.sidebar.caption("UChicago · ADSP 31012 · Spring 2026")


# =============================================================================
# PAGE: OVERVIEW
# =============================================================================

if page == "Overview":
    st.title("BRFSS 2024 — Health Risk Overview")
    st.caption(
        "Weighted to the US adult population using BRFSS survey weights. "
        "All percentages reflect prevalence in the noninstitutionalized civilian population age 18+."
    )

    st.markdown("""
    This dashboard answers **three core public health questions** using BRFSS 2024 data:
    - **Q1 → Risk Predictors:** Which behavioral risk factors most strongly predict chronic disease?
    - **Q2 → State Benchmarking:** How do risk profiles vary by state, income, and age group?
    - **Q3 → Care Gap Report:** Where are high-risk populations not accessing preventive care?

    Use the sidebar to navigate to each analysis.
    """)

    st.markdown("---")

    kpi_df = q("""
        SELECT COUNT(*) AS n_respondents, SUM(survey_weight) AS weighted_pop,
               COUNT(DISTINCT location_key) AS n_states
        FROM {GOLD}.fact_health_response
    """).iloc[0]

    avg_cond = q("""
        SELECT AVG(cc.condition_count) AS avg_count
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Respondents", f"{int(kpi_df.n_respondents):,}")
    kpi(c2, "Weighted Population", f"{float(kpi_df.weighted_pop)/1e6:.1f}M")
    kpi(c3, "States Covered", f"{int(kpi_df.n_states)}")
    kpi(c4, "Avg Chronic Conditions", f"{float(avg_cond.avg_count):.2f}")

    st.markdown("### Weighted prevalence — chronic conditions")
    cond = q("""
        SELECT 'Arthritis'      AS condition, SUM(CASE WHEN cc.arthritis      THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Depression',     SUM(CASE WHEN cc.depression     THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Asthma',         SUM(CASE WHEN cc.asthma         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Diabetes',       SUM(CASE WHEN cc.diabetes       THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'COPD',           SUM(CASE WHEN cc.copd           THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Cancer',         SUM(CASE WHEN cc.cancer         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Kidney Disease', SUM(CASE WHEN cc.kidney_disease THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Heart Attack',   SUM(CASE WHEN cc.heart_attack   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Stroke',         SUM(CASE WHEN cc.stroke         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
    """).sort_values("pct")

    fig = px.bar(cond, x="pct", y="condition", orientation="h",
                 text=cond["pct"].map(lambda v: f"{v:.1f}%"),
                 labels={"pct": "Prevalence (%)", "condition": ""})
    fig.update_traces(textposition="outside", marker_color=DBX_RED, cliponaxis=False)
    fig.update_layout(height=440, showlegend=False)
    style_axis_percent(fig, "x")
    st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown("### Multimorbidity — conditions per respondent")
        mm = q("""
            SELECT cc.condition_count AS n_conditions, SUM(f.survey_weight)/1e6 AS weighted_pop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            GROUP BY cc.condition_count ORDER BY n_conditions
        """)
        fig = px.bar(mm, x="n_conditions", y="weighted_pop_millions",
                     labels={"n_conditions": "Number of chronic conditions", "weighted_pop_millions": "Weighted population (millions)"})
        fig.update_traces(marker_color=DBX_NAVY)
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("### Diabetes status")
        ds = q("""
            SELECT cc.diabetes_status AS status, SUM(f.survey_weight) AS wpop
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            WHERE cc.diabetes_status IS NOT NULL GROUP BY cc.diabetes_status
        """)
        fig = px.pie(ds, values="wpop", names="status", hole=0.55)
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE: Q1 — RISK PREDICTORS (Clustering)
# =============================================================================

elif page == "Risk Predictors":
    question_box("1", "Which behavioral risk factors most strongly predict chronic disease diagnoses?")
    deliverable_badge("Clustering — Behavioral Risk by Demographic Group")

    st.caption("Explore how smoking, drinking, exercise, and BMI relate to chronic disease rates across population segments.")

    condition_options = {
        "Diabetes":     "diabetes",
        "Heart Attack": "heart_attack",
        "Stroke":       "stroke",
        "Depression":   "depression",
        "COPD":         "copd",
        "Asthma":       "asthma",
    }
    selected_condition = st.selectbox("Analyze condition:", list(condition_options.keys()))
    col_name = condition_options[selected_condition]

    st.markdown("---")

    # Behavioral risk vs disease rate
    st.markdown("### How behavioral risk factors cluster with disease")

    beh_df = q(f"""
        SELECT
            SUM(CASE WHEN b.ever_smoker     AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN b.ever_smoker     THEN f.survey_weight END), 0) * 100 AS smoker_disease_pct,
            SUM(CASE WHEN NOT b.ever_smoker AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN NOT b.ever_smoker  THEN f.survey_weight END), 0) * 100 AS nonsmoker_disease_pct,
            SUM(CASE WHEN b.binge_drinking  AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN b.binge_drinking   THEN f.survey_weight END), 0) * 100 AS binge_disease_pct,
            SUM(CASE WHEN NOT b.binge_drinking AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN NOT b.binge_drinking THEN f.survey_weight END), 0) * 100 AS nobinge_disease_pct,
            SUM(CASE WHEN b.exercise        AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN b.exercise         THEN f.survey_weight END), 0) * 100 AS exercise_disease_pct,
            SUM(CASE WHEN NOT b.exercise    AND cc.{col_name} THEN f.survey_weight END) / NULLIF(SUM(CASE WHEN NOT b.exercise     THEN f.survey_weight END), 0) * 100 AS noexercise_disease_pct
        FROM {{GOLD}}.fact_health_response f
        JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        JOIN {{GOLD}}.dim_behavior b           ON f.behavior_key = b.behavior_key
    """)

    if not beh_df.empty:
        row = beh_df.iloc[0]
        compare_data = pd.DataFrame([
            {"Factor": "Smoking",        "Group": "Ever Smoker",         "Disease Rate (%)": row.get("smoker_disease_pct", 0)},
            {"Factor": "Smoking",        "Group": "Non-Smoker",          "Disease Rate (%)": row.get("nonsmoker_disease_pct", 0)},
            {"Factor": "Binge Drinking", "Group": "Binge Drinker",       "Disease Rate (%)": row.get("binge_disease_pct", 0)},
            {"Factor": "Binge Drinking", "Group": "Non-Binge Drinker",   "Disease Rate (%)": row.get("nobinge_disease_pct", 0)},
            {"Factor": "Exercise",       "Group": "Exercises",           "Disease Rate (%)": row.get("exercise_disease_pct", 0)},
            {"Factor": "Exercise",       "Group": "Does Not Exercise",   "Disease Rate (%)": row.get("noexercise_disease_pct", 0)},
        ])
        fig = px.bar(compare_data, x="Factor", y="Disease Rate (%)", color="Group", barmode="group",
                     text=compare_data["Disease Rate (%)"].map(lambda v: f"{v:.1f}%"),
                     title=f"{selected_condition} rate by behavioral risk factor",
                     color_discrete_sequence=[DBX_RED, DBX_NAVY, DBX_AMBER, DBX_GREEN, DBX_PURPLE, DBX_BLUE])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=420, legend_title="", bargroupgap=0.1,
                          xaxis=dict(categoryorder="array", categoryarray=["Smoking", "Binge Drinking", "Exercise"]))
        style_axis_percent(fig, "y")
        st.plotly_chart(fig, use_container_width=True)

    # BMI x Disease
    st.markdown(f"### {selected_condition} rate by BMI category")
    bmi_disease = q(f"""
        SELECT b.bmi_category_clean AS bmi_category,
               SUM(CASE WHEN cc.{col_name} THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS disease_pct
        FROM {{GOLD}}.fact_health_response f
        JOIN {{GOLD}}.dim_behavior b           ON f.behavior_key = b.behavior_key
        JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        WHERE b.bmi_category_clean IS NOT NULL
        GROUP BY b.bmi_category_clean
    """)
    bmi_order = ["Underweight", "Normal weight", "Overweight", "Obese"]
    bmi_disease["bmi_category"] = pd.Categorical(bmi_disease["bmi_category"], categories=bmi_order, ordered=True)
    bmi_disease = bmi_disease.sort_values("bmi_category")
    fig = px.bar(bmi_disease, x="bmi_category", y="disease_pct",
                 text=bmi_disease["disease_pct"].map(lambda v: f"{v:.1f}%"),
                 color="disease_pct",
                 color_continuous_scale=[[0, DBX_GREEN], [0.5, DBX_AMBER], [1, DBX_RED]])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=380, yaxis_title=f"{selected_condition} prevalence (%)", xaxis_title="BMI category", showlegend=False)
    style_axis_percent(fig, "y")
    st.plotly_chart(fig, use_container_width=True)

    # Demographic clustering
    st.markdown("### Risk factor clustering by demographic group")
    st.caption("Filter by demographic to see which segments carry the heaviest behavioral and disease burden.")

    demo_options = {
        "Age Group": "age_group", "Sex": "sex", "Race / Ethnicity": "race",
        "Income Group": "income_group", "Education": "education",
    }
    demo_label = st.selectbox("Break down by:", list(demo_options.keys()))
    demo_col = demo_options[demo_label]

    demo_df = q(f"""
        SELECT r.{demo_col} AS segment,
               SUM(CASE WHEN b.ever_smoker    THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS smoker_pct,
               SUM(CASE WHEN NOT b.exercise   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS no_exercise_pct,
               SUM(CASE WHEN b.binge_drinking THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS binge_pct,
               SUM(CASE WHEN cc.{col_name}   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS disease_pct
        FROM {{GOLD}}.fact_health_response f
        JOIN {{GOLD}}.dim_respondent r         ON f.respondent_key = r.respondent_key
        JOIN {{GOLD}}.dim_behavior b           ON f.behavior_key = b.behavior_key
        JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        WHERE r.{demo_col} IS NOT NULL
        GROUP BY r.{demo_col}
        ORDER BY disease_pct DESC
    """)

    if not demo_df.empty:
        long = demo_df.melt(id_vars="segment", var_name="Metric", value_name="Prevalence (%)")
        metric_labels = {
            "smoker_pct": "Ever Smoker", "no_exercise_pct": "Does Not Exercise",
            "binge_pct": "Binge Drinker", "disease_pct": selected_condition,
        }
        long["Metric"] = long["Metric"].map(metric_labels)
        fig = px.bar(long, x="segment", y="Prevalence (%)", color="Metric", barmode="group",
                     color_discrete_map={
                         "Ever Smoker": DBX_AMBER, "Does Not Exercise": DBX_GREEN,
                         "Binge Drinker": DBX_PURPLE, selected_condition: DBX_RED,
                     })
        fig.update_layout(height=440, xaxis_title=demo_label, legend_title="")
        style_axis_percent(fig, "y")
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE: Q2 — STATE BENCHMARKING
# =============================================================================

elif page == "State Benchmarking":
    question_box("2", "How do risk profiles vary by state, income bracket, and age group?")
    deliverable_badge("Benchmarking — State-Level Health Department Dashboard")

    st.caption("Compare disease burden against the national average. Use filters to explore by condition, income, and age.")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        condition_options = {
            "Diabetes": "diabetes", "Heart Attack": "heart_attack", "Stroke": "stroke",
            "Depression": "depression", "COPD": "copd", "Asthma": "asthma",
            "Cancer": "cancer", "Arthritis": "arthritis",
        }
        selected_condition = st.selectbox("Condition to analyze:", list(condition_options.keys()))
        col_name = condition_options[selected_condition]

    with col_f2:
        view_by = st.selectbox("Benchmark by:", ["State map", "Income bracket", "Age group"])

    st.markdown("---")

    if view_by == "State map":
        state_df = q(f"""
            SELECT loc.state_code AS state, loc.state_name,
                   SUM(CASE WHEN cc.{col_name} THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct
            FROM {{GOLD}}.fact_health_response f
            JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            JOIN {{GOLD}}.dim_location loc         ON f.location_key = loc.location_key
            WHERE loc.state_code IS NOT NULL
            GROUP BY loc.state_code, loc.state_name ORDER BY pct DESC
        """)
        national_avg = state_df["pct"].mean()
        insight_box(f"<strong>National average:</strong> {national_avg:.1f}% prevalence of {selected_condition}. States above this average are shown in darker red on the map.")

        map_fig = px.choropleth(
            state_df, locations="state", locationmode="USA-states", color="pct",
            scope="usa", hover_name="state_name",
            color_continuous_scale=[[0, DBX_BG], [0.5, "#FFA98F"], [1, DBX_RED]],
            labels={"pct": f"{selected_condition} (%)"},
        )
        map_fig.update_layout(height=500, margin=dict(t=20, b=10, l=10, r=10))
        st.plotly_chart(map_fig, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Top 10 states — highest burden")
            top = state_df.head(10).copy()
            fig = px.bar(top.iloc[::-1], x="pct", y="state_name", orientation="h",
                         text=top.iloc[::-1]["pct"].map(lambda v: f"{v:.1f}%"))
            fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
            fig.update_layout(height=420, yaxis_title="", xaxis_title=f"{selected_condition} (%)", showlegend=False)
            style_axis_percent(fig, "x")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("### Bottom 10 states — lowest burden")
            bot = state_df.tail(10).copy()
            fig = px.bar(bot, x="pct", y="state_name", orientation="h",
                         text=bot["pct"].map(lambda v: f"{v:.1f}%"))
            fig.update_traces(marker_color=DBX_GREEN, textposition="outside", cliponaxis=False)
            fig.update_layout(height=420, yaxis_title="", xaxis_title=f"{selected_condition} (%)", showlegend=False)
            style_axis_percent(fig, "x")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Disease burden vs. Social Vulnerability Index")
        st.caption("Do states with higher social vulnerability carry more disease? Each dot is a state; size = prevalence.")
        svi_df = q("""
            SELECT s.state_code, s.state_name, s.svi_overall, s.pct_uninsured, s.pct_poverty,
                   m.medicaid_expansion_status
            FROM {GOLD}.dim_svi s
            LEFT JOIN {GOLD}.dim_medicaid m ON s.state_name = m.state_name
        """)
        merged = state_df.merge(svi_df.drop(columns=["state_name"]), left_on="state", right_on="state_code", how="inner")
        merged["svi_overall"] = pd.to_numeric(merged["svi_overall"], errors="coerce")
        fig = px.scatter(merged, x="svi_overall", y="pct", size="pct", color="medicaid_expansion_status",
                         hover_name="state_name", size_max=40,
                         labels={"svi_overall": "Social Vulnerability Index (0–1)", "pct": f"{selected_condition} (%)", "medicaid_expansion_status": "Medicaid"})
        fig.update_layout(height=460)
        style_axis_percent(fig, "y")
        st.plotly_chart(fig, use_container_width=True)

    elif view_by == "Income bracket":
        st.markdown(f"### {selected_condition} prevalence by income bracket")
        st.caption("Lower-income groups often face higher disease burden — this view shows the socioeconomic gradient.")

        income_df = q(f"""
            SELECT r.income_group,
                   SUM(CASE WHEN cc.{col_name} THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS disease_pct,
                   SUM(f.survey_weight)/1e6 AS wpop_millions
            FROM {{GOLD}}.fact_health_response f
            JOIN {{GOLD}}.dim_respondent r         ON f.respondent_key = r.respondent_key
            JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            WHERE r.income_group IS NOT NULL
            GROUP BY r.income_group
        """)
        inc_order = ["<$15k", "$15-25k", "$25-35k", "$35-50k", "$50-100k", "$100-200k", ">$200k"]
        income_df["income_group"] = pd.Categorical(income_df["income_group"], categories=inc_order, ordered=True)
        income_df = income_df.sort_values("income_group")
        fig = px.bar(income_df, x="income_group", y="disease_pct",
                     text=income_df["disease_pct"].map(lambda v: f"{v:.1f}%"),
                     color="disease_pct",
                     color_continuous_scale=[[0, DBX_GREEN], [0.5, DBX_AMBER], [1, DBX_RED]])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=420, yaxis_title=f"{selected_condition} prevalence (%)", xaxis_title="Income bracket", showlegend=False)
        style_axis_percent(fig, "y")
        st.plotly_chart(fig, use_container_width=True)

    elif view_by == "Age group":
        st.markdown(f"### {selected_condition} prevalence by age group")
        st.caption("Disease burden typically increases with age — this benchmarks each cohort.")

        age_df = q(f"""
            SELECT r.age_group,
                   SUM(CASE WHEN cc.{col_name} THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS disease_pct
            FROM {{GOLD}}.fact_health_response f
            JOIN {{GOLD}}.dim_respondent r         ON f.respondent_key = r.respondent_key
            JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            WHERE r.age_group IS NOT NULL
            GROUP BY r.age_group
        """)
        age_order = ["18-24","25-29","30-34","35-39","40-44","45-49","50-54","55-59","60-64","65-69","70-74","75-79","80+"]
        age_df["age_group"] = pd.Categorical(age_df["age_group"], categories=age_order, ordered=True)
        age_df = age_df.sort_values("age_group")
        fig = px.line(age_df, x="age_group", y="disease_pct", markers=True,
                      labels={"age_group": "Age group", "disease_pct": f"{selected_condition} prevalence (%)"})
        fig.update_traces(line_color=DBX_RED, marker_color=DBX_NAVY, marker_size=8)
        fig.update_layout(height=400)
        style_axis_percent(fig, "y")
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE: Q3 — CARE GAP REPORT
# =============================================================================

elif page == "Care Gap Report":
    question_box("3", "Where are populations engaging in high-risk behaviors but not accessing preventive care?")
    deliverable_badge("Care Gap Report — Federal Policy / CMS Analytics")

    st.caption("Identify where preventive care is falling short for the highest-risk groups — critical for CMS policy targeting.")

    # Insurance x preventive care
    st.markdown("### Preventive care uptake: Insured vs. Uninsured")
    insight_box("<strong>Key insight:</strong> Uninsured populations consistently under-utilize every preventive service — even low-cost ones like flu shots. This is the core care gap.")

    gap = q("""
        SELECT ha.has_insurance AS insurance,
               SUM(CASE WHEN pc.flu_shot          THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Flu shot`,
               SUM(CASE WHEN pc.pneumo_vaccine    THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Pneumo vaccine`,
               SUM(CASE WHEN pc.colorectal_screen THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Colorectal screen`,
               SUM(CASE WHEN pc.cervical_screen   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Cervical screen`,
               SUM(CASE WHEN pc.mammogram_2yr     THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Mammogram (2yr)`,
               SUM(CASE WHEN pc.hiv_test          THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `HIV test`
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        JOIN {GOLD}.dim_preventive_care pc   ON f.preventive_key = pc.preventive_key
        WHERE ha.has_insurance IS NOT NULL
        GROUP BY ha.has_insurance
    """)
    long = gap.melt(id_vars="insurance", var_name="service", value_name="pct")
    fig = px.bar(long, x="service", y="pct", color="insurance", barmode="group",
                 color_discrete_map={"Insured": DBX_NAVY, "Not Insured": DBX_RED},
                 text=long["pct"].map(lambda v: f"{v:.0f}%"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=440, yaxis_title="Uptake (%)", xaxis_title="", legend_title="Insurance status")
    style_axis_percent(fig, "y")
    st.plotly_chart(fig, use_container_width=True)

    # Cost barrier x condition burden
    st.markdown("### Cost barriers hit the sickest hardest")
    st.caption("People with multiple chronic conditions are most likely to skip care due to cost — the inverse of what good policy should produce.")

    cost = q("""
        SELECT ha.cost_barrier,
               cc.condition_count AS conditions,
               SUM(f.survey_weight)/1e6 AS wpop_millions
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        WHERE ha.cost_barrier IS NOT NULL AND cc.condition_count IS NOT NULL
        GROUP BY ha.cost_barrier, cc.condition_count ORDER BY conditions
    """)
    cost["cost_barrier_lbl"] = cost["cost_barrier"].map({True: "Skipped care due to cost", False: "No cost barrier"})
    fig = px.bar(cost, x="conditions", y="wpop_millions", color="cost_barrier_lbl", barmode="group",
                 color_discrete_map={"Skipped care due to cost": DBX_RED, "No cost barrier": DBX_NAVY},
                 labels={"conditions": "# of chronic conditions", "wpop_millions": "Weighted population (millions)", "cost_barrier_lbl": ""})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    # High-risk + no PCP by state
    st.markdown("### High-risk populations without a primary care provider — by state")
    st.caption("States with the most high-risk, unattached patients are highest-priority targets for CMS outreach.")

    risk_condition = st.selectbox(
        "Show states where these patients lack a PCP:",
        ["diabetes", "heart_attack", "copd", "stroke"],
        format_func=lambda x: x.replace("_", " ").title()
    )

    state_gap = q(f"""
        SELECT loc.state_name,
               SUM(CASE WHEN cc.{risk_condition} AND ha.has_pcp = 'No' THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct_highrisk_no_pcp
        FROM {{GOLD}}.fact_health_response f
        JOIN {{GOLD}}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        JOIN {{GOLD}}.dim_healthcare_access ha ON f.access_key = ha.access_key
        JOIN {{GOLD}}.dim_location loc         ON f.location_key = loc.location_key
        WHERE loc.state_name IS NOT NULL
        GROUP BY loc.state_name
        ORDER BY pct_highrisk_no_pcp DESC
        LIMIT 20
    """)

    fig = px.bar(state_gap.iloc[::-1], x="pct_highrisk_no_pcp", y="state_name", orientation="h",
                 text=state_gap.iloc[::-1]["pct_highrisk_no_pcp"].map(lambda v: f"{v:.1f}%"),
                 labels={"pct_highrisk_no_pcp": "% with condition but no PCP", "state_name": ""})
    fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
    fig.update_layout(height=560, showlegend=False)
    style_axis_percent(fig, "x")
    st.plotly_chart(fig, use_container_width=True)

    # PCP access summary
    st.markdown("### Overall: Does having a PCP close the gap?")
    pcp = q("""
        SELECT ha.has_pcp AS pcp_status, SUM(f.survey_weight) AS wpop
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        WHERE ha.has_pcp IS NOT NULL GROUP BY ha.has_pcp
    """)
    fig = px.pie(pcp, values="wpop", names="pcp_status", hole=0.55,
                 color_discrete_sequence=[DBX_NAVY, DBX_AMBER, DBX_RED],
                 title="Has a personal care provider?")
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
