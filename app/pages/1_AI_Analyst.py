"""AI Analyst page: chat interface for the text-to-SQL agent."""
import time

import streamlit as st

st.set_page_config(page_title="AI Analyst", page_icon="🤖", layout="wide")

from shared import cached_engine, hero, inject_css, render_result  # noqa: E402
from src.agent import ask  # noqa: E402

inject_css()

MAX_QUESTIONS_PER_SESSION = 15
EXAMPLE_QUESTIONS = [
    "What is the total revenue and profit?",
    "Return rate percent by year",
    "Top 5 brands by item net sales",
    "Revenue by customer segment",
    "Which sales channel has the highest revenue?",
    "Average customer rating by region",
]

hero("🤖 AI Analyst", "Ask a business question. The agent writes read-only SQL, "
     "runs it on the marts and shows the result.",
     ["Read-only role", "SQL validation", "Max 200 rows"])

if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = None

st.markdown('<div class="section-title">Try an example</div>', unsafe_allow_html=True)
for chunk in (EXAMPLE_QUESTIONS[:3], EXAMPLE_QUESTIONS[3:]):
    for col, example in zip(st.columns(3), chunk):
        if col.button(example, key=f"ex_{example}"):
            st.session_state.pending = example

st.markdown('<div class="section-title">Conversation</div>', unsafe_allow_html=True)
for item in st.session_state.history:
    with st.chat_message("user", avatar="🧑‍💼"):
        st.write(item["question"])
    with st.chat_message("assistant", avatar="📊"):
        render_result(item)

typed = st.chat_input("Ask a question about orders, customers or products...")
question = typed or st.session_state.pending
st.session_state.pending = None

if question:
    if len(st.session_state.history) >= MAX_QUESTIONS_PER_SESSION:
        st.info(f"Demo limit reached ({MAX_QUESTIONS_PER_SESSION} questions per session). "
                "Refresh the page to start again.")
    else:
        with st.chat_message("user", avatar="🧑‍💼"):
            st.write(question)
        with st.chat_message("assistant", avatar="📊"):
            with st.spinner("Writing and running the SQL..."):
                started = time.perf_counter()
                item = ask(question, engine=cached_engine())
                item["seconds"] = round(time.perf_counter() - started, 1)
            render_result(item)
        st.session_state.history.append(item)

st.caption("Synthetic dataset. Answers come from analytics_marts via a read-only database role.")