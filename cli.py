import time

import duckdb

from guardrails import check_sql, log_blocked
from text2sql import DB_PATH, get_schema, question_to_sql, run_query
from validator import sanity_check, score_confidence

if __name__ == "__main__":
    con = duckdb.connect(DB_PATH, read_only=True)  # second safety layer
    schema = get_schema(con)
    deep_mode = False

    print("Ask questions about the store.")
    print("Commands: 'deep on' / 'deep off' (full confidence checks, slower). Empty line quits.")
    print("Mode: FAST (instant sanity checks only)\n")

    while True:
        question = input("Question: ").strip()
        if not question:
            break

        if question.lower() in ("deep on", "deep off"):
            deep_mode = question.lower() == "deep on"
            print(f"Mode: {'DEEP (slower, full confidence report)' if deep_mode else 'FAST'}\n")
            continue

        start = time.time()
        print("  [1/3] Writing SQL...")
        sql = question_to_sql(question, schema)

        if sql == "CANNOT_ANSWER":
            print("\nThis can't be answered with this database.")
            print(f"Done in {time.time() - start:.0f}s. Ready for your next question.\n")
            continue

        print("  [2/3] Checking safety guardrails...")
        verdict = check_sql(sql)
        if not verdict["allowed"]:
            log_blocked(question, sql, verdict["reasons"])
            print(f"\nBLOCKED by guardrails. Generated SQL was:\n{sql}")
            for reason in verdict["reasons"]:
                print(f"  - {reason}")
            print(f"Done in {time.time() - start:.0f}s. Ready for your next question.\n")
            continue

        print("  [3/3] Running query...")
        print(f"\nSQL that will run:\n{verdict['sql']}\n")
        try:
            df = run_query(con, verdict["sql"])
        except Exception as e:
            print(f"Query failed: {e}")
            print(f"Done in {time.time() - start:.0f}s. Ready for your next question.\n")
            continue

        print(df)

        if deep_mode:
            print("\nRunning deep confidence checks (2 more AI calls, about a minute)...")
            report = score_confidence(
                question, verdict["sql"], df, schema,
                lambda s: run_query(con, s), check_sql,
            )
            print(f"\nConfidence: {report['confidence']}/100 ({report['label']})")
            for name, value in report["signals"].items():
                print(f"  {name}: {value:.2f}")
            for note in report["notes"]:
                print(f"  - {note}")
            if report["label"] == "Low":
                print("  WARNING: low confidence. Double-check this answer.")
        else:
            score, warnings = sanity_check(df)
            print(f"\nQuick check: {'OK' if not warnings else 'WARNING'}")
            for w in warnings:
                print(f"  - {w}")

        print(f"\nDone in {time.time() - start:.0f}s. Ready for your next question.\n")