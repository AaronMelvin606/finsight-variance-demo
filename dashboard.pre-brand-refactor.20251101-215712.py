from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ------------------------------
# Page / constants
# ------------------------------
st.set_page_config(page_title="FinSight AI — SaaS Variance Dashboard", page_icon="👁️", layout="wide")
DATA_PATH = Path(__file__).parent / "data" / "demo_finance.csv"
CURRENCY = "£"
REVENUE_CATS = {"Sales"}   # revenue category name

# ------------------------------
# Style helpers
# ------------------------------
st.markdown("""
<style>
section.main > div { padding-top:.5rem; }
.finsight-kpi { padding:1rem 1.25rem; border-radius:14px; background:rgba(31,42,32,0.85);
                border:1px solid rgba(245,241,232,0.08); box-shadow: 0 1px 2px rgba(0,0,0,0.25); }
.finsight-kpi h3 { margin:0 0 .35rem 0; font-size:.95rem; opacity:.85; letter-spacing:.2px; }
.finsight-kpi .row { display:flex; gap:1rem; align-items:baseline; }
.finsight-kpi .lbl { font-size:.8rem; opacity:.8; }
.finsight-kpi .num { font-weight:800; font-size:1.15rem; }
.pill { display:inline-block; padding:.25rem .55rem; border-radius:999px;
        border:1px solid rgba(245,241,232,0.18); background:rgba(31,42,32,.6); margin-right:.35rem; margin-bottom:.35rem; }
.good { color:#2ecc71; } .bad { color:#e74c3c; }
.small { font-size:.9rem; opacity:.9; }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# Data
# ------------------------------
@st.cache_data(show_spinner=False)
def load_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["DataType"] = df["DataType"].str.title()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def fmt_cur(x):
    try: return f"{CURRENCY}{x:,.0f}"
    except: return "—"

def fmt_pct(x):
    if x is None or pd.isna(x): return "—"
    return f"{x:.1%}"

def safe_div(n, d):
    return np.nan if d==0 or pd.isna(d) else n/d

def sum_amt(df, cond):
    if df.empty: return 0.0
    return df.loc[cond, "Amount"].sum()

# ------------------------------
# KPI & variance logic
# ------------------------------
def kpi_blocks(fdf, kpi_scope):
    # Revenue (Sales) from KPI scope (always includes Sales even if table filters exclude it)
    b_rev = sum_amt(kpi_scope, (kpi_scope.Category.isin(REVENUE_CATS)) & (kpi_scope.DataType=="Budget"))
    a_rev = sum_amt(kpi_scope, (kpi_scope.Category.isin(REVENUE_CATS)) & (kpi_scope.DataType=="Actual"))
    v_rev = a_rev - b_rev

    # Costs always respect the visible selection (fdf)
    b_cos = sum_amt(fdf, (fdf.Category=="Cost of Sales") & (fdf.DataType=="Budget"))
    a_cos = sum_amt(fdf, (fdf.Category=="Cost of Sales") & (fdf.DataType=="Actual"))
    v_cos = a_cos - b_cos

    b_dir = sum_amt(fdf, (fdf.CostType=="Direct") & (fdf.Category!="Cost of Sales") & (fdf.DataType=="Budget"))
    a_dir = sum_amt(fdf, (fdf.CostType=="Direct") & (fdf.Category!="Cost of Sales") & (fdf.DataType=="Actual"))
    v_dir = a_dir - b_dir

    b_ind = sum_amt(fdf, (fdf.CostType=="Indirect") & (fdf.DataType=="Budget"))
    a_ind = sum_amt(fdf, (fdf.CostType=="Indirect") & (fdf.DataType=="Actual"))
    v_ind = a_ind - b_ind

    # OPI
    b_opi = b_rev - (b_cos + b_dir + b_ind)
    a_opi = a_rev - (a_cos + a_dir + a_ind)
    v_opi = a_opi - b_opi
    return dict(
        revenue=(a_rev,b_rev,v_rev),
        cos=(a_cos,b_cos,v_cos),
        direct=(a_dir,b_dir,v_dir),
        indirect=(a_ind,b_ind,v_ind),
        opi=(a_opi,b_opi,v_opi)
    )

def kpi_card(label, actual, budget, variance):
    good = (label=="Revenue" and variance>=0) or (label=="OPI" and variance>=0) or (label not in {"Revenue","OPI"} and variance<=0)
    cls = "good" if good else "bad"
    return f"""
    <div class="finsight-kpi">
      <h3>{label}</h3>
      <div class="row"><span class="lbl">Actual</span><span class="num">{fmt_cur(actual)}</span></div>
      <div class="row"><span class="lbl">Budget</span><span class="num">{fmt_cur(budget)}</span></div>
      <div class="row"><span class="lbl">Variance</span><span class="num {cls}">{fmt_cur(variance)}</span></div>
    </div>
    """

def var_by_category(df):
    pv = df.pivot_table(index=["Category"], columns="DataType", values="Amount", aggfunc="sum", fill_value=0.0).reset_index()
    if "Actual" not in pv: pv["Actual"] = 0.0
    if "Budget" not in pv: pv["Budget"] = 0.0
    pv["Var£"] = pv["Actual"] - pv["Budget"]
    pv["Var%"] = pv.apply(lambda r: safe_div(r["Var£"], r["Budget"]), axis=1)
    return pv

def opi_waterfall(fdf, kpi_scope):
    vt = var_by_category(fdf).copy()
    vt["Impact"] = vt.apply(lambda r: r["Var£"] if r["Category"] in REVENUE_CATS else -r["Var£"], axis=1)
    k = kpi_blocks(fdf, kpi_scope)
    b_opi = k["opi"][1]; a_opi = k["opi"][0]

    names=["Budget OPI"]; measures=["absolute"]; values=[b_opi]
    # order by magnitude of OPI impact
    for _, r in vt.assign(abs_imp=lambda d:d["Impact"].abs()).sort_values("abs_imp", ascending=False).iterrows():
        names.append(r["Category"]); measures.append("relative"); values.append(r["Impact"])
    names.append("Actual OPI"); measures.append("total"); values.append(a_opi)

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=names, y=values,
        text=[fmt_cur(v) if isinstance(v,(int,float)) and not pd.isna(v) else "" for v in values],
        connector={"line":{"color":"rgba(245,241,232,0.25)"}},
        decreasing={"marker":{"color":"#c0392b"}}, increasing={"marker":{"color":"#2ecc71"}},
        totals={"marker":{"color":"#8B9D83"}}
    ))
    fig.update_layout(title="OPI Waterfall — Budget → Category Impacts → Actual",
                      showlegend=False, margin=dict(t=40,l=8,r=8,b=8), yaxis_title="Amount")
    return fig

def concise_commentary(fdf, kpi_scope):
    """Offline CFO-style single line (no AI yet)."""
    k = kpi_blocks(fdf, kpi_scope)
    a_opi,b_opi,v_opi = k["opi"]
    pct = safe_div(v_opi, b_opi)
    # Identify top drivers by OPI impact
    vt = var_by_category(fdf)
    vt["Impact"] = vt.apply(lambda r: r["Var£"] if r["Category"] in REVENUE_CATS else -r["Var£"], axis=1)
    top = vt.assign(abs_imp=lambda d:d["Impact"].abs()).sort_values("abs_imp", ascending=False).head(3)
    bits = [f"{fmt_cur(a_opi)} vs {fmt_cur(b_opi)} (Δ {fmt_cur(v_opi)}, {fmt_pct(pct)})"]
    drivers = []
    for _, r in top.iterrows():
        arrow = "↑" if r["Impact"]>=0 else "↓"
        drivers.append(f"{r['Category']} {arrow} {fmt_cur(r['Impact'])}")
    if drivers:
        return f"OPI {', '.join(bits)}; driven by " + "; ".join(drivers) + "."
    return f"OPI {', '.join(bits)}."

# ------------------------------
# App
# ------------------------------
st.title("FinSight AI — SaaS Variance Dashboard")
st.caption("UK FY (Apr–Mar) • UK entity • All table amounts positive • KPIs (Revenue, COS, Direct, Indirect, OPI) • OPI waterfall")

if not DATA_PATH.exists():
    st.error(f"Data not found at {DATA_PATH}"); st.stop()
df = load_df(DATA_PATH)

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    fy  = st.multiselect("FY", sorted(df["FY"].unique()), default=sorted(df["FY"].unique()))
    per = st.multiselect("Period", sorted(df["Period"].unique()), default=sorted(df["Period"].unique()))
    ent = st.multiselect("Entity", sorted(df["Entity"].unique()), default=sorted(df["Entity"].unique()))
    dep = st.multiselect("Department", sorted(df["Department"].unique()), default=sorted(df["Department"].unique()))
    cat = st.multiselect("Category", sorted(df["Category"].unique()), default=sorted(df["Category"].unique()))
    ct  = st.multiselect("Cost Type", sorted([c for c in df["CostType"].dropna().unique() if c!=""]), default=sorted([c for c in df["CostType"].dropna().unique() if c!=""]))
    st.markdown("---")
    auto_rev = st.toggle("Always include Sales in KPI revenue (recommended)", value=True)

# Apply mask
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
    st.warning("No data for the current selection."); st.stop()

# KPI scope: union Sales when toggle is on
if auto_rev:
    sales_scope = df.loc[
        (df["FY"].isin(fy)) & (df["Period"].isin(per)) & (df["Entity"].isin(ent)) &
        (df["Department"].isin(dep)) & (df["Category"].isin(REVENUE_CATS))
    ].copy()
    kpi_scope = pd.concat([fdf, sales_scope], ignore_index=True)
else:
    kpi_scope = fdf

# ----- Scope capsule under title
st.markdown("**Scope**: ", help="Current filter context (for exports and commentary).")
scope_cols = st.columns(2)
with scope_cols[0]:
    st.markdown(
        " ".join([
            f"<span class='pill'>FY: {', '.join(fy)}</span>",
            f"<span class='pill'>Periods: {', '.join(per)}</span>",
            f"<span class='pill'>Entity: {', '.join(ent)}</span>",
        ]), unsafe_allow_html=True
    )
with scope_cols[1]:
    st.markdown(
        " ".join([
            f"<span class='pill'>Dept: {', '.join(dep)}</span>",
            f"<span class='pill'>Cat: {', '.join(cat)}</span>",
            f"<span class='pill'>CostType: {', '.join(ct) if ct else 'All'}</span>",
        ]), unsafe_allow_html=True
    )

# ----- KPI row
k = kpi_blocks(fdf, kpi_scope)
c1,c2,c3,c4,c5 = st.columns(5)
with c1: st.markdown(kpi_card("Revenue", *k["revenue"]), unsafe_allow_html=True)
with c2: st.markdown(kpi_card("Cost of Sales", *k["cos"]), unsafe_allow_html=True)
with c3: st.markdown(kpi_card("Direct Cost", *k["direct"]), unsafe_allow_html=True)
with c4: st.markdown(kpi_card("Indirect Cost", *k["indirect"]), unsafe_allow_html=True)
with c5: st.markdown(kpi_card("OPI", *k["opi"]), unsafe_allow_html=True)

# ----- Executive strip (tight one-liner, non-AI)
st.subheader("Executive summary")
st.write(concise_commentary(fdf, kpi_scope))

# ----- Variance by Category with sort toggle + dual downloads
st.subheader("Variance by Category")
sort_choice = st.radio("Sort by", options=["OPI impact","Var£"], horizontal=True, key="sort_toggle")
vt = var_by_category(fdf)
vt["Impact"] = vt.apply(lambda r: r["Var£"] if r["Category"] in REVENUE_CATS else -r["Var£"], axis=1)
if sort_choice == "OPI impact":
    vt = vt.assign(abs_imp=lambda d:d["Impact"].abs()).sort_values("abs_imp", ascending=False).drop(columns=["abs_imp"])
else:
    vt = vt.sort_values("Var£", key=lambda s:s.abs(), ascending=False)

# Pretty table for display
pretty = vt.copy()
pretty["Budget"] = pretty["Budget"].map(fmt_cur)
pretty["Actual"] = pretty["Actual"].map(fmt_cur)
pretty["Var£"]   = pretty["Var£"].map(fmt_cur)
pretty["Var%"]   = pretty["Var%"].apply(fmt_pct)
pretty["Impact"] = pretty["Impact"].map(fmt_cur)
st.dataframe(pretty, use_container_width=True)

# Dual downloads
st.download_button("Download (Raw CSV)", vt.to_csv(index=False).encode("utf-8"),
                   file_name="variance_by_category_raw.csv", mime="text/csv")
st.download_button("Download (Pretty CSV)", pretty.to_csv(index=False).encode("utf-8"),
                   file_name="variance_by_category_pretty.csv", mime="text/csv")

# ----- OPI Waterfall
st.subheader("OPI Waterfall — Budget → Category Impacts → Actual")
st.plotly_chart(opi_waterfall(fdf, kpi_scope), use_container_width=True, config={"displaylogo": False})

# ----- Data sanity snapshot
with st.expander("Data check (current filter context)"):
    chk = fdf.groupby(["Category","DataType"], as_index=False)["Amount"].sum()\
             .pivot(index="Category", columns="DataType", values="Amount")\
             .fillna(0.0).reset_index()
    st.dataframe(chk, use_container_width=True)
