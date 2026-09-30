import os
import re

import duckdb
import ollama

from prompts import PROMPTS

MODEL = "qwen2.5-coder:7b"
DB_PATH = "store.duckdb"

# Choose the prompt version with:  set PROMPT_VERSION=v2   (default is v4)
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v4")
SYSTEM_PROMPT = PROMPTS[PROMPT_VERSION]

# If OLLAMA_HOST is set (used when running inside Docker), point the client
# at that address instead of the default local one.
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST")
_client = ollama.Client(host=_OLLAMA_HOST) if _OLLAMA_HOST else ollama


def get_schema(con):
    """Describe the database for the AI, including the possible values of
    short text columns (like country or status)."""
    lines = []
    for (table,) in con.execute("SHOW TABLES").fetchall():
        cols = con.execute(f"DESCRIBE {table}").fetchall()
        parts = []
        for col in cols:
            name, ctype = col[0], col[1]
            desc = f"{name} ({ctype}"
            if ctype == "VARCHAR":
                rows = con.execute(
                    f'SELECT DISTINCT "{name}" FROM {table} '
                    f'WHERE "{name}" IS NOT NULL LIMIT 11'
                ).fetchall()
                values = sorted(r[0] for r in rows)
                if len(values) <= 10:  # only short lists, not names or emails
                    desc += ", possible values: " + ", ".join(repr(v) for v in values)
            parts.append(desc + ")")
        lines.append(f"Table {table}: " + ", ".join(parts))
    return "\n".join(lines)


def clean_sql(text):
    """Small models often add extra text or code fences. Strip them off."""
    text = text.strip()
    if "CANNOT_ANSWER" in text:
        return "CANNOT_ANSWER"
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    match = re.search(r"\b(SELECT|WITH)\b", text, flags=re.IGNORECASE)
    if match:
        text = text[match.start():]
    return text.strip()


def question_to_sql(question, schema):
    """Ask the local AI to write SQL for the question."""
    response = _client.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.replace("SCHEMA_HERE", schema)},
            {"role": "user", "content": question},
        ],
        options={
            "temperature": 0,     # 0 = most predictable answers
            "num_predict": 400,   # SQL is short; stop generating after this many tokens
            "num_ctx": 8192,      # bigger context so long prompts don't truncate the answer
        },
        keep_alive="30m",         # keep the model in memory between questions
    )
    return clean_sql(response["message"]["content"])


def run_query(con, sql):
    """Run the SQL and return the results as a table."""
    return con.execute(sql).df()


if __name__ == "__main__":
    con = duckdb.connect(DB_PATH, read_only=True)
    schema = get_schema(con)

    print(f"Prompt version: {PROMPT_VERSION}")
    print("Ask questions about the store (type 'quit' to exit).\n")
    while True:
        question = input("Question: ").strip()
        if question.lower() in ("quit", "exit", ""):
            break

        sql = question_to_sql(question, schema)
        print(f"\nGenerated SQL:\n{sql}\n")

        if sql == "CANNOT_ANSWER":
            print("This can't be answered with this database.\n")
            continue

        try:
            print(run_query(con, sql))
        except Exception as e:
            print(f"Query failed: {e}")
        print()