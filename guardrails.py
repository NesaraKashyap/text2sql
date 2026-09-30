import json
import re
from datetime import datetime

MAX_ROWS = 1000
MAX_SUBQUERY_DEPTH = 3
LOG_FILE = "blocked_queries.log"

BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "ATTACH", "DETACH", "COPY", "EXPORT", "IMPORT", "PRAGMA", "INSTALL",
    "LOAD", "CALL", "GRANT", "REVOKE", "MERGE", "VACUUM", "EXECUTE",
]

# Functions that can read files, run hidden SQL, or expose system info
BLOCKED_FUNCTION_PATTERN = re.compile(
    r"\b(read_\w+|\w+_scan|glob|query|query_table|sniff_csv|getenv|"
    r"duckdb_\w+|pragma_\w+|current_setting)\s*\(",
    re.IGNORECASE,
)


def strip_strings(sql):
    """Replace the inside of 'text in quotes' so words inside it don't trigger rules.
    Example: WHERE name = 'Update' should not be flagged as an UPDATE command."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def subquery_depth(sql):
    """Count how deeply (SELECT ...) blocks are nested inside each other."""
    depth = 0
    max_depth = 0
    stack = []
    for i, ch in enumerate(sql):
        if ch == "(":
            is_sub = re.match(r"\s*(select|with)\b", sql[i + 1:], re.IGNORECASE) is not None
            stack.append(is_sub)
            if is_sub:
                depth += 1
                max_depth = max(max_depth, depth)
        elif ch == ")":
            if stack and stack.pop():
                depth -= 1
    return max_depth


def fix_group_by(sql):
    """If SELECT has plain columns not in GROUP BY, add them.
    Fixes a common small-model mistake without needing another AI call."""
    match = re.search(r"^\s*SELECT\s+(.*?)\s+FROM\s", sql, re.IGNORECASE | re.DOTALL)
    group_match = re.search(r"\bGROUP BY\b\s+(.*?)(\bORDER BY\b|\bLIMIT\b|$)",
                             sql, re.IGNORECASE | re.DOTALL)
    if not match or not group_match:
        return sql  # no GROUP BY at all, nothing to fix

    select_clause = match.group(1)
    group_cols = [c.strip() for c in group_match.group(1).split(",") if c.strip()]

    # Split top-level SELECT columns (ignore commas inside function calls)
    cols, depth, current = [], 0, ""
    for ch in select_clause:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            cols.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        cols.append(current.strip())

    missing = []
    for col in cols:
        plain = re.split(r"\s+AS\s+", col, flags=re.IGNORECASE)[0].strip()
        if re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", plain, re.IGNORECASE):
            continue  # aggregate, doesn't need to be in GROUP BY
        if plain not in group_cols:
            missing.append(plain)

    if not missing:
        return sql

    new_group = group_match.group(1).strip().rstrip(",") + ", " + ", ".join(missing)
    return sql[:group_match.start(1)] + new_group + " " + sql[group_match.end(1):]


def check_sql(sql):
    """Inspect a query. Returns {"allowed": bool, "sql": final_sql, "reasons": [...]}."""
    reasons = []
    cleaned = sql.strip().rstrip(";").strip()
    stripped = strip_strings(cleaned)

    if not cleaned:
        return {"allowed": False, "sql": sql, "reasons": ["Empty query"]}

    if "--" in stripped or "/*" in stripped:
        reasons.append("SQL comments are not allowed")

    if ";" in stripped:
        reasons.append("Multiple statements are not allowed")

    first_word = stripped.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        reasons.append(f"Only SELECT queries are allowed (got {first_word})")

    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", stripped, re.IGNORECASE):
            reasons.append(f"Blocked keyword: {kw}")

    match = BLOCKED_FUNCTION_PATTERN.search(stripped)
    if match:
        reasons.append(f"Blocked function: {match.group(1)}")

    if re.search(r"\b(from|join)\s+''", stripped, re.IGNORECASE):
        reasons.append("Reading files directly in FROM is not allowed")
    if re.search(r'\b(from|join)\s+"[^"]*[./\\][^"]*"', stripped, re.IGNORECASE):
        reasons.append("Reading files directly in FROM is not allowed")

    if subquery_depth(stripped) > MAX_SUBQUERY_DEPTH:
        reasons.append(f"Subqueries nested deeper than {MAX_SUBQUERY_DEPTH} levels")

    if reasons:
        return {"allowed": False, "sql": sql, "reasons": reasons}

    # Fix a common small-model mistake before enforcing the row limit
    final_sql = fix_group_by(cleaned)

    # Enforce the row limit
    limit_match = re.search(r"\blimit\s+(\d+)\s*$", strip_strings(final_sql), re.IGNORECASE)
    if limit_match:
        if int(limit_match.group(1)) > MAX_ROWS:
            final_sql = re.sub(r"(?i)\blimit\s+\d+\s*$", f"LIMIT {MAX_ROWS}", final_sql)
    elif not re.search(r"\blimit\b", strip_strings(final_sql), re.IGNORECASE):
        final_sql = f"{final_sql} LIMIT {MAX_ROWS}"

    return {"allowed": True, "sql": final_sql, "reasons": []}


def log_blocked(question, sql, reasons):
    """Save every blocked query to a log file (an audit trail)."""
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "sql": sql,
        "reasons": reasons,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")