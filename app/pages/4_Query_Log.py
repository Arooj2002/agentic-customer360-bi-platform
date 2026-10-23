"""Query Log: what the AI agent was asked in this session."""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Query Log", page_icon="🧾", layout="wide")

from shared import hero, inject_css  # noqa: E402

inject_css()

hero("🧾 Query Log", "Every question, generated SQL, status and latency for this session.",
     ["Observability", "Session only"])

history = st.session_state.get("history", [])
if not history:
    st.info("No questions yet. Ask something on the AI Analyst page and come back.")
    st.stop()

rows = [{
    "Question": item["question"],
    "Status": "OK" if not item["error"] else "Failed",
    "Rows": 0 if item["data"] is None else len(item["data"]),
    "Seconds": item.get("seconds"),
    "Tokens": item["tokens"],
    "SQL": item["sql"],
} for item in history]
log = pd.DataFrame(rows)

ok = int((log["Status"] == "OK").sum())
cards = [("Questions", str(len(log))), ("Succeeded", str(ok)), ("Failed", str(len(log) - ok)),
         ("Avg seconds", f"{log['Seconds'].mean():.1f}")]
for col, (label, value) in zip(st.columns(4), cards):
    col.markdown(f'<div class="kpi"><div class="label">{label}</div>'
                 f'<div class="value">{value}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">History</div>', unsafe_allow_html=True)
st.dataframe(log, hide_index=True, width="stretch")
st.caption("The log lives in this browser session only. The agent role is read-only, "
           "so nothing is written to the database.")