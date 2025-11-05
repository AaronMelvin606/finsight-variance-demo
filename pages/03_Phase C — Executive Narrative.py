import os
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Phase C — Executive Narrative", layout="wide")
st.title("Phase C — Executive Narrative")

@st.cache_data
def load_data():
    path = os.path.join("data", "demo_finance.csv")
    df = pd.read_csv(path)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def summarize_variance(df):
    piv = df.pivot_table(values="Amount", index="Category", columns="DataType", aggfunc="sum").fillna(0.0)
    for col in ["Actual","Budget"]:
        if col not in piv.columns: piv[col] = 0.0
    piv["Var"] = piv["Actual"] - piv["Budget"]
    total_var = float(piv["Var"].sum())
    top = piv["Var"].abs().sort_values(ascending=False).head(3)

    bullets = []
    for cat, val_abs in top.items():
        val = float(piv.loc[cat,"Var"])
        sign = "favourable" if (cat.lower()=="revenue" and val>0) or (cat.lower()!="revenue" and val<0) else "unfavourable"
        prefix = "+" if val>=0 else "−"
        bullets.append(f"- {cat}: {prefix}{abs(val):,.0f} ({sign})")
    return total_var, bullets

def local_commentary(total_var, bullets):
    tone = "ahead" if total_var>0 else "behind"
    body = [
        f"Overall, performance is **{tone} of plan** by **£{abs(total_var):,.0f}**.",
        "Key drivers:",
        *bullets,
        "Recommendation: focus scenario analysis on the top drivers and re-validate run-rate assumptions into next quarter."
    ]
    return "\n".join(body)

df = load_data()

cols = st.columns(3)
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

st.markdown("### Executive Summary (Auto-generated)")
total_var, bullets = summarize_variance(df)
st.markdown(local_commentary(total_var, bullets))

st.caption("Local fast commentary. Add an API key in Secrets later to switch to LLM output with the same inputs.")
