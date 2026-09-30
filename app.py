import time

import duckdb
import pandas as pd
import streamlit as st

from guardrails import check_sql, log_blocked
from text2sql import DB_PATH, PROMPT_VERSION, get_schema, question_to_sql, run_query
from validator import sanity_check

st.set_page_config(page_title="Text-to-SQL Assistant", page_icon="🗄️", layout="wide")


@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


@st.cache_data
def get_cached_schema():
    return get_schema(get_connection())


con = get_connection()
schema = get_cached_schema()

st.title("🗄️ Text-to-SQL Assistant")
st.caption(f"Ask questions about the store database in plain English. "
           f"Running locally with Ollama · prompt version: {PROMPT_VERSION}")

with st.sidebar:
    st.subheader("About this project")
    st.write(
        "This assistant translates natural language into SQL, runs it through "
        "safety guardrails before execution, and flags results that look wrong. "
        "It only has read-only access to the database."
    )
    st.subheader("Try asking")
    for example in [
        "What are the top 5 products by revenue?",
        "How many customers are there in each country?",
        "What was total revenue in 2024?",
        "Delete all customers from India",
    ]:
        if st.button(example, use_container_width=True):
            st.session_state["question"] = example

    st.subheader("Database schema")
    st.code(schema, language="text")

question = st.text_input(
    "Your question",
    key="question",
    placeholder="e.g. What are the top 5 products by revenue?",
)

if st.button("Ask", type="primary") or question:
    if not question.strip():
        st.stop()

    start = time.time()
    with st.spinner("Writing SQL..."):
        sql = question_to_sql(question, schema)

    if sql == "CANNOT_ANSWER":
        st.warning("This can't be answered with the current database.")
        st.stop()

    verdict = check_sql(sql)
    if not verdict["allowed"]:
        log_blocked(question, sql, verdict["reasons"])
        st.error("🚫 Blocked by safety guardrails")
        st.code(sql, language="sql")
        for reason in verdict["reasons"]:
            st.write(f"- {reason}")
        st.stop()

    st.subheader("Generated SQL")
    st.code(verdict["sql"], language="sql")

    with st.spinner("Running query..."):
        try:
            df = run_query(con, verdict["sql"])
        except Exception as e:
            st.error(f"Query failed: {e}")
            st.stop()

    st.subheader("Results")
    st.dataframe(df, use_container_width=True)

    score, warnings = sanity_check(df)
    elapsed = time.time() - start

    col1, col2 = st.columns(2)
    with col1:
        if warnings:
            st.warning("⚠️ Result sanity check flagged this answer")
            for w in warnings:
                st.write(f"- {w}")
        else:
            st.success("✅ Passed automated sanity checks")
    with col2:
        st.metric("Response time", f"{elapsed:.1f}s")

    if len(df) > 1 and df.select_dtypes("number").shape[1] >= 1:
        with st.expander("📊 Quick chart"):
            numeric_cols = df.select_dtypes("number").columns.tolist()
            label_cols = [c for c in df.columns if c not in numeric_cols]
            if numeric_cols and label_cols:
                chart_df = df.set_index(label_cols[0])[numeric_cols]
                st.bar_chart(chart_df)