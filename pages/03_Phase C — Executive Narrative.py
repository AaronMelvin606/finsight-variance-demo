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

st.markdown("### Executive Summary (Auto-generated)")
if anthropic_key:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=anthropic_key)

        context = {
            "FY": fy_sel,
            "Entity": entity_sel,
            "Departments": dept_sel,
            "Revenue": sums["Revenue"],
            "Cost of Sales": sums["Cost of Sales"],
            "Direct": sums["Direct"],
            "Indirect": sums["Indirect"],
            "OPI": sums["OPI"],
        }

        prompt = (
            "You are an FP&A copilot. Write a crisp executive summary (5–7 sentences) about the variance performance. "
            "Use CFO tone, avoid fluff, explain drivers and practical actions. Numbers are GBP. "
            f"Here is the JSON context to base your answer on:\n{context}\n"
            "Rules:\n"
            "- Start with OPI performance vs budget and high-level percent.\n"
            "- Attribute drivers to categories. Mention favourable/unfavourable.\n"
            "- Offer 2–3 specific actions (e.g., pricing checks, spend pacing, vendor renegotiations).\n"
        )

        msg = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=500,
            temperature=0.2,
            system="You write CFO-grade variance commentary grounded strictly in provided data.",
            messages=[{"role":"user","content":prompt}],
        )
        st.write(msg.content[0].text)
    except Exception as e:
        st.info("Anthropic not available; showing local fast commentary.")
        total, bullets = local_commentary(sums)
        st.write(f"Overall, performance is **{('ahead of' if sums['OPI']['Var']>=0 else 'behind')} plan** by {money(abs(sums['OPI']['Var']))}.")
        for b in bullets: st.write(f"- {b}")
else:
    total, bullets = local_commentary(sums)
    st.write(f"Overall, performance is **{('ahead of' if sums['OPI']['Var']>=0 else 'behind')} plan** by {money(abs(sums['OPI']['Var']))}.")
    for b in bullets: st.write(f"- {b}")

st.markdown("---")
st.subheader("Ask AI about this view")
st.caption("Ask natural-language questions about the filtered data (uses Claude if a key is present).")

if "chat" not in st.session_state:
    st.session_state.chat = []

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

q = st.chat_input("e.g., Which department contributed most to the positive OPI variance?")
if q:
    st.session_state.chat.append(("user", q))
    with st.chat_message("assistant"):
        if anthropic_key:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_key)
            # Give Claude a compact table summary to reason over
            by_dept = (
                fdf.groupby(["Department","Category","DataType"])["Amount"]
                .sum()
                .reset_index()
                .pivot_table(index=["Department","Category"], columns="DataType", values="Amount", fill_value=0.0)
                .reset_index()
            )
            # Build a small text table (safe length)
            head_rows = min(len(by_dept), 80)
            table_txt = by_dept.head(head_rows).to_string(index=False)
            chat_prompt = (
                "You are an FP&A analytics assistant. Answer strictly from the table and context.\n"
                f"Filters -> FY:{fy_sel} | Entity:{entity_sel} | Departments:{dept_sel}\n"
                "Table columns: Department, Category, Actual, Budget (GBP). OPI = Revenue - Cost of Sales - Direct - Indirect.\n"
                f"Table:\n{table_txt}\n\n"
                f"Question: {q}\n"
                "Give a concise, actionable answer with numbers."
            )
            resp = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=400,
                temperature=0.2,
                system="You are precise and numeric. Never invent data outside the table.",
                messages=[{"role":"user","content":chat_prompt}],
            )
            answer = resp.content[0].text
        else:
            answer = "AI chat is disabled (no Anthropic key in Secrets). Add one to enable this."
        st.markdown(answer)
        st.session_state.chat.append(("assistant", answer))
