import json
import re

import ollama
import pandas as pd

from text2sql import MODEL, SYSTEM_PROMPT, clean_sql


def ask_model(prompt, system=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = ollama.chat(model=MODEL, messages=messages,
                           options={"temperature": 0}, keep_alive="30m")
    return response["message"]["content"].strip()


# ---------- Check 1: back-translation ----------
def back_translation_score(question, sql):
    """Ask the AI to judge if the SQL answers the question. Returns (score 0-1, note)."""
    prompt = f"""Question asked by a user:
{question}

SQL query written for it:
{sql}

Step 1: In one sentence, say what question this SQL query actually answers.
Step 2: Does that match the user's question? Consider filters, grouping, sorting and limits.

Reply with ONLY a JSON object like:
{{"actual_question": "...", "match_score": 0-10, "problem": "none or short description"}}"""
    raw = ask_model(prompt)
    try:
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))
        score = max(0, min(10, float(data["match_score"]))) / 10
        note = data.get("problem", "none")
        return score, f"AI thinks the SQL answers: \"{data.get('actual_question', '?')}\" (problem: {note})"
    except Exception:
        return 0.5, "Could not parse the AI's judgement (neutral score used)"


# ---------- Check 2: result sanity ----------
def sanity_check(df):
    """Plain-code checks on the results. Returns (score 0-1, list of warnings)."""
    warnings = []
    score = 1.0

    if df.empty:
        return 0.3, ["Query returned no rows. The filter may be wrong, or there is genuinely no data."]

    if df.shape == (1, 1) and pd.isna(df.iloc[0, 0]):
        return 0.2, ["The single result is NULL. Likely a bad filter or JOIN."]

    for col in df.columns:
        null_ratio = df[col].isna().mean()
        if null_ratio > 0.5:
            warnings.append(f"Column '{col}' is {null_ratio:.0%} NULL (possible bad JOIN)")
            score -= 0.2

    numeric = df.select_dtypes("number")
    for col in numeric.columns:
        name = col.lower()
        if (numeric[col] < 0).any():
            warnings.append(f"Column '{col}' has negative values")
            score -= 0.2
        if "count" in name and (numeric[col] > 1_000_000).any():
            warnings.append(f"Column '{col}' has an implausibly large count")
            score -= 0.2

    if len(df) >= 1000:
        warnings.append("Result hit the 1000 row cap, so it may be incomplete")
        score -= 0.1

    return max(0.0, score), warnings


# ---------- Check 3: independent second query ----------
def second_opinion(question, schema, first_sql):
    """Ask the AI to write the SQL again a different way. Returns the new SQL or None."""
    hint = (
        "\n\nWrite the query in a different style than the obvious one "
        "(for example use a different JOIN or subquery structure) while still "
        "answering the question exactly. "
        f"Do NOT copy this query:\n{first_sql}"
    )
    system = SYSTEM_PROMPT.replace("SCHEMA_HERE", schema)
    raw = ask_model(question + hint, system=system)
    sql = clean_sql(raw)
    return None if sql == "CANNOT_ANSWER" else sql


def results_match(df1, df2):
    """Compare two result tables, ignoring column names and row order."""
    if df1.shape != df2.shape:
        return False

    def normalise(df):
        rows = []
        for row in df.itertuples(index=False):
            rows.append(tuple(round(float(v), 2) if isinstance(v, (int, float)) and not pd.isna(v)
                              else str(v) for v in row))
        return sorted(rows)

    try:
        return normalise(df1) == normalise(df2)
    except Exception:
        return False


# ---------- Combine everything ----------
def score_confidence(question, sql, df, schema, run_fn, guard_fn):
    """Run all checks and return a confidence report."""
    signals = {}
    notes = []

    bt_score, bt_note = back_translation_score(question, sql)
    signals["back_translation"] = bt_score
    notes.append(bt_note)

    sanity_score, sanity_warnings = sanity_check(df)
    signals["result_sanity"] = sanity_score
    notes.extend(sanity_warnings)

    second_sql = second_opinion(question, schema, sql)
    agreement = 0.5  # neutral if the second query can't be used
    if second_sql:
        verdict = guard_fn(second_sql)
        if verdict["allowed"]:
            try:
                df2 = run_fn(verdict["sql"])
                agreement = 1.0 if results_match(df, df2) else 0.0
                notes.append("Second independent query " +
                             ("AGREES with the first" if agreement == 1.0
                              else "DISAGREES with the first"))
            except Exception:
                notes.append("Second query failed to run (neutral)")
        else:
            notes.append("Second query was blocked by guardrails (neutral)")
    else:
        notes.append("No usable second query (neutral)")
    signals["query_agreement"] = agreement

    # Weighted average, scaled to 0-100
    weights = {"back_translation": 0.35, "result_sanity": 0.25, "query_agreement": 0.40}
    total = sum(signals[k] * weights[k] for k in weights)
    confidence = round(total * 100)
    # Hard rule: if the results themselves look wrong, never report better than Low
    if signals["result_sanity"] < 0.5:
        confidence = min(confidence, 49)
    label = "High" if confidence >= 75 else "Medium" if confidence >= 50 else "Low"

    return {"confidence": confidence, "label": label, "signals": signals, "notes": notes}