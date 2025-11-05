from passgate import require_password
require_password()

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------------
st.set_page_config(page_title="FinSight AI — SaaS Variance Dashboard", page_icon="👁️", layout="wide")

# -------------------------------------------------------------------
# THEME + BRAND CSS
# -------------------------------------------------------------------
st.markdown("""
<style>
/* --- PAGE LAYOUT --- */
section.main > div {
    padding-top: 0.75rem;
    padding-left: 2rem;
    padding-right: 2rem;
    background-color: #F5F1E8; /* Cream main background */
}

/* --- SIDEBAR --- */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important; /* Clean white sidebar */
    border-right: 1px solid rgba(44,62,42,0.08);
}
[data-testid="stSidebar"] .stMarkdown {
    color: #2C3E2A !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #2C3E2A !important;
}
button[kind="primary"] {
    background-color: #2C3E2A !important;
    color: #FFFFFF !important;
    border-radius: 8px;
}

/* --- KPI CARDS --- */
.finsight-kpi {
    padding: 1rem 1.25rem;
    border-radius: 16px;
    background: #FFFFFF;
    border: 1px solid rgba(44,62,42,0.10);
    box-shadow: 0 1px 4px rgba(44,62,42,0.08);
    color: #2C3E2A;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.finsight-kpi:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 6px rgba(44,62,42,0.12);
}
.finsight-kpi h3 {
    margin: 0 0 .35rem 0;
    font-size: 1.05rem;
    letter-spacing: .2px;
    font-weight: 700;
    color: #2C3E2A;
}
.finsight-kpi .row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}
.finsight-kpi .lbl {
    font-size: .85rem;
    opacity: .75;
    color: #2C3E2A;
}
.finsight-kpi .num {
    font-weight: 800;
    font-size: 1.15rem;
    color: #2C3E2A;
}
.good { color: #2C6E49; }  /* Success green */
.bad { color: #C0392B; }   /* Variance red */

/* --- TABLE + HEADERS --- */
thead tr th {
    background-color: #F5F1E8 !important;
    color: #2C3E2A !important;
    font-weight: 700 !important;
}
tbody tr {
    color: #2C3E2A !important;
    font-size: 0.9rem;
}

/* --- DOWNLOAD BUTTONS --- */
.stDownloadButton > button {
    background-color: #2C3E2A !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    padding: 0.4rem 1rem !important;
    border: none !important;
}
.stDownloadButton > button:hover {
    background-color: #1E2D1B !important;
}

/* --- EXPANDER + DETAILS --- */
.streamlit-expanderHeader {
    background-color: #FFFFFF !important;
    color: #2C3E2A !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------
DATA_PATH = Path(__file__).parent / "data" / "demo_finance.csv"
CURRENCY = "£"
REVENUE_CATS = {"Sales"}
REQUIRED_COLS = ["FY", "Period", "Entity", "Department", "Category", "DataType", "Amount"]

# -------------------------------------------------------------------
# SAFE LOAD + VALIDATION
# -------------------------------------------------------------------
def load_df_safe(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        st.error("📁 Demo data not found. Please contact hello@finsightai.tech")
        st.stop()
    except pd.errors.EmptyDataError:
        st.error("📄 Data file is empty or corrupted.")
        st.stop()
    except Exception as e:
        st.error(f"❗Unexpected error loading data: {e}")
        st.stop()

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        st.error(f"⚠️ Missing required columns: {', '.join(missing)}")
        st.stop()

    if df["Amount"].isna().any():
        st.warning("ℹ️ Some Amount values are NaN. Treating them as 0 for calculations.")
        df["Amount"] = df["Amount"].fillna(0)

    return df

# -------------------------------------------------------------------
# STYLE
# -------------------------------------------------------------------
st.markdown("""
<style>
section.main > div { padding-top:.5rem; }
.finsight-kpi{padding:1rem 1.25rem;border-radius:14px;background:#FFFFFF;border:1px solid rgba(44,62,42,0.10);box-shadow:0 1px 2px rgba(44,62,42,0.06);color:#2C3E2A;}
.finsight-kpi h3{margin:0 0 .35rem 0;font-size:.95rem;letter-spacing:.2px;color:#2C3E2A;opacity:.85;}
.finsight-kpi .row{display:flex;gap:1rem;align-items:baseline;}
.finsight-kpi .lbl{font-size:.8rem;opacity:.8;color:#2C3E2A;}
.finsight-kpi .num{font-weight:800;font-size:1.15rem;color:#2C3E2A;}
.good{color:#2ecc71;} .bad{color:#e74c3c;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------
# DATA LOAD
# -------------------------------------------------------------------
df = load_df_safe(DATA_PATH)
df["DataType"] = df["DataType"].str.title()
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)

# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------
def fmt_cur(x): 
    try: return f"{CURRENCY}{x:,.0f}"
    except: return "—"

def fmt_pct(x):
    if x is None or pd.isna(x): return "—"
    return f"{x:.1%}"

def safe_div(n, d): return np.nan if d == 0 or pd.isna(d) else n / d
def sum_amt(df_, cond): return 0.0 if df_.empty else df_.loc[cond, "Amount"].sum()

def var_by_category(df_):
    pv = df_.pivot_table(index=["Category"], columns="DataType", values="Amount", aggfunc="sum", fill_value=0.0).reset_index()
    pv["Actual"] = pv.get("Actual", 0.0)
    pv["Budget"] = pv.get("Budget", 0.0)
    pv["Var£"] = pv["Actual"] - pv["Budget"]
    pv["Var%"] = pv.apply(lambda r: safe_div(r["Var£"], r["Budget"]), axis=1)
    return pv

def kpi_blocks(fdf, kpi_scope):
    b_rev = sum_amt(kpi_scope, (kpi_scope.Category.isin(REVENUE_CATS)) & (kpi_scope.DataType == "Budget"))
    a_rev = sum_amt(kpi_scope, (kpi_scope.Category.isin(REVENUE_CATS)) & (kpi_scope.DataType == "Actual"))
    v_rev = a_rev - b_rev
    b_cos = sum_amt(fdf, (fdf.Category == "Cost of Sales") & (fdf.DataType == "Budget"))
    a_cos = sum_amt(fdf, (fdf.Category == "Cost of Sales") & (fdf.DataType == "Actual"))
    v_cos = a_cos - b_cos
    b_dir = sum_amt(fdf, (fdf.CostType == "Direct") & (fdf.Category != "Cost of Sales") & (fdf.DataType == "Budget"))
    a_dir = sum_amt(fdf, (fdf.CostType == "Direct") & (fdf.Category != "Cost of Sales") & (fdf.DataType == "Actual"))
    v_dir = a_dir - b_dir
    b_ind = sum_amt(fdf, (fdf.CostType == "Indirect") & (fdf.DataType == "Budget"))
    a_ind = sum_amt(fdf, (fdf.CostType == "Indirect") & (fdf.DataType == "Actual"))
    v_ind = a_ind - b_ind
    b_opi = b_rev - (b_cos + b_dir + b_ind)
    a_opi = a_rev - (a_cos + a_dir + a_ind)
    v_opi = a_opi - b_opi
    return dict(
        revenue=(a_rev, b_rev, v_rev),
        cos=(a_cos, b_cos, v_cos),
        direct=(a_dir, b_dir, v_dir),
        indirect=(a_ind, b_ind, v_ind),
        opi=(a_opi, b_opi, v_opi)
    )

def concise_commentary(fdf, kpi_scope):
    k = kpi_blocks(fdf, kpi_scope)
    a_opi, b_opi, v_opi = k["opi"]
    pct = safe_div(v_opi, b_opi)
    vt = var_by_category(fdf)
    vt["Impact"] = vt.apply(lambda r: r["Var£"] if r["Category"] in REVENUE_CATS else -r["Var£"], axis=1)
    top = vt.assign(abs_imp=lambda d: d["Impact"].abs()).sort_values("abs_imp", ascending=False).head(3)
    drivers = []
    for _, r in top.iterrows():
        arrow = "↑" if r["Impact"] >= 0 else "↓"
        drivers.append(f"{r['Category']} {arrow} {fmt_cur(r['Impact'])}")
    return f"OPI {fmt_cur(a_opi)} vs {fmt_cur(b_opi)} (Δ {fmt_cur(v_opi)}, {fmt_pct(pct)}); driven by " + "; ".join(drivers) + "."

# -------------------------------------------------------------------
# OPI WATERFALL (Budget → Category Impacts → Actual)
# -------------------------------------------------------------------
def opi_waterfall_figure(fdf, kpi_scope):
    k = kpi_blocks(fdf, kpi_scope)
    a_opi, b_opi, _ = k["opi"]

    vt = var_by_category(fdf).copy()
    vt["Impact"] = vt.apply(lambda r: r["Var£"] if r["Category"] in REVENUE_CATS else -r["Var£"], axis=1)
    vt = vt.sort_values("Impact", key=lambda s: s.abs(), ascending=False)

    labels = ["Budget OPI"]
    measures = ["absolute"]
    y = [b_opi]
    text = [fmt_cur(b_opi)]

    for _, r in vt.iterrows():
        labels.append(r["Category"])
        measures.append("relative")
        y.append(r["Impact"])
        text.append(f"{'+' if r['Impact']>=0 else ''}{fmt_cur(r['Impact'])}")

    labels.append("Actual OPI")
    measures.append("total")
    y.append(a_opi)
    text.append(fmt_cur(a_opi))

    fig = go.Figure(go.Waterfall(
        name="OPI",
        orientation="v",
        measure=measures,
        x=labels,
        y=y,
        text=text,
        textposition="outside",
        textfont=dict(size=12),
        hovertemplate="<b>%{x}</b><br>Impact: £%{y:,.0f}<extra></extra>",
        increasing={"marker": {"color": "#2ecc71"}},
        decreasing={"marker": {"color": "#e74c3c"}},
        totals={"marker": {"color": "#2C3E2A"}},
        connector={"line": {"color": "rgba(44,62,42,0.35)"}}
    ))

    fig.update_layout(
        title="OPI Waterfall — Budget → Category Impacts → Actual",
        margin=dict(l=0, r=0, t=48, b=0),
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Amount (£)",
        font=dict(color="#2C3E2A")
    )
    return fig

# -------------------------------------------------------------------
# SIDEBAR FILTERS + BRANDING + RESET
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")

    fy = st.multiselect("FY", sorted(df["FY"].unique()), default=sorted(df["FY"].unique()), key="fy_sel")
    per = st.multiselect("Period", sorted(df["Period"].unique()), default=sorted(df["Period"].unique()), key="per_sel")
    ent = st.multiselect("Entity", sorted(df["Entity"].unique()), default=sorted(df["Entity"].unique()), key="entity_sel")
    dep = st.multiselect("Department", sorted(df["Department"].unique()), default=sorted(df["Department"].unique()), key="dept_sel")
    cat = st.multiselect("Category", sorted(df["Category"].unique()), default=sorted(df["Category"].unique()), key="cat_sel")
    ct = st.multiselect("Cost Type", sorted([c for c in df["CostType"].dropna().unique() if c!=""]),
                        default=sorted([c for c in df["CostType"].dropna().unique() if c!=""]), key="ct_sel")

    st.markdown("---")
    if st.button("🔄 Reset All Filters", use_container_width=True):
        for k in ["fy_sel","per_sel","entity_sel","dept_sel","cat_sel","ct_sel"]:
            if k in st.session_state: st.session_state.pop(k)
        st.rerun()
    st.markdown("---")
    st.markdown("**FinSight AI**  \n[https://finsightai.tech](https://finsightai.tech)  \n*AI-powered intelligence for modern finance*")

# -------------------------------------------------------------------
# FILTERED DATAFRAME
# -------------------------------------------------------------------
mask = (
    df["FY"].isin(fy) &
    df["Period"].isin(per) &
    df["Entity"].isin(ent) &
    df["Department"].isin(dep) &
    df["Category"].isin(cat) &
    (df["CostType"].isin(ct) | (df["CostType"]==""))
)
fdf = df.loc[mask].copy()

if fdf.empty:
    st.warning("No data for the current filter selection.")
    st.stop()

# -------------------------------------------------------------------
# HEADER + KPI + EXEC SUMMARY
# -------------------------------------------------------------------
st.title("FinSight AI — SaaS Variance Dashboard")
st.caption("UK FY (Apr–Mar) • UK entity • KPIs (Revenue, COS, Direct, Indirect, OPI) • OPI waterfall")

sales_scope = df.loc[(df["FY"].isin(fy)) & (df["Period"].isin(per)) & (df["Entity"].isin(ent)) &
                     (df["Department"].isin(dep)) & (df["Category"].isin(REVENUE_CATS))].copy()
kpi_scope = pd.concat([fdf, sales_scope], ignore_index=True)
k = kpi_blocks(fdf, kpi_scope)

c1,c2,c3,c4,c5 = st.columns(5)
for label, vals, col in zip(["Revenue","Cost of Sales","Direct Cost","Indirect Cost","OPI"],
                            [k["revenue"],k["cos"],k["direct"],k["indirect"],k["opi"]],
                            [c1,c2,c3,c4,c5]):
    with col:
        var=vals[2]; good = (label in {"Revenue","OPI"} and var>=0) or (label not in {"Revenue","OPI"} and var<=0)
        col.markdown(f"""
        <div class="finsight-kpi">
          <h3>{label}</h3>
          <div class="row"><span class="lbl">Actual</span><span class="num">{fmt_cur(vals[0])}</span></div>
          <div class="row"><span class="lbl">Budget</span><span class="num">{fmt_cur(vals[1])}</span></div>
          <div class="row"><span class="lbl">Variance</span><span class="num {'good' if good else 'bad'}">{fmt_cur(var)}</span></div>
        </div>
        """, unsafe_allow_html=True)

st.subheader("Executive summary")
st.write(concise_commentary(fdf, kpi_scope))
with st.expander("💡 What this tells us", expanded=False):
    st.markdown("""
**Key takeaways for leadership**
- Operating profit variance is driven by the top-impact categories highlighted below.
- Focus review on departments with persistent adverse trends; rebalance spend toward working drivers.
- Update the rolling forecast to reflect the scenario currently filtered (FY/period/entity/dept).
    """)

# -------------------------------------------------------------------
# DOWNLOAD CSVs
# -------------------------------------------------------------------
st.markdown("### 📥 Export Data")
csv_raw = fdf.to_csv(index=False)
csv_pretty = var_by_category(fdf).to_csv(index=False)
c1,c2 = st.columns(2)
with c1:
    st.download_button("Download (Raw CSV)", data=csv_raw, file_name="raw_finsight_data.csv", mime="text/csv")
with c2:
    st.download_button("Download (Pretty CSV)", data=csv_pretty, file_name="variance_summary.csv", mime="text/csv")

# -------------------------------------------------------------------
# WATERFALL
# -------------------------------------------------------------------
st.subheader("OPI Waterfall — Budget → Category Impacts → Actual")
wf_fig = opi_waterfall_figure(fdf, kpi_scope)
st.plotly_chart(wf_fig, use_container_width=True, config={"displaylogo": False})

# -------------------------------------------------------------------
# DATA CHECK
# -------------------------------------------------------------------
with st.expander("🧭 Data check (current filter context)"):
    st.write(f"Records loaded: **{len(fdf):,}**")
    st.write(f"Departments: {', '.join(sorted(fdf['Department'].unique()))}")
    st.write(f"Categories: {', '.join(sorted(fdf['Category'].unique()))}")
    st.write(f"FY: {', '.join(map(str, sorted(fdf['FY'].unique())))} | Periods: {', '.join(map(str, sorted(fdf['Period'].unique())))}")
    st.dataframe(fdf.head(10), use_container_width=True)

# -------------------------------------------------------------------
# VARIANCE TABLE
# -------------------------------------------------------------------
st.subheader("Variance by Category")
st.dataframe(var_by_category(fdf), use_container_width=True)

