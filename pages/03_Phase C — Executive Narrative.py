# pages/03_Phase C — Executive Narrative.py
import os
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Phase C — Executive Narrative", layout="wide")

# ----------------------- Data -----------------------
@st.cache_data
def load_data():
    df = pd.read_csv("data/demo_finance.csv")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def money(x: float) -> str:
    return f"£{x:,.0f}"

# Category-level rollup used by the local fallback
def variance_by_category(df: pd.DataFrame) -> dict:
    cats = ["Revenue", "Cost of Sales", "Direct", "Indirect"]
    res = {}
    for c in cats:
        a = df.loc[(df["Category"] == c) & (df["DataType"] == "Actual"), "Amount"].sum()
        b = df.loc[(df["Category"] == c) & (df["DataType"] == "Budget"), "Amount"].sum()
        res[c] = {"Actual": float(a), "Budget": float(b), "Var": float(a - b)}
    a_opi = res["Revenue"]["Actual"] - res["Cost of Sales"]["Actual"] - res["Direct"]["Actual"] - res["Indirect"]["Actual"]
    b_opi = res["Revenue"]["Budget"] - res["Cost of Sales"]["Budget"] - res["Direct"]["Budget"] - res["Indirect"]["Budget"]
    res["OPI"] = {"Actual": float(a_opi), "Budget": float(b_opi), "Var": float(a_opi - b_opi)}
    return res

def local_commentary_from_rollup(sums: dict) -> tuple[float, list[str]]:
    bullets = []
    # Prefer Marketing if present, else Direct (keeps your original behavior)
    order = ["Revenue", "Marketing" if "Marketing" in sums else "Direct", "Cost of Sales", "Indirect"]
    for k in order:
        if k in sums:
            v = sums[k]["Var"]
            sign = "favourable" if v >= 0 else "unfavourable"
            bullets.append(f"{k}: {money(v)} ({sign})")
    total = sums.get("OPI", {}).get("Var", 0.0)
    return total, bullets

def render_local_summary(df: pd.DataFrame) -> str:
    sums = variance_by_category(df)
    total_var, bullets = local_commentary_from_rollup(sums)
    direction = "ahead of plan" if total_var >= 0 else "behind plan"
    header = f"Overall, performance is **{direction}** by {money(abs(total_var))}."
    bullet_md = "\n".join(f"- {b}" for b in bullets)
    return f"{header}\n\n{bullet_md}"

# ----------------------- Anthropic client helpers -----------------------
def _get_anthropic_key() -> str | None:
    """Read from Streamlit Secrets (sectioned or top-level), else env."""
    try:
        # Check [anthropic] section
        if "anthropic" in st.secrets:
            sect = st.secrets["anthropic"]
            if "ANTHROPIC_API_KEY" in sect:
                return sect["ANTHROPIC_API_KEY"]
            if "api_key" in sect:
                return sect["api_key"]
        # Check top-level keys
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
        if "anthropic_api_key" in st.secrets:
            return st.secrets["anthropic_api_key"]
    except Exception:
        pass
    # Fallback for local environment variable
    return os.environ.get("ANTHROPIC_API_KEY")


# Optional: debug visibility check (you can remove after verifying)
st.caption(f"Secrets sections: {list(getattr(st, 'secrets', {}).keys())}")
st.caption(f"Key visible to app: {bool(_get_anthropic_key())}")

# ----------------------- LLM Executive Summary -----------------------
def llm_exec_summary(fdf: pd.DataFrame, fy_sel, entity_sel, dept_sel) -> str | None:
    client = _anthropic_client()
    if not client:
        return None

    # Compact, model-friendly table
    tbl = (
        fdf.groupby(["Department", "Category", "DataType"])["Amount"]
        .sum().reset_index()
        .pivot_table(
            index=["Department", "Category"],
            columns="DataType",
            values="Amount",
            fill_value=0.0,
            aggfunc="sum",
        )
        .reset_index()
    )
    table_txt = tbl.head(80).to_string(index=False)

    sys_prompt = (
        "You are an FP&A analytics assistant. Use only the table provided.\n"
        "KPI rule: OPI = Revenue – Cost of Sales – Direct – Indirect (GBP).\n"
        "Write 3–5 bullets: overall up/down vs budget, top drivers (by £), and one crisp recommendation."
    )
    user_prompt = (
        f"Filters → FY: {', '.join(map(str, fy_sel))} | Entity: {', '.join(entity_sel)} | Departments: {', '.join(dept_sel)}\n"
        f"Table (Department, Category with Actual/Budget):\n{table_txt}\n"
        "Now generate the executive summary."
    )

    resp = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=300,
        temperature=0.2,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text.strip()

