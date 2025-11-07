import os
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Phase C — Executive Narrative", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("data/demo_finance.csv")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def money(x):
    return f"£{x:,.0f}"

def summarize_variance(df):
    # Totals by category
    cats = ["Revenue","Cost of Sales","Direct","Indirect"]
    res = {}
    for c in cats:
        a = df.loc[(df["Category"]==c)&(df["DataType"]=="Actual"),"Amount"].sum()
        b = df.loc[(df["Category"]==c)&(df["DataType"]=="Budget"),"Amount"].sum()
        res[c] = {"Actual": float(a), "Budget": float(b), "Var": float(a-b)}
    # OPI
    a_opi = res["Revenue"]["Actual"] - res["Cost of Sales"]["Actual"] - res["Direct"]["Actual"] - res["Indirect"]["Actual"]
    b_opi = res["Revenue"]["Budget"] - res["Cost of Sales"]["Budget"] - res["Direct"]["Budget"] - res["Indirect"]["Budget"]
    res["OPI"] = {"Actual": float(a_opi), "Budget": float(b_opi), "Var": float(a_opi - b_opi)}
    return res

def local_commentary(sums):
    bullets = []
    for k in ["Revenue","Marketing" if "Marketing" in sums else "Direct","Cost of Sales","Indirect"]:
        if k in sums:
            v = sums[k]["Var"]
            sign = "favourable" if v >= 0 else "unfavourable"
            bullets.append(f"{k}: {money(v)} ({sign})")
    total = money(sums["OPI"]["Var"])
    return total, bullets

df = load_data()
st.title("Phase C — Executive Narrative")

# Filters
c1, c2, c3 = st.columns([1,1,2])
with c1:
    fy_sel = st.multiselect("FY", sorted(df["FY"].dropna().unique().tolist()), default=sorted(df["FY"].dropna().unique().tolist()))
with c2:
    entity_sel = st.multiselect("Entity", sorted(df["Entity"].dropna().unique().tolist()), default=sorted(df["Entity"].dropna().unique().tolist()))
with c3:
    dept_sel = st.multiselect("Department", sorted(df["Department"].dropna().unique().tolist()), default=sorted(df["Department"].dropna().unique().tolist()))

mask = df["FY"].isin(fy_sel) & df["Entity"].isin(entity_sel) & df["Department"].isin(dept_sel)
fdf = df.loc[mask].copy()
sums = summarize_variance(fdf)

# === Anthropic (optional) ===
anthropic_key = st.secrets.get("anthropic", {}).get("api_key") if hasattr(st, "secrets") else None

import os
import anthropic
import streamlit as st

def _anthropic_client():
    key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None

def llm_exec_summary(df):
    # small, model-friendly table (Department x Category x DataType → Amount)
    tbl = (
        df.groupby(["Department","Category","DataType"])["Amount"]
          .sum().reset_index()
          .pivot_table(index=["Department","Category"], columns="DataType", values="Amount", fill_value=0.0)
          .reset_index()
          .head(80)  # keep context modest
    )
    # stringify
    table_txt = tbl.to_string(index=False)

    sys_prompt = (
        "You are an FP&A analytics assistant. Use only the table below and be precise.\n"
        "KPI rule: OPI = Revenue – Cost of Sales – Direct – Indirect (GBP).\n"
        "Write 3–5 bullet points: overall up/down vs budget, top drivers (by £), and a crisp recommendation."
    )
    user_prompt = (
        f"Filters → FY: {', '.join(map(str, fy_sel))} | Entity: {', '.join(entity_sel)} | "
        f"Departments: {', '.join(dept_sel)}\n"
        f"Table (Department, Category, Actual, Budget):\n{table_txt}\n"
        "Now generate the executive summary."
    )

    client = _anthropic_client()
    if not client:
        st.info("Anthropic key not found; showing fast local commentary.")
        return None  # caller will fallback

    resp = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=300,
        temperature=0.2,
        messages=[{"role":"user","content": user_prompt}],
        system=sys_prompt,
    )
    return resp.content[0].text.strip()

# --- where you currently render the “Executive Summary (Auto-generated)” ---
st.markdown("### Executive Summary (Auto-generated)")
llm_text = llm_exec_summary(df)
if llm_text:
    st.markdown(llm_text)
else:
    # your existing local summary function as fallback
    total_var, bullets = summarize_variance(df)
    st.markdown(local_commentary(total_var, bullets))
    st.caption("Local fast commentary. Add an Anthropic key in Secrets to enable LLM output.")

