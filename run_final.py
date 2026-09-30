import json
from collections import defaultdict

import duckdb

import text2sql
from evaluate import eval_question, pct
from final_set import FINAL
from text2sql import DB_PATH, get_schema

if __name__ == "__main__":
    version = text2sql.PROMPT_VERSION
    con = duckdb.connect(DB_PATH, read_only=True)
    schema = get_schema(con)

    print(f"FINAL SET | prompt {version} | model {text2sql.MODEL} | {len(FINAL)} questions\n")
    results = []
    for i, (cat, q, gold) in enumerate(FINAL, 1):
        r = eval_question(con, schema, cat, q, gold)
        results.append(r)
        mark = "OK  " if r["status"] in ("correct", "correct_refusal") else "FAIL"
        print(f"[{i:2}/{len(FINAL)}] {mark} {r['status']:<20} {r['seconds']:>5}s  {q}")

    answerable = [r for r in results if r["category"] != "unanswerable"]
    unans = [r for r in results if r["category"] == "unanswerable"]
    correct = sum(r["status"] == "correct" for r in answerable)
    refused = sum(r["status"] == "correct_refusal" for r in unans)

    print("\n" + "=" * 60)
    print(f"FINAL RESULTS | prompt {version}")
    print("=" * 60)
    print(f"Execution accuracy: {correct}/{len(answerable)} = {pct(correct, len(answerable))}")
    by_cat = defaultdict(lambda: [0, 0])
    for r in answerable:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += r["status"] == "correct"
    for cat, (c, t) in by_cat.items():
        print(f"   {cat:<12} {c}/{t} = {pct(c, t)}")
    print(f"Correct refusals: {refused}/{len(unans)} = {pct(refused, len(unans))}")

    fails = [r for r in results if r["status"] not in ("correct", "correct_refusal")]
    if fails:
        print("\nFailures:")
        for r in fails:
            print(f"- [{r['status']}] {r['question']}\n    {r['generated_sql']}")

    out = f"results_final_{version}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"version": version, "results": results}, f, indent=2)
    print(f"\nSaved to {out}")