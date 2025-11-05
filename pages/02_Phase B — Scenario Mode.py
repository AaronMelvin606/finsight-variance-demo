cat > "pages/02_Phase B — Scenario Mode.py" <<'PY'
import os
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Scenario Mode — FinSight AI", layout="wide")

# ---------- Helpers ----------
@st.cache_data
def load_data():
    # Re-use your demo CSV; adjust path if different in your repo
    path = os.path.join("data", "demo_finance.csv")
    df = pd.read_csv(path)
    # Normalize expected columns
    wanted = {"FY","Period","Entity","Department","Category","CostType","DataType","Amount"}
    missing = wanted - set(df.columns)
    if missing:
        st.warning(f"Columns missing from CSV: {sorted(missing)}. Scenario Mode will try to proceed with what's available.")
    # Clean types
    if "Amount" in df.columns:
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def pct_slider(label, default=0.0, minv=-30.0, maxv=30.0, step=0.5, help_txt=""):
    return st.slider(label, minv, maxv, value=default, step=step, help=help_txt, format="%.1f%%")

def fmt(n): 
    try:
        return f"£{n:,.0f}"
    except Exception:
        return n

def scenario_adjust(df, rev_pct, cogs_pct, direct_pct, indirect_pct, apply_to="Budget"):
    """
    Applies percentage shocks to Budget rows; compares to Actual to produce
    Scenario vs Actual and Scenario vs Budget variances by Category and in total.
    Positive = favourable for profit (so revenue ↑ is favourable, costs ↓ favourable).
    """
    if "DataType" not in df.columns or "Category" not in df.columns:
        st.stop()

    base = df.copy()

    # Split
    is_budget = base["DataType"].str.lower().eq(apply_to.lower()) if "DataType" in base else pd.Series(False, index=base.index)
    scen = base.copy()

    # Map category buckets for shocks
    cat = scen["Category"].str.lower()

    # Revenue shock (+% increases revenue)
    rev_mask = cat.eq("revenue")
    scen.loc[is_budget & rev_mask, "Amount"] *= (1 + rev_pct/100.0)

    # COGS shock (+% increases cost => unfavourable)
    cogs_mask = cat.eq("cost of sales") | cat.eq("cogs")
    scen.loc[is_budget & cogs_mask, "Amount"] *= (1 + cogs_pct/100.0)

    # Direct Opex shock
    direct_mask = cat.eq("direct")
    scen.loc[is_budget & direct_mask, "Amount"] *= (1 + direct_pct/100.0)

    # Indirect Opex shock
    indirect_mask = cat.eq("indirect")
    scen.loc[is_budget & indirect_mask, "Amount"] *= (1 + indirect_pct/100.0)

    # Aggregate to Category x DataType
    keys = [c for c in ["FY","Period","Entity","Department"] if c in scen.columns]
    grp_cols = keys + ["Category","DataType"] if keys else ["Category","DataType"]

    agg_scen = scen.groupby(grp_cols, dropna=False, as_index=False)["Amount"].sum()
    agg_base = base.groupby(grp_cols, dropna=False, as_index=False)["Amount"].sum()

    # Pivot to wide for compare
    def w(df_):
        return df_.pivot_table(index=[c for c in df_.columns if c not in ["Amount","DataType"]],
                               columns="DataType", values="Amount", aggfunc="sum").fillna(0.0)

    w_scen = w(agg_scen).rename_axis(None, axis=1)
    w_base = w(agg_base).rename_axis(None, axis=1)

    # Join
    out = w_scen.join(w_base, lsuffix="_SCEN", rsuffix="_BASE", how="outer").fillna(0.0)

    # Derive variances (Actual - Budget/Scenario) with sign so that positive = favourable to profit
    def profit_sign(row):
        # Revenue is favourable if it goes UP; costs favourable if they go DOWN
        cat = str(row.get("Category","")).lower()
        return 1 if cat == "revenue" else -1

    # Compute totals per column if present
    for col in ["Actual","Budget","Forecast","Plan"]:
        if col not in out.columns:
            out[col] = 0.0
    for col in ["Actual_SCEN","Budget_SCEN","Forecast_SCEN","Plan_SCEN"]:
        if col not in out.columns:
            out[col] = 0.0

    out["Var_SCEN_vs_Actual"] = (out["Actual"] - out["Budget_SCEN"]).apply(float)
    out["Var_BASE_vs_Actual"] = (out["Actual"] - out["Budget"]).apply(float)

    # Favourability
    if "Category" in out.columns:
        signs = out.apply(profit_sign, axis=1)
        out["Var_SCEN_sign"] = out["Var_SCEN_vs_Actual"] * signs
        out["Var_BASE_sign"] = out["Var_BASE_vs_Actual"] * signs
    else:
        out["Var_SCEN_sign"] = out["Var_SCEN_vs_Actual"]
        out["Var_BASE_sign"] = out["Var_BASE_vs_Actual"]

    return out.reset_index()