# ----------------------- UI -----------------------
df = load_data()
st.title("Phase C — Executive Narrative")

# Filters
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    fy_sel = st.multiselect("FY", sorted(df["FY"].dropna().unique().tolist()),
                            default=sorted(df["FY"].dropna().unique().tolist()))
with c2:
    entity_sel = st.multiselect("Entity", sorted(df["Entity"].dropna().unique().tolist()),
                                default=sorted(df["Entity"].dropna().unique().tolist()))
with c3:
    dept_sel = st.multiselect("Department", sorted(df["Department"].dropna().unique().tolist()),
                              default=sorted(df["Department"].dropna().unique().tolist()))

mask = df["FY"].isin(fy_sel) & df["Entity"].isin(entity_sel) & df["Department"].isin(dept_sel)
fdf = df.loc[mask].copy()

# Executive Summary
st.markdown("### Executive Summary (Auto-generated)")
llm_text = llm_exec_summary(fdf, fy_sel, entity_sel, dept_sel)
if llm_text:
    st.markdown(llm_text)
else:
    st.info("Anthropic key not found; showing fast local commentary.")
    st.markdown(render_local_summary(fdf))
    st.caption("Local fast commentary. Add an Anthropic key in Secrets to enable LLM output.")

# ----------------------- Ask the data (beta) -----------------------
st.divider()
st.subheader("Ask the data (beta)")

def _mini_table(src_df: pd.DataFrame) -> pd.DataFrame:
    g = (
        src_df.groupby(["Department", "Category", "DataType"])["Amount"]
        .sum().reset_index()
        .pivot_table(index=["Department", "Category"], columns="DataType",
                     values="Amount", fill_value=0.0, aggfunc="sum")
        .reset_index()
    )
    return g.head(min(len(g), 80))

def _table_to_text(df_: pd.DataFrame) -> str:
    return df_.to_string(index=False)

if "chat" not in st.session_state:
    st.session_state.chat = []

for role, msg in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(msg)

q = st.chat_input("e.g., Which department contributed most to the positive OPI variance?")
if q:
    st.session_state.chat.append(("user", q))
    with st.chat_message("user"):
        st.markdown(q)

    tbl = _mini_table(fdf)
    tbl_txt = _table_to_text(tbl)

    filters_txt = f"Filters → FY: {', '.join(map(str, fy_sel))} | Entity: {', '.join(entity_sel)} | Departments: {', '.join(dept_sel)}"
    kpi_rule = "KPI rule: OPI = Revenue – Cost of Sales – Direct – Indirect (GBP)."
    user_prompt = (
        "You are an FP&A analytics assistant. Answer directly using only the table below.\n"
        f"{kpi_rule}\n"
        "Write at most 3–5 bullets, numeric, and finish with one crisp recommendation.\n\n"
        f"{filters_txt}\n"
        "Table (Department, Category with KPI columns):\n"
        f"{tbl_txt}\n\n"
        f"Question: {q}\n"
        "Be concise, numeric, and never invent data that is not present in the table."
    )

    answer_md = None
    client = _anthropic_client()
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
        answer_md = (
            f"_Chat unavailable right now ({type(e).__name__}). Showing table-driven context only._\n\n"
            f"**Context summary (local):**\n"
            f"- Departments included: {', '.join(sorted(fdf['Department'].dropna().unique().tolist()))}\n"
            f"- Rows shown: {len(tbl)}"
        )

    st.session_state.chat.append(("assistant", answer_md))
    with st.chat_message("assistant"):
        st.markdown(answer_md)
