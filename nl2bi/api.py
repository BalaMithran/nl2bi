"""
Public-facing NL2BI API - a thin facade over NL2BIOrchestrator.
"""

from typing import Any, Dict, List, NamedTuple, Optional
from dataclasses import dataclass, field
from collections import deque
import logging
import time
import pandas as pd

from nl2bi.orchestrator import NL2BIOrchestrator
from nl2bi.core.vector_store import SimpleVectorStore

_SUPPORTED_PROVIDERS = ("openai", "anthropic", "local")
_HISTORY_SIZE = 5
_logger = logging.getLogger("nl2bi")


class Turn(NamedTuple):
    """One prior question/SQL pair in a conversation."""
    query: str
    sql: str


@dataclass
class QueryMetrics:
    """Observability data for a single query - not a substitute for a real eval harness."""
    question_type: Optional[str]
    sql_retry_count: int
    validation_passed: Optional[bool]
    execution_success: Optional[bool]
    latency_seconds: float
    chart_recommendation_count: int


@dataclass
class QueryResult:
    """Result of an NL2BI query, with attribute access matching the public API."""
    query: str
    table: Optional[pd.DataFrame]
    sql: Optional[str]
    summary: Optional[str]
    chart_type: Optional[str]
    chart_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    metrics: Optional[QueryMetrics] = None

    @classmethod
    def from_orchestrator_result(
        cls, result: Dict[str, Any], latency_seconds: float = 0.0
    ) -> "QueryResult":
        data = result.get("data")
        columns = result.get("columns")
        table = pd.DataFrame.from_records(data, columns=columns) if data is not None else None

        chart_recommendations = result.get("chart_recommendations") or []
        chart_type = chart_recommendations[0]["type"] if chart_recommendations else None

        metrics = QueryMetrics(
            question_type=result.get("question_type"),
            sql_retry_count=result.get("retry_count", 0),
            validation_passed=result.get("validation_passed"),
            execution_success=result.get("execution_success"),
            latency_seconds=latency_seconds,
            chart_recommendation_count=len(chart_recommendations),
        )

        return cls(
            query=result.get("query"),
            table=table,
            sql=result.get("sql"),
            summary=result.get("sql_explanation"),
            chart_type=chart_type,
            chart_recommendations=chart_recommendations,
            error=result.get("error"),
            metrics=metrics,
        )


class NL2BI:
    """Ask questions in plain English, get tables, charts, and answers back."""

    def __init__(
        self,
        db_url: str,
        llm: str = "openai",
        api_key: Optional[str] = None,
        memory: bool = False,
        memory_path: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize NL2BI.

        Args:
            db_url: SQLAlchemy connection string for the target database
            llm: LLM provider to use ("openai", "anthropic", or "local")
            api_key: API key for the chosen provider
            memory: Whether to recall similar past queries across turns (costs
                one extra embedding call per query - opt-in)
            memory_path: JSON file to persist long-term memory to, if memory=True
            **kwargs: Passed through to NL2BIOrchestrator (e.g. max_sql_retries)
        """
        if llm not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported llm provider: {llm!r}. Choose from {_SUPPORTED_PROVIDERS}")

        self.llm = llm
        self._orchestrator = NL2BIOrchestrator(
            connection_string=db_url,
            openai_api_key=api_key,
            provider=llm,
            **kwargs,
        )

        self._history: "deque[Turn]" = deque(maxlen=_HISTORY_SIZE)
        self._memory_path = memory_path
        self._vector_store: Optional[SimpleVectorStore] = None
        if memory:
            self._vector_store = SimpleVectorStore(api_key=api_key)
            if memory_path:
                self._vector_store.load(memory_path)

    def query(
        self,
        natural_language_query: str,
        execute: bool = True,
        recommend_charts: bool = True,
    ) -> QueryResult:
        """
        Ask a natural language question.

        Args:
            natural_language_query: Question in plain English
            execute: Whether to execute the generated SQL
            recommend_charts: Whether to recommend visualizations

        Returns:
            QueryResult with attribute access (.table, .sql, .summary, .chart_type)
        """
        history_context = self._build_history_context(natural_language_query)

        start = time.perf_counter()
        result = self._orchestrator.query(
            natural_language_query,
            execute=execute,
            recommend_charts=recommend_charts,
            history_context=history_context,
        )
        latency_seconds = time.perf_counter() - start

        query_result = QueryResult.from_orchestrator_result(result, latency_seconds=latency_seconds)
        self._log_metrics(query_result)

        if query_result.sql:
            self._remember(natural_language_query, query_result.sql)

        return query_result

    def _log_metrics(self, query_result: QueryResult) -> None:
        """
        Emit a structured log line for this query.

        This is the honest minimum for "observability" - retry counts,
        pass/fail flags, and latency. It is not a golden-dataset eval
        harness (no ground truth exists yet to score SQL correctness or
        hallucination rate against) - that's future work once real usage
        produces a seed set of (question, expected_result) pairs.
        """
        m = query_result.metrics
        _logger.info(
            "question_type=%s retry_count=%d validation_passed=%s execution_success=%s "
            "latency_seconds=%.3f chart_recommendation_count=%d error=%s",
            m.question_type, m.sql_retry_count, m.validation_passed, m.execution_success,
            m.latency_seconds, m.chart_recommendation_count, query_result.error,
        )

    def _build_history_context(self, query: str) -> Optional[str]:
        """Build a text block summarizing short-term and (if enabled) long-term memory."""
        parts = []

        if self._history:
            parts.append("Recent turns in this conversation:")
            for turn in self._history:
                parts.append(f'  Q: "{turn.query}" -> SQL: {turn.sql}')

        if self._vector_store is not None:
            similar = self._vector_store.search(query, top_k=3)
            if similar:
                parts.append("Similar past queries:")
                for entry in similar:
                    parts.append(f'  Q: "{entry["text"]}" -> SQL: {entry["metadata"].get("sql")}')

        return "\n".join(parts) if parts else None

    def _remember(self, query: str, sql: str) -> None:
        """Record a successful turn in short-term (and, if enabled, long-term) memory."""
        self._history.append(Turn(query, sql))

        if self._vector_store is not None:
            self._vector_store.add(query, {"sql": sql})
            if self._memory_path:
                self._vector_store.save(self._memory_path)
