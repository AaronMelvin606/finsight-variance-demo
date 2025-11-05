cat > "pages/03_Phase C — Executive Narrative.py" <<'PY'
import os, math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Executive Narrative — FinSight AI", layout="wide")

@st.cache_data
def load_data():
    path = os.path.join("data", "demo_finance.csv")
    df = pd.read_csv(path)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def summarize_variance(df):
    # Expect Actual/Budget by Category
    piv = df.pivot_table(values="Amount", index="Category", columns="DataType", aggfunc="sum").fillna(0.0)
    for col in ["Actual","Budget"]:
        if col not in piv.columns: piv[col] = 0.0
    piv["Var"] = piv["Actual"] - piv["Budget"]
    total_var = piv["Var"].sum()
    top = piv["Var"].abs().sort_values(ascending=False).head(3)
    bullets = []
    for cat, val in top.items():
        sign = "favourable" if (cat.lower()=="revenue" and val>0) or (cat.lower()!="revenue" and val<0) else "unfavourable"
        bullets.append(f"- {cat}: {('+' if val>=0 else '−')}{abs(val):,.0f} ({sign})")
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

st.title("Phase C — Executive Narrative")
df = load_data()

# Optional: same quick filters as Scenario page
cols = st.columns(3)
if "FY" in df.columns:
    fy = cols[0].multiselect("FY", sorted(df["FY"].dropna().unique().tolist()), default=sorted(df["FY"].dropna().unique().tolist()))
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

st.caption("This is a fast local generator. If you add a Claude/OpenAI key to Streamlit Secrets, we can swap to LLM-powered narratives here with one function call.")
PY