def waterfall_for_category(out_df):
    if "Category" not in out_df.columns:
        st.info("Category column not found; cannot render waterfall.")
        return

    # Build Budget → Category deltas → Actual (Scenario)
    cat_totals = out_df.groupby("Category", as_index=False)[["Budget_SCEN","Actual"]].sum()
    budget_total = cat_totals["Budget_SCEN"].sum()
    actual_total = cat_totals["Actual"].sum()

    steps = [{"label":"Budget (Scenario)","value":budget_total}]
    for _, r in cat_totals.iterrows():
        delta = r["Actual"] - r["Budget_SCEN"]
        steps.append({"label":str(r["Category"]), "value":delta})
    steps.append({"label":"Actual","value":actual_total - budget_total})

    fig = go.Figure(go.Waterfall(
        name="Scenario",
        orientation="v",
        measure=["absolute"] + ["relative"]*(len(steps)-2) + ["total"],
        x=[s["label"] for s in steps],
        y=[s["value"] for s in steps],
    ))
    fig.update_layout(height=420, margin=dict(l=20,r=20,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

# ---------- UI ----------
st.title("Phase B — Scenario Mode")
df = load_data()

# Basic filter subset (FY/Entity/Department) if present
cols = st.columns(4)
if "FY" in df.columns:
    fy = cols[0].multiselect("FY", sorted(df["FY"].dropna().unique().tolist()), default=sorted(df["FY"].dropna().unique().tolist()))
    df = df[df["FY"].isin(fy)]
if "Entity" in df.columns:
    ent = cols[1].multiselect("Entity", sorted(df["Entity"].dropna().unique().tolist()))
    if ent: df = df[df["Entity"].isin(ent)]
if "Department" in df.columns:
    dep = cols[2].multiselect("Department", sorted(df["Department"].dropna().unique().tolist()))
    if dep: df = df[df["Department"].isin(dep)]

st.subheader("Adjust drivers")
c1,c2,c3,c4 = st.columns(4)
rev = c1.slider("Revenue %", -30.0, 30.0, 0.0, 0.5, help="Increase/decrease revenue vs Budget")
cogs = c2.slider("COGS %",   -30.0, 30.0, 0.0, 0.5, help="Change Cost of Sales vs Budget")
direct = c3.slider("Direct Opex %", -30.0, 30.0, 0.0, 0.5)
indirect = c4.slider("Indirect Opex %", -30.0, 30.0, 0.0, 0.5)

out = scenario_adjust(df, rev, cogs, direct, indirect, apply_to="Budget")

st.subheader("Scenario Impact — by Category")
showcols = [c for c in ["Category","Budget","Actual","Budget_SCEN","Var_BASE_vs_Actual","Var_SCEN_vs_Actual","Var_BASE_sign","Var_SCEN_sign"] if c in out.columns]
st.dataframe(out[showcols].sort_values(by="Category"), use_container_width=True)

st.markdown("#### Scenario Waterfall")
waterfall_for_category(out)

# Totals row
if {"Budget_SCEN","Actual"}.issubset(out.columns):
    b = float(out["Budget_SCEN"].sum())
    a = float(out["Actual"].sum())
    v = a - b
    st.markdown(f"**Totals** — Scenario Budget: {fmt(b)}  |  Actual: {fmt(a)}  |  Variance: {fmt(v)}")
PY

