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
def _get_anthropic_key():
    if not hasattr(st, "secrets"):
        return None
    sec = st.secrets
    # Support either [anthropic].ANTHROPIC_API_KEY, [anthropic].api_key, or top-level ANTHROPIC_API_KEY
    if "anthropic" in sec:
        return sec["anthropic"].get("ANTHROPIC_API_KEY") or sec["anthropic"].get("api_key")
    return sec.get("ANTHROPIC_API_KEY") or sec.get("anthropic_api_key")

from anthropic import Anthropic

def anthropic_client():
    key = _get_anthropic_key()
    if not key:
        return None
    return Anthropic(api_key=key)

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
client = anthropic_client()
if not client:
    st.info("Anthropic key not found; showing fast local commentary.")
    # … local summary fallback …
else:
    # … use client.messages.create( … ) …

    resp = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=300,
        temperature=0.2,
        messages=[{"role":"user","content": user_prompt}],
        system=sys_prompt,
    )
    return resp.content[0].text.strip()

# --- Local fast fallback (used when Anthropic key is missing) ---
def summarize_variance(df):
    """Quick local summary when AI is disabled."""
    total = df["Amount"].sum()
    revenue = df.loc[df["Category"] == "Revenue", "Amount"].sum()
    costs = df.loc[df["Category"].str.contains("Cost", case=False), "Amount"].sum()
    net = revenue - costs

    bullets = [
        f"Overall variance vs plan: £{total:,.0f}",
        f"Revenue: £{revenue:,.0f}",
        f"Costs: £{costs:,.0f}",
        f"Net impact: £{net:,.0f}",
    ]
    return total, bullets

def local_commentary(total_var: float, bullets: list[str]) -> str:
    """Return a single markdown block for the fallback summary."""
    direction = "ahead of plan" if total_var > 0 else "behind plan"
    header = f"Overall, performance is **{direction}** by £{abs(total_var):,.0f}."
    bullet_md = "\n".join(f"- {str(b)}" for b in bullets)
    return f"{header}\n\n{bullet_md}"

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

# --- Ask the data (chat beta) ---
st.divider()
st.subheader("Ask the data (beta)")

# Keep a small, readable table for the model / fallback
def _mini_table(src_df):
    # Department x Category x DataType (Amount), filled & compact
    g = (
        src_df.groupby(["Department", "Category", "DataType"])["Amount"]
        .sum()
        .reset_index()
        .pivot_table(
            index=["Department", "Category"],
            columns="DataType",
            values="Amount",
            fill_value=0.0,
            aggfunc="sum",
        )
        .reset_index()
    )
    # keep it modest in size; Streamlit still shows the full df above
    head_rows = min(len(g), 80)
    return g.head(head_rows)

def _table_to_text(df_):
    # Tight, deterministic text table
    return df_.to_string(index=False)

# Session chat state
if "chat" not in st.session_state:
    st.session_state.chat = []

# Render history
for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

# Input
q = st.chat_input("e.g., Which department contributed most to the positive OPI variance?")
if q:
    st.session_state.chat.append(("user", q))
    with st.chat_message("user"):
        st.markdown(q)

    # Build a compact table based on CURRENT filters on this page
    tbl = _mini_table(df)
    tbl_txt = _table_to_text(tbl)

    # Compose a strict prompt with the KPI rule + active filters
    # (fy_sel, entity_sel, dept_sel are already defined earlier on this page)
    filters_txt = f"Filters → FY: {', '.join(map(str, fy_sel))} | Entity: {', '.join(entity_sel)} | Departments: {', '.join(dept_sel)}"
    kpi_rule = "KPI rule: OPI = Revenue – Cost of Sales – Direct – Indirect (GBP)."
    user_prompt = (
        "You are an FP&A analytics assistant. Answer directly using only the table below.\n"
        f"{kpi_rule}\n"
        "Write 3–5 bullet points max (overall up/down vs budget, top drivers by £), and finish with one crisp recommendation.\n\n"
        f"{filters_txt}\n"
        "Table (Department, Category with KPI columns):\n"
        f"{tbl_txt}\n\n"
        f"Question: {q}\n"
        "Be concise, numeric, and never invent data that is not present in the table."
    )

    # Try Anthropic; fall back to a tiny local heuristic if no key is available
    answer_md = None
    client = anthropic_client() if "anthropic_client" in globals() else None
    try:
        if client:
            resp = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=400,
                temperature=0.2,
                system="You are a precise FP&A assistant. Only use numbers from the provided table.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            answer_md = resp.content[0].text.strip()
        else:
            answer_md = (
                "_AI chat is disabled (no Anthropic key in Secrets). "
                "Add one in Streamlit Cloud to enable this assistant._"
            )
    except Exception as e:
        answer_md = f"_Chat unavailable right now ({type(e).__name__}). Showing table-driven context only._\n\n" \
                    f"**Context summary (local):**\n- Departments included: {', '.join(sorted(df['Department'].dropna().unique().tolist()))}\n" \
                    f"- Rows shown: {len(tbl)}"

    st.session_state.chat.append(("assistant", answer_md))
    with st.chat_message("assistant"):
        st.markdown(answer_md)


