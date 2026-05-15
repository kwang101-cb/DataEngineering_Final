"""
BRFSS 2024 Chronic Disease Analytics — Databricks App (Streamlit).

Reads from the gold star schema in `data_engineering.gold` via the bound SQL warehouse
and renders weighted prevalence, geographic, demographic, behavioral, and care-gap views.
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

# ─── Databricks visual theme for plotly ──────────────────────────────────────

DBX_RED       = "#FF3621"
DBX_NAVY      = "#1B3139"
DBX_GREEN     = "#00A972"
DBX_BLUE      = "#0073E6"
DBX_AMBER     = "#FF9900"
DBX_PURPLE    = "#7C4DFF"
DBX_BG        = "#F9F7F4"
DBX_GRID      = "#E5E5E5"

DBX_COLORS = [DBX_RED, DBX_NAVY, DBX_GREEN, DBX_BLUE, DBX_AMBER, DBX_PURPLE, "#9C27B0", "#00897B"]

pio.templates["databricks"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, system-ui, -apple-system, sans-serif", size=13, color=DBX_NAVY),
        paper_bgcolor="white",
        plot_bgcolor=DBX_BG,
        colorway=DBX_COLORS,
        title=dict(font=dict(size=20, color=DBX_NAVY), x=0, xanchor="left"),
        xaxis=dict(gridcolor=DBX_GRID, linecolor=DBX_NAVY, zerolinecolor=DBX_GRID),
        yaxis=dict(gridcolor=DBX_GRID, linecolor=DBX_NAVY, zerolinecolor=DBX_GRID),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor=DBX_GRID, borderwidth=1),
        margin=dict(t=60, b=40, l=60, r=20),
        hoverlabel=dict(bgcolor="white", bordercolor=DBX_NAVY, font=dict(family="Inter, sans-serif")),
    )
)
pio.templates.default = "databricks"

# ─── Custom CSS for Databricks-style polish ──────────────────────────────────

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="stMetricValue"] { color: #1B3139; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #5C6970; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; }
    [data-testid="stHorizontalBlock"] { gap: 1rem; }
    h1 { color: #1B3139; font-weight: 800; }
    h2 { color: #1B3139; font-weight: 700; padding-top: 1rem; }
    h3 { color: #1B3139; font-weight: 600; }
    .stSelectbox label { color: #5C6970; font-size: 0.85rem; }
    section[data-testid="stSidebar"] { background-color: #1B3139; }
    section[data-testid="stSidebar"] * { color: #F5F5F5; }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] code {
        background-color: rgba(255,255,255,0.1); color: #FFA98F;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Warehouse connection ────────────────────────────────────────────────────


@st.cache_resource
def _connection():
    cfg = Config()
    if not WAREHOUSE_ID:
        st.error(
            "No `DATABRICKS_WAREHOUSE_ID` env var. Bind a SQL warehouse to this app via "
            "`databricks.yml` → `resources.apps.brfss_analytics_app.resources` or set the var manually."
        )
        st.stop()
    return sql.connect(
        server_hostname=cfg.host.replace("https://", "").rstrip("/"),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


@st.cache_data(ttl=3600, show_spinner="Querying warehouse…")
def q(sql_text: str, **params: Any) -> pd.DataFrame:
    """Run a SQL query and return a pandas DataFrame. Cached for 1 hour.

    databricks-sql-connector returns DECIMAL columns as Python ``Decimal`` objects
    inside an object-dtype Series, which Plotly rejects for numeric props like
    ``size=`` and ``color=``. Auto-convert those columns to float here so the rest
    of the app can treat every numeric column as a real number.
    """
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


# ─── Sidebar navigation ──────────────────────────────────────────────────────

st.sidebar.markdown("# BRFSS 2024")
st.sidebar.caption("Behavioral Risk Factor Surveillance System")
st.sidebar.markdown("---")

PAGES = {
    "Overview":            "Weighted prevalence of chronic conditions and high-level risk factors",
    "Geographic":          "State-level disease prevalence with social vulnerability overlay",
    "Demographics":        "Cross-tabs by age, sex, race, income, and education",
    "Behavioral Risk":     "Smoking, drinking, exercise, diet, and BMI distributions",
    "Care Gaps":           "Where high-risk populations lack preventive access",
}

page = st.sidebar.radio("View", list(PAGES.keys()), label_visibility="collapsed")
st.sidebar.caption(PAGES[page])

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Source**\n`{GOLD}.*`")
st.sidebar.markdown(f"**Warehouse**\n`{WAREHOUSE_ID or 'unset'}`")
st.sidebar.markdown("---")
st.sidebar.caption("UChicago · ADSP 31012 · Spring 2026")


# ─── Reusable helpers ────────────────────────────────────────────────────────


def kpi(col, label: str, value: str, delta: str | None = None):
    with col:
        st.metric(label, value, delta)


def style_axis_percent(fig: go.Figure, axis: str = "x") -> go.Figure:
    if axis == "x":
        fig.update_xaxes(ticksuffix="%")
    else:
        fig.update_yaxes(ticksuffix="%")
    return fig


# ─── Page: OVERVIEW ──────────────────────────────────────────────────────────

if page == "Overview":
    st.title("Health Risk Overview")
    st.caption(
        "Weighted to the US adult population using BRFSS survey weights. "
        "All percentages reflect the prevalence in the noninstitutionalized civilian population age 18+."
    )

    kpi_df = q(
        """
        SELECT
            COUNT(*)                                AS n_respondents,
            SUM(survey_weight)                      AS weighted_pop,
            COUNT(DISTINCT location_key)            AS n_states
        FROM {GOLD}.fact_health_response
        """
    ).iloc[0]

    avg_cond = q(
        """
        SELECT AVG(cc.condition_count) AS avg_count
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        """
    ).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Respondents", f"{int(kpi_df.n_respondents):,}")
    kpi(c2, "Weighted population", f"{float(kpi_df.weighted_pop):,.0f}")
    kpi(c3, "States covered", f"{int(kpi_df.n_states)}")
    kpi(c4, "Avg chronic conditions", f"{float(avg_cond.avg_count):.2f}")

    st.markdown("### Weighted prevalence — chronic conditions")
    cond = q(
        """
        SELECT
            'Arthritis'      AS condition, SUM(CASE WHEN cc.arthritis      THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Depression',     SUM(CASE WHEN cc.depression     THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Asthma',         SUM(CASE WHEN cc.asthma         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Diabetes',       SUM(CASE WHEN cc.diabetes       THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'COPD',           SUM(CASE WHEN cc.copd           THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Cancer',         SUM(CASE WHEN cc.cancer         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Kidney disease', SUM(CASE WHEN cc.kidney_disease THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Heart attack',   SUM(CASE WHEN cc.heart_attack   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        UNION ALL SELECT 'Stroke',         SUM(CASE WHEN cc.stroke         THEN f.survey_weight END) / SUM(f.survey_weight) * 100 FROM {GOLD}.fact_health_response f JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        """
    ).sort_values("pct")

    fig = px.bar(
        cond, x="pct", y="condition", orientation="h",
        text=cond["pct"].map(lambda v: f"{v:.1f}%"),
        labels={"pct": "Prevalence (%)", "condition": ""},
    )
    fig.update_traces(textposition="outside", marker_color=DBX_RED, cliponaxis=False)
    fig.update_layout(height=440, showlegend=False)
    style_axis_percent(fig, "x")
    st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown("### Multimorbidity — count of conditions per respondent")
        mm = q(
            """
            SELECT cc.condition_count AS n_conditions,
                   SUM(f.survey_weight) / 1e6 AS weighted_pop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            GROUP BY cc.condition_count
            ORDER BY n_conditions
            """
        )
        fig = px.bar(
            mm, x="n_conditions", y="weighted_pop_millions",
            labels={"n_conditions": "Number of chronic conditions", "weighted_pop_millions": "Weighted population (millions)"},
        )
        fig.update_traces(marker_color=DBX_NAVY)
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("### Diabetes status")
        ds = q(
            """
            SELECT cc.diabetes_status AS status,
                   SUM(f.survey_weight) AS wpop
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
            WHERE cc.diabetes_status IS NOT NULL
            GROUP BY cc.diabetes_status
            """
        )
        fig = px.pie(ds, values="wpop", names="status", hole=0.55)
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# ─── Page: GEOGRAPHIC ────────────────────────────────────────────────────────

elif page == "Geographic":
    st.title("Geographic Disease Burden")
    st.caption("Choose a metric to map across US states. Hover a state for the underlying value.")

    metric_options = {
        "Diabetes prevalence (%)":     ("diabetes", "cc"),
        "Heart attack prevalence (%)": ("heart_attack", "cc"),
        "Stroke prevalence (%)":       ("stroke", "cc"),
        "Asthma prevalence (%)":       ("asthma", "cc"),
        "Depression prevalence (%)":   ("depression", "cc"),
        "Arthritis prevalence (%)":    ("arthritis", "cc"),
        "Cancer prevalence (%)":       ("cancer", "cc"),
        "COPD prevalence (%)":         ("copd", "cc"),
    }
    metric_label = st.selectbox("Metric", list(metric_options.keys()))
    col_name, alias = metric_options[metric_label]

    state_df = q(
        f"""
        SELECT loc.state_code AS state, loc.state_name,
               SUM(CASE WHEN {alias}.{col_name} THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct
        FROM {{GOLD}}.fact_health_response f
        JOIN {{GOLD}}.dim_chronic_condition {alias} ON f.condition_key = {alias}.condition_key
        JOIN {{GOLD}}.dim_location loc ON f.location_key = loc.location_key
        WHERE loc.state_code IS NOT NULL
        GROUP BY loc.state_code, loc.state_name
        ORDER BY pct DESC
        """
    )

    map_fig = px.choropleth(
        state_df, locations="state", locationmode="USA-states", color="pct",
        scope="usa", hover_name="state_name",
        color_continuous_scale=[[0, DBX_BG], [0.5, "#FFA98F"], [1, DBX_RED]],
        labels={"pct": metric_label},
    )
    map_fig.update_layout(height=520, margin=dict(t=20, b=10, l=10, r=10))
    st.plotly_chart(map_fig, use_container_width=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### Top 10 states")
        top = state_df.head(10).copy()
        fig = px.bar(top.iloc[::-1], x="pct", y="state_name", orientation="h",
                     text=top.iloc[::-1]["pct"].map(lambda v: f"{v:.1f}%"))
        fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
        fig.update_layout(height=420, yaxis_title="", xaxis_title=metric_label, showlegend=False)
        style_axis_percent(fig, "x")
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.markdown("### Bottom 10 states")
        bot = state_df.tail(10).copy()
        fig = px.bar(bot, x="pct", y="state_name", orientation="h",
                     text=bot["pct"].map(lambda v: f"{v:.1f}%"))
        fig.update_traces(marker_color=DBX_GREEN, textposition="outside", cliponaxis=False)
        fig.update_layout(height=420, yaxis_title="", xaxis_title=metric_label, showlegend=False)
        style_axis_percent(fig, "x")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Disease prevalence vs. Social Vulnerability Index")
    svi_df = q(
        """
        SELECT s.state_code, s.state_name, s.svi_overall, s.pct_uninsured, s.pct_poverty,
               m.medicaid_expansion_status
        FROM {GOLD}.dim_svi s
        LEFT JOIN {GOLD}.dim_medicaid m ON s.state_name = m.state_name
        """
    )
    # svi_df also has state_name — drop it before merge so we keep the BRFSS-side label
    # and avoid the _x / _y suffix collision.
    merged = state_df.merge(
        svi_df.drop(columns=["state_name"]),
        left_on="state", right_on="state_code", how="inner",
    )
    merged["svi_overall"] = pd.to_numeric(merged["svi_overall"], errors="coerce")
    fig = px.scatter(
        merged, x="svi_overall", y="pct", size="pct", color="medicaid_expansion_status",
        hover_name="state_name",
        labels={"svi_overall": "Social Vulnerability Index (composite, 0–1)", "pct": metric_label, "medicaid_expansion_status": "Medicaid"},
    )
    fig.update_layout(height=460)
    style_axis_percent(fig, "y")
    st.plotly_chart(fig, use_container_width=True)


# ─── Page: DEMOGRAPHICS ──────────────────────────────────────────────────────

elif page == "Demographics":
    st.title("Demographic Profile")
    st.caption("Weighted composition of the BRFSS adult population by demographics.")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("### Age × Sex")
        age_sex = q(
            """
            SELECT r.age_group, r.sex, SUM(f.survey_weight)/1e6 AS wpop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_respondent r ON f.respondent_key = r.respondent_key
            WHERE r.age_group IS NOT NULL AND r.sex IS NOT NULL
            GROUP BY r.age_group, r.sex
            """
        )
        age_order = ["18-24","25-29","30-34","35-39","40-44","45-49","50-54","55-59","60-64","65-69","70-74","75-79","80+"]
        age_sex["age_group"] = pd.Categorical(age_sex["age_group"], categories=age_order, ordered=True)
        age_sex = age_sex.sort_values("age_group")
        fig = px.bar(
            age_sex, x="age_group", y="wpop_millions", color="sex",
            barmode="group", color_discrete_map={"Male": DBX_NAVY, "Female": DBX_RED},
            labels={"age_group": "Age band", "wpop_millions": "Weighted population (millions)", "sex": ""},
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("### Race / Ethnicity")
        race = q(
            """
            SELECT r.race, SUM(f.survey_weight)/1e6 AS wpop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_respondent r ON f.respondent_key = r.respondent_key
            WHERE r.race IS NOT NULL
            GROUP BY r.race
            ORDER BY wpop_millions DESC
            """
        )
        fig = px.bar(race, x="wpop_millions", y="race", orientation="h",
                     text=race["wpop_millions"].map(lambda v: f"{v:.1f}M"))
        fig.update_traces(marker_color=DBX_NAVY, textposition="outside", cliponaxis=False)
        fig.update_layout(height=400, yaxis_title="", xaxis_title="Weighted population (millions)", showlegend=False, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("### Education")
        edu = q(
            """
            SELECT r.education, SUM(f.survey_weight) AS wpop
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_respondent r ON f.respondent_key = r.respondent_key
            WHERE r.education IS NOT NULL
            GROUP BY r.education
            """
        )
        edu_order = ["< HS", "HS Grad", "Some College", "College Grad"]
        edu["education"] = pd.Categorical(edu["education"], categories=edu_order, ordered=True)
        edu = edu.sort_values("education")
        fig = px.pie(edu, values="wpop", names="education", hole=0.5,
                     color_discrete_sequence=DBX_COLORS)
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("### Income brackets")
        income = q(
            """
            SELECT r.income_group, SUM(f.survey_weight)/1e6 AS wpop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_respondent r ON f.respondent_key = r.respondent_key
            WHERE r.income_group IS NOT NULL
            GROUP BY r.income_group
            """
        )
        inc_order = ["<$15k", "$15-25k", "$25-35k", "$35-50k", "$50-100k", "$100-200k", ">$200k"]
        income["income_group"] = pd.Categorical(income["income_group"], categories=inc_order, ordered=True)
        income = income.sort_values("income_group")
        fig = px.bar(income, x="income_group", y="wpop_millions",
                     text=income["wpop_millions"].map(lambda v: f"{v:.1f}M"))
        fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
        fig.update_layout(height=380, yaxis_title="Weighted population (millions)", xaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# ─── Page: BEHAVIORAL RISK ───────────────────────────────────────────────────

elif page == "Behavioral Risk":
    st.title("Behavioral Risk Factors")
    st.caption("Self-reported behaviors associated with chronic disease, weighted to the population.")

    pct_df = q(
        """
        SELECT
            SUM(CASE WHEN b.exercise          THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Exercise`,
            SUM(CASE WHEN b.ever_smoker       THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Ever smoker`,
            SUM(CASE WHEN b.any_alcohol       THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Any alcohol`,
            SUM(CASE WHEN b.binge_drinking    THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Binge drinking`,
            SUM(CASE WHEN b.heavy_drinker     THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Heavy drinking`
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_behavior b ON f.behavior_key = b.behavior_key
        """
    )
    long = pct_df.T.reset_index()
    long.columns = ["behavior", "pct"]
    long = long.sort_values("pct")

    fig = px.bar(long, x="pct", y="behavior", orientation="h",
                 text=long["pct"].map(lambda v: f"{v:.1f}%"))
    fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
    fig.update_layout(height=380, yaxis_title="", xaxis_title="Prevalence (%)", showlegend=False)
    style_axis_percent(fig, "x")
    st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### Smoking status")
        smk = q(
            """
            SELECT b.smoke_status AS status, SUM(f.survey_weight) AS wpop
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_behavior b ON f.behavior_key = b.behavior_key
            WHERE b.smoke_status IS NOT NULL
            GROUP BY b.smoke_status
            """
        )
        fig = px.pie(smk, values="wpop", names="status", hole=0.55)
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(height=420, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("### BMI distribution")
        bmi = q(
            """
            SELECT b.bmi_category_clean AS category, SUM(f.survey_weight)/1e6 AS wpop_millions
            FROM {GOLD}.fact_health_response f
            JOIN {GOLD}.dim_behavior b ON f.behavior_key = b.behavior_key
            WHERE b.bmi_category_clean IS NOT NULL
            GROUP BY b.bmi_category_clean
            """
        )
        bmi_order = ["Underweight", "Normal weight", "Overweight", "Obese"]
        bmi["category"] = pd.Categorical(bmi["category"], categories=bmi_order, ordered=True)
        bmi = bmi.sort_values("category")
        fig = px.bar(bmi, x="category", y="wpop_millions",
                     text=bmi["wpop_millions"].map(lambda v: f"{v:.1f}M"),
                     color="category",
                     color_discrete_sequence=[DBX_GREEN, DBX_NAVY, DBX_AMBER, DBX_RED])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=420, yaxis_title="Weighted population (millions)", xaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Diabetes prevalence by BMI category")
    bmi_diab = q(
        """
        SELECT b.bmi_category_clean AS bmi,
               SUM(CASE WHEN cc.diabetes THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS pct
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_behavior b           ON f.behavior_key = b.behavior_key
        JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        WHERE b.bmi_category_clean IS NOT NULL
        GROUP BY b.bmi_category_clean
        """
    )
    bmi_diab["bmi"] = pd.Categorical(bmi_diab["bmi"], categories=bmi_order, ordered=True)
    bmi_diab = bmi_diab.sort_values("bmi")
    fig = px.bar(bmi_diab, x="bmi", y="pct", text=bmi_diab["pct"].map(lambda v: f"{v:.1f}%"))
    fig.update_traces(marker_color=DBX_RED, textposition="outside", cliponaxis=False)
    fig.update_layout(height=380, yaxis_title="Diabetes prevalence (%)", xaxis_title="BMI category", showlegend=False)
    style_axis_percent(fig, "y")
    st.plotly_chart(fig, use_container_width=True)


# ─── Page: CARE GAPS ─────────────────────────────────────────────────────────

elif page == "Care Gaps":
    st.title("Preventive Care Gaps")
    st.caption("Where high-risk populations are not connecting to preventive services.")

    gap = q(
        """
        SELECT ha.has_insurance AS insurance,
               SUM(CASE WHEN pc.flu_shot          THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Flu shot`,
               SUM(CASE WHEN pc.pneumo_vaccine   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Pneumo vaccine`,
               SUM(CASE WHEN pc.colorectal_screen THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Colorectal screen`,
               SUM(CASE WHEN pc.cervical_screen   THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Cervical screen`,
               SUM(CASE WHEN pc.mammogram_2yr     THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `Mammogram (2yr)`,
               SUM(CASE WHEN pc.hiv_test          THEN f.survey_weight END) / SUM(f.survey_weight) * 100 AS `HIV test`
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        JOIN {GOLD}.dim_preventive_care pc   ON f.preventive_key = pc.preventive_key
        WHERE ha.has_insurance IS NOT NULL
        GROUP BY ha.has_insurance
        """
    )
    long = gap.melt(id_vars="insurance", var_name="service", value_name="pct")
    fig = px.bar(long, x="service", y="pct", color="insurance", barmode="group",
                 color_discrete_map={"Insured": DBX_NAVY, "Not Insured": DBX_RED},
                 text=long["pct"].map(lambda v: f"{v:.0f}%"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=440, yaxis_title="Uptake (%)", xaxis_title="", legend_title="")
    style_axis_percent(fig, "y")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Cost barrier × condition burden")
    cost = q(
        """
        SELECT ha.cost_barrier AS cost_barrier,
               cc.condition_count AS conditions,
               SUM(f.survey_weight)/1e6 AS wpop_millions
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        JOIN {GOLD}.dim_chronic_condition cc ON f.condition_key = cc.condition_key
        WHERE ha.cost_barrier IS NOT NULL AND cc.condition_count IS NOT NULL
        GROUP BY ha.cost_barrier, cc.condition_count
        ORDER BY conditions
        """
    )
    cost["cost_barrier_lbl"] = cost["cost_barrier"].map({True: "Skipped care due to cost", False: "No cost barrier"})
    fig = px.bar(cost, x="conditions", y="wpop_millions", color="cost_barrier_lbl",
                 barmode="group",
                 color_discrete_map={"Skipped care due to cost": DBX_RED, "No cost barrier": DBX_NAVY},
                 labels={"conditions": "# of chronic conditions", "wpop_millions": "Weighted population (millions)", "cost_barrier_lbl": ""})
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Care access composition")
    pcp = q(
        """
        SELECT ha.has_pcp AS pcp_status, SUM(f.survey_weight) AS wpop
        FROM {GOLD}.fact_health_response f
        JOIN {GOLD}.dim_healthcare_access ha ON f.access_key = ha.access_key
        WHERE ha.has_pcp IS NOT NULL
        GROUP BY ha.has_pcp
        """
    )
    fig = px.pie(pcp, values="wpop", names="pcp_status", hole=0.55,
                 color_discrete_sequence=[DBX_NAVY, DBX_AMBER, DBX_RED])
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(height=400, showlegend=False, title_text="Has a personal care provider?")
    st.plotly_chart(fig, use_container_width=True)
