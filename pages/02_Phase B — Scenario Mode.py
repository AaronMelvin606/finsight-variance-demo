import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Phase B — Scenario Mode", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("data/demo_finance.csv")
    # Ensure column names are as expected:
    # ['FY','Period','Entity','Department','Category','CostType','DataType','Amount']
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    return df

def money(x):  # £123,456 style
    return f"£{x:,.0f}"

def kpi_tile(title, scenario_amt, budget_amt):
    var = scenario_amt - budget_amt
    delta_txt = f"{money(var)}"
    # Simple tile styling
    st.markdown(
        f"""
        <div style="padding:1.25rem;border:1px solid #ddd;border-radius:12px;background:#fff;">
          <div style="font-size:1.1rem;color:#344e41;margin-bottom:0.35rem;">{title}</div>
          <div style="display:flex;gap:1.75rem;flex-wrap:wrap;">
            <div><div style="color:#5f6c62;">Scenario</div><div style="font-weight:700;font-size:1.6rem;">{money(scenario_amt)}</div></div>
            <div><div style="color:#5f6c62;">Budget</div><div style="font-weight:700;font-size:1.6rem;">{money(budget_amt)}</div></div>
            <div><div style="color:#5f6c62;">Variance</div><div style="font-weight:700;font-size:1.6rem;">{delta_txt}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

df = load_data()
st.title("Phase B — Scenario Mode")

# === Filters (mirror the main dashboard) ===
c1, c2, c3 = st.columns([1,1,2])
with c1:
    fy_sel = st.multiselect("FY", sorted(df["FY"].dropna().unique().tolist()), default=sorted(df["FY"].dropna().unique().tolist()))
with c2:
    entity_sel = st.multiselect("Entity", sorted(df["Entity"].dropna().unique().tolist()), default=sorted(df["Entity"].dropna().unique().tolist()))
with c3:
    dept_sel = st.multiselect("Department", sorted(df["Department"].dropna().unique().tolist()), default=sorted(df["Department"].dropna().unique().tolist()))

mask = (
    df["FY"].isin(fy_sel) &
    df["Entity"].isin(entity_sel) &
    df["Department"].isin(dept_sel)
)
fdf = df.loc[mask].copy()

# === Scenario sliders ===
st.markdown("#### Scenario Adjustments (%)")
s1, s2, s3, s4 = st.columns(4)
with s1:
    rev_pct = st.slider("Revenue %", -20, 20, 0, 1)
with s2:
    cogs_pct = st.slider("COGS %", -20, 20, 0, 1)
with s3:
    direct_pct = st.slider("Direct %", -20, 20, 0, 1)
with s4:
    indirect_pct = st.slider("Indirect %", -20, 20, 0, 1)

adj = {
    "Revenue": 1.0 + (rev_pct / 100.0),
    "Cost of Sales": 1.0 + (cogs_pct / 100.0),
    "Direct": 1.0 + (direct_pct / 100.0),
    "Indirect": 1.0 + (indirect_pct / 100.0),
}

# === Pivot helpers ===
def sum_amount(category, datatype):
    m = (fdf["Category"] == category) & (fdf["DataType"] == datatype)
    return float(fdf.loc[m, "Amount"].sum())

# Budget + Actual by category
B_rev   = sum_amount("Revenue", "Budget")
B_cogs  = sum_amount("Cost of Sales", "Budget")
B_dir   = sum_amount("Direct", "Budget")
B_ind   = sum_amount("Indirect", "Budget")
B_OPI   = B_rev - B_cogs - B_dir - B_ind

A_rev   = sum_amount("Revenue", "Actual")
A_cogs  = sum_amount("Cost of Sales", "Actual")
A_dir   = sum_amount("Direct", "Actual")
A_ind   = sum_amount("Indirect", "Actual")
A_OPI   = A_rev - A_cogs - A_dir - A_ind

# Scenario = Actual scaled by sliders
S_rev   = A_rev * adj["Revenue"]
S_cogs  = A_cogs * adj["Cost of Sales"]
S_dir   = A_dir * adj["Direct"]
S_ind   = A_ind * adj["Indirect"]
S_OPI   = S_rev - S_cogs - S_dir - S_ind

st.markdown("### Scenario vs Budget — KPI Tiles")
col1, col2, col3, col4 = st.columns(4)
with col1: kpi_tile("Revenue", S_rev, B_rev)
with col2: kpi_tile("Cost of Sales", S_cogs, B_cogs)
with col3: kpi_tile("Direct", S_dir, B_dir)
with col4: kpi_tile("Indirect", S_ind, B_ind)

st.markdown("---")
st.subheader("OPI (Scenario vs Budget)")
st.markdown(
    f"**Scenario OPI:** {money(S_OPI)}  •  **Budget OPI:** {money(B_OPI)}  •  **Variance:** {money(S_OPI - B_OPI)}"
)
