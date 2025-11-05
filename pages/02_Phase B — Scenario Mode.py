import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Phase B — Scenario Mode", layout="wide")
st.title("Phase B — Scenario Mode")

# ---------- Data ----------
@st.cache_data
def load_data():
    path = os.path.join("data", "demo_finance.csv")
    df = pd.read_csv(path)
    for c in ["Amount"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

def pct_slider(label, default=0.0, minv=-30.0, maxv=30.0, step=0.5, help_txt=""):
    return st.slider(label, minv, maxv, value=default, step=step, help=help_txt, format="%.1f%%")

def scenario_adjust(df, rev_pct, cogs_pct, direct_pct, indirect_pct, apply_to="Budget"):
    if not {"DataType","Category","Amount"}.issubset(df.columns):
        st.error("CSV must include DataType, Category, Amount.")
        st.stop()

    base = df.copy()
    scen = df.copy()

    is_budget = scen["DataType"].str.lower().eq(apply_to.lower())

    cat = scen["Category"].str.lower()
    rev_mask = cat.eq("revenue")
    cogs_mask = cat.isin(["cost of sales","cogs"])
    direct_mask = cat.eq("direct")
    indirect_mask = cat.eq("indirect")

    scen.loc[is_budget & rev_mask, "Amount"] *= (1 + rev_pct/100.0)
    scen.loc[is_budget & cogs_mask, "Amount"] *= (1 + cogs_pct/100.0)
    scen.loc[is_budget & direct_mask, "Amount"] *= (1 + direct_pct/100.0)
    scen.loc[is_budget & indirect_mask, "Amount"] *= (1 + indirect_pct/100.0)

    keys = [c for c in ["FY","Period","Entity","Department"] if c in df.columns]
    grp = keys + ["Category","DataType"]

    agg_scen = scen.groupby(grp, dropna=False, as_index=False)["Amount"].sum()
    agg_base = base.groupby(grp, dropna=False, as_index=False)["Amount"].sum()

    def wide(d):
        return d.pivot_table(index=[c for c in d.columns if c not in ["Amount","DataType"]],
                             columns="DataType", values="Amount", aggfunc="sum").fillna(0.0)

    w_scen = wide(agg_scen).rename_axis(None, axis=1)
    w_base = wide(agg_base).rename_axis(None, axis=1)

    out = w_scen.join(w_base, lsuffix="_SCEN", rsuffix="_BASE", how="outer").fillna(0.0)

    for col in ["Actual","Budget"]:
        if col not in out.columns: out[col] = 0.0
    if "Budget_SCEN" not in out.columns: out["Budget_SCEN"] = 0.0

    out["Var_SCEN_vs_Actual"] = out["Actual"] - out["Budget_SCEN"]
    out["Var_BASE_vs_Actual"] = out["Actual"] - out["Budget"]

    # Profit-friendly sign: revenue↑ favourable; costs↓ favourable
    def favour_sign(row):
        return 1 if str(row.get("Category","")).lower()=="revenue" else -1

    out["Var_SCEN_sign"] = out.apply(lambda r: r["Var_SCEN_vs_Actual"] * favour_sign(r), axis=1)
    out["Var_BASE_sign"] = out.apply(lambda r: r["Var_BASE_vs_Actual"] * favour_sign(r), axis=1)

    return out.reset_index()

def fmt(n): 
    try: return f"£{n:,.0f}"
    except: return n

def waterfall_for_category(out_df):
    if not {"Category","Budget_SCEN","Actual"}.issubset(out_df.columns):
        st.info("Not enough columns for waterfall.")
        return
    cat_totals = out_df.groupby("Category", as_index=False)[["Budget_SCEN","Actual"]].sum()
    budget_total = float(cat_totals["Budget_SCEN"].sum())
    actual_total = float(cat_totals["Actual"].sum())

    steps = [{"label":"Budget (Scenario)","value":budget_total}]
    for _, r in cat_totals.iterrows():
        steps.append({"label":str(r["Category"]), "value": float(r["Actual"]-r["Budget_SCEN"])})
    steps.append({"label":"Actual","value": actual_total - budget_total})

    fig = go.Figure(go.Waterfall(
        name="Scenario",
        orientation="v",
        measure=["absolute"] + ["relative"]*(len(steps)-2) + ["total"],
        x=[s["label"] for s in steps],
        y=[s["value"] for s in steps],
    ))
    fig.update_layout(height=420, margin=dict(l=20,r=20,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

df = load_data()

# Basic filters
cols = st.columns(4)
if "FY" in df.columns:
    fy = cols[0].multiselect("FY", sorted(df["FY"].dropna().unique().tolist()),
                             default=sorted(df["FY"].dropna().unique().tolist()))
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
showcols = [c for c in ["Category","Budget","Actual","Budget_SCEN",
                        "Var_BASE_vs_Actual","Var_SCEN_vs_Actual",
                        "Var_BASE_sign","Var_SCEN_sign"] if c in out.columns]
st.dataframe(out[showcols].sort_values(by="Category"), use_container_width=True)

st.markdown("#### Scenario Waterfall")
waterfall_for_category(out)

if {"Budget_SCEN","Actual"}.issubset(out.columns):
    b = float(out["Budget_SCEN"].sum())
    a = float(out["Actual"].sum())
    v = a - b
    st.markdown(f"**Totals** — Scenario Budget: {fmt(b)}  |  Actual: {fmt(a)}  |  Variance: {fmt(v)}")
