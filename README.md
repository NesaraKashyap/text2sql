\# Text-to-SQL Assistant with Safety Guardrails and Hallucination Detection



A natural language interface to a SQL database that translates plain English questions

into SQL, blocks dangerous queries before they run, and flags answers that look wrong —

all running entirely on a local, open-source LLM with zero API costs.



\## Why this exists



Text-to-SQL is one of the most requested AI engineering skills, but most demos are

unsafe toys: they let an LLM run arbitrary SQL against a real database with no

guardrails, and they never check whether the generated query actually answers the

question that was asked. This project treats both of those as first-class problems.



\## What it does



1\. \*\*Translates\*\* a plain English question into SQL using a locally-hosted LLM

&#x20;  (Qwen2.5-Coder 7B via Ollama — no API keys, no cloud costs).

2\. \*\*Validates\*\* every generated query against a safety layer before execution:

&#x20;  blocks writes/DDL, SQL injection patterns, file-read functions, and overly

&#x20;  deep subqueries; enforces a row limit. Backed by a read-only database

&#x20;  connection as a second line of defense.

3\. \*\*Checks\*\* the result for signs of a wrong answer: empty results, NULL-heavy

&#x20;  columns, implausible values, and (in deep mode) LLM-based back-translation and

&#x20;  an independently-generated second query, combined into a 0-100 confidence score.

4\. \*\*Refuses\*\* to answer questions the schema can't support, rather than

&#x20;  guessing or inventing columns.

5\. \*\*Serves\*\* through both a CLI and a Streamlit web app.



\## Results



Measured on a held-out 24-question test set that was never used to develop the

prompt (18 answerable questions across simple/aggregation/join/date queries,

6 deliberately unanswerable questions):



| Metric | Result |

|---|---|

| Execution accuracy | \*\*94%\*\* (17/18) |

| Correct refusal on unanswerable questions | \*\*100%\*\* (6/6) |

| Malicious prompts neutralized | \*\*100%\*\* (10/10 attack scenarios) |

| Unsafe queries that reached the database | \*\*0\*\* |



\### Prompt engineering methodology



I tested four prompt strategies, each validated against the same held-out set to

avoid overfitting to any one round of failures:



| Version | Approach | Accuracy | Refusals |

|---|---|---|---|

| v1 | Baseline rules + few examples | 83% | 83% |

| v2 | Added "never invent columns" + stricter status-filter rule | 83% | 100% |

| v3 | Stricter always-filter-by-status rule | 78% | 83% |

| \*\*v4\*\* | \*\*Rule refinement + 9 worked few-shot examples\*\* | \*\*94%\*\* | \*\*100%\*\* |



Key finding: for a 7B model, showing worked examples of tricky patterns

(multi-table joins, average-per-order calculations, correct refusals) outperformed

adding more explicit negative rules. v3's stricter rule actually reduced accuracy by

causing the model to over-apply a status filter to unrelated queries — a reminder

that prompt changes need regression testing, the same as code changes.



\### Model size vs. accuracy trade-off



I also benchmarked a smaller model (Llama 3.2 3B, \~40% the parameter count) to see

if it was a viable faster alternative for CPU-only inference:



| Model | Size | Accuracy | Refusal accuracy |

|---|---|---|---|

| Qwen2.5-Coder 7B (default) | 4.7 GB | 94% | 100% |

| Llama 3.2 3B | 2.0 GB | 83% | \*\*0%\*\* |



The smaller model hallucinated a confident, incorrect answer for every single

unanswerable question (inventing columns like `warehouse` and `discount\_amount`

that don't exist in the schema), with no reliable speed advantage. For a tool whose

core value proposition is not making things up, this made it an easy call to keep

the larger model as the default despite slower CPU inference.



\## Safety guardrails



Every generated query passes through a rule-based checker before execution:



\- Only `SELECT`/`WITH` statements allowed — blocks `DROP`, `DELETE`, `INSERT`,

&#x20; `UPDATE`, `CREATE`, `ALTER`, and other write/DDL operations

\- Blocks file-reading functions (`read\_csv`, `glob`, etc.) that could expose the

&#x20; filesystem

\- Blocks SQL comments (a common injection/obfuscation technique) and

&#x20; multi-statement queries

\- Enforces a maximum subquery nesting depth

\- Auto-adds/enforces a row limit

\- Every blocked query is logged with a timestamp and reason (audit trail)

\- Backed by a \*\*read-only database connection\*\* as a second, independent layer —

&#x20; even if the query checker missed something, the database itself refuses writes



Tested against 10 adversarial prompts (prompt injection, direct destructive

requests, file access attempts): 10/10 neutralized, 0 unsafe queries executed.



\## Architecture

