# NL2BI — Natural Language to Business Intelligence

**Ask questions in plain English. Get tables, charts, and answers — directly from your database.**

[![PyPI version](https://badge.fury.io/py/nl2bi.svg)](https://pypi.org/project/nl2bi)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org)

---

## What it does

NL2BI is an agentic analytics framework that translates natural language questions into validated SQL queries, executes them, and returns structured results with chart recommendations — no dashboards, no SQL knowledge required.

```
"Show me the top 5 suppliers by contract value this quarter"
        ↓
  QueryRouter classifies intent → TopN handler
        ↓
  Schema extracted → SQL planned → validated → executed
        ↓
  Table + bar chart recommendation + NL summary
```

---

## Architecture

Built on a **multi-agent LangGraph pipeline** where each stage is a specialised agent:

| Stage | Agent | What it does |
|---|---|---|
| 1 | Schema Extractor | Reads DB schema and builds context |
| 2 | Intent Classifier | Routes to one of 10 question types |
| 3 | SQL Planner | Generates SQL from intent + schema |
| 4 | Validator | Checks SQL correctness, enforces read-only |
| 5 | Executor | Runs query, returns structured results |
| 6 | Self-Correction | Detects failures, reformulates and retries |
| 7 | Chart Reasoner | Recommends visualisation type |

**10 question types:** Filter, KPI, Grouping, TopN, Comparison, CrossEntity, RiskAlert, Financial, Drilldown, Recommendation

**Memory:** Short-term context window for multi-turn conversations ("now show those by region"), long-term vector memory (ChromaDB) for schema and query history.

**Guardrails:** Read-only execution enforcement, structured output validation, approval gates for destructive queries.

**Observability:** Evaluation pipelines tracking SQL correctness, hallucination rates, and end-to-end latency.

---

## Install

```bash
pip install nl2bi
```

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

print(result.table)        # structured data
print(result.sql)          # generated SQL
print(result.summary)      # NL explanation
print(result.chart_type)   # recommended visualisation
```

**Multi-turn conversation:**
```python
result1 = agent.query("Show me contracts expiring this quarter")
result2 = agent.query("Now filter those above $50K")   # uses session memory
result3 = agent.query("Which supplier has the most?")  # cross-entity reasoning
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
- Anthropic (Claude)
- Local models via Ollama

---

## Why not just use text-to-SQL?

Plain text-to-SQL breaks on ambiguous queries, complex joins, and multi-step questions. NL2BI adds:

- **Intent classification** before SQL generation — different question types need different query patterns
- **Self-correction loops** — if the SQL fails, the agent diagnoses why and retries
- **Session memory** — follow-up questions work naturally
- **Guardrails** — no accidental writes or deletes

---

## License

MIT

---

*Built by [Mithran Bala](https://linkedin.com/in/mithran-bala123)*
