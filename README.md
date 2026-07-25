# NL2BI — Natural Language to Business Intelligence

**Ask questions in plain English. Get tables, charts, and answers — directly from your database.**

[![PyPI version](https://badge.fury.io/py/nl2bi.svg)](https://pypi.org/project/nl2bi)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org)

---

## What it does

NL2BI translates natural language questions into validated, read-only SQL queries, executes them, and returns structured results with chart recommendations — no dashboards, no SQL knowledge required.

```
"Show me the top 5 suppliers by contract value this quarter"
        ↓
  Intent classified (TopN) → hint steers SQL generation
        ↓
  Relevant schema retrieved → SQL planned → validated (read-only) → executed
        ↓
  Table + bar chart recommendation + NL summary
```

---

## Architecture

A sequential multi-stage pipeline, plain Python (no agent framework):

| Stage | Component | What it does |
|---|---|---|
| 1 | Schema Extractor | Introspects the DB once at startup; retrieves just the relevant tables per query (lexical + business-term scoring) |
| 2 | Intent Classifier | Classifies into one of 10 question types, which nudges SQL generation with a type-specific hint |
| 3 | SQL Planner | Generates SQL from the query + retrieved schema + intent hint |
| 4 | Validator | Rejects anything that isn't a single read-only `SELECT`/`WITH` statement (AST-checked via `sqlglot` — catches statement-stacking and DML hidden in CTEs) |
| 5 | Executor | Runs the validated query, returns structured results |
| 6 | Self-Correction | On a validation or execution failure, feeds the error back to the SQL Planner and retries (bounded by `max_sql_retries`, default 2) |
| 7 | Chart Reasoner | Recommends a visualization type for the result columns |

**10 question types:** Filter, KPI, Grouping, TopN, Comparison, CrossEntity, RiskAlert, Financial, Drilldown, Recommendation

**Semantic layer:** Map business vocabulary to schema elements the LLM would never guess from column names alone — see [Business terms](#business-terms) below.

**Memory:** Short-term — the last 5 turns of a conversation are always included as context. Long-term — optional (`memory=True`), stores past queries in a lightweight JSON-persisted embedding store and recalls similar ones on future queries.

**Guardrails:** Read-only execution enforcement (Stage 4) and structured JSON output from the LLM at every stage.

**Observability:** Every query returns `result.metrics` (question type, retry count, validation/execution pass-fail, latency) and emits one structured log line via `logging.getLogger("nl2bi")`. This is retry/latency tracking, not a golden-dataset eval harness — there's no SQL-correctness or hallucination-rate scoring yet, since that needs ground truth this project doesn't have.

---

## Install

```bash
pip install nl2bi
```

For Anthropic support: `pip install nl2bi[llm]`. OpenAI and local (Ollama) providers need no extra install.

---

## Quick Start

```python
from nl2bi import NL2BI

# Connect to your database
agent = NL2BI(
    db_url="postgresql://user:password@localhost/mydb",
    llm="openai",  # or "anthropic", "local"
    api_key="your-api-key"
)

# Ask a question
result = agent.query("What are the top 10 customers by revenue last month?")

print(result.table)        # structured data (pandas DataFrame)
print(result.sql)          # generated SQL
print(result.summary)      # NL explanation
print(result.chart_type)   # recommended visualisation
print(result.metrics)      # question_type, retry_count, latency_seconds, ...
```

**Multi-turn conversation** (short-term memory is always on):
```python
result1 = agent.query("Show me contracts expiring this quarter")
result2 = agent.query("Now filter those above $50K")  # prior turn is in context
```

**Long-term memory** (opt-in — costs one extra embedding call per query):
```python
agent = NL2BI(db_url="...", memory=True, memory_path="memory.json")
```

**Local models via Ollama** (`llm="local"` expects Ollama running at `http://localhost:11434` with the model already pulled):
```python
agent = NL2BI(db_url="...", llm="local")
```

---

## Business terms

Map domain vocabulary to schema elements before querying, so "churn" resolves to the right table even if no column is named that:

```python
result = agent.query("...")  # after connecting

# Access the underlying schema extractor for glossary/description setup:
extractor = agent._orchestrator.schema_extractor
extractor.add_business_term("churn", "subscriptions.cancelled_at", "customers who stopped paying")
extractor.add_table_description("subscriptions", "Active and cancelled customer subscriptions")
```

---

## Supported Databases

Any database supported by SQLAlchemy:
- PostgreSQL
- MySQL
- SQLite
- MS SQL Server
- Oracle

---

## Supported LLMs

- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude) — requires `pip install nl2bi[llm]`
- Local models via Ollama (uses Ollama's OpenAI-compatible endpoint, no extra dependency)

---

## Why not just use text-to-SQL?

Plain text-to-SQL breaks on ambiguous queries, complex joins, and multi-step questions. NL2BI adds:

- **Intent classification** before SQL generation — different question types get a tailored prompt hint
- **Self-correction loops** — if the SQL fails validation or execution, the agent sees why and retries
- **Session memory** — follow-up questions work naturally
- **Guardrails** — a rejected write/delete never reaches your database

---

## License

MIT

---

*Built by [Mithran Bala](https://linkedin.com/in/mithran-bala123)*
