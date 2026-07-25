"""
Public-facing NL2BI API - a thin facade over NL2BIOrchestrator.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import pandas as pd

from nl2bi.orchestrator import NL2BIOrchestrator

_SUPPORTED_PROVIDERS = ("openai", "anthropic", "local")


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

    @classmethod
    def from_orchestrator_result(cls, result: Dict[str, Any]) -> "QueryResult":
        data = result.get("data")
        columns = result.get("columns")
        table = pd.DataFrame.from_records(data, columns=columns) if data is not None else None

        chart_recommendations = result.get("chart_recommendations") or []
        chart_type = chart_recommendations[0]["type"] if chart_recommendations else None

        return cls(
            query=result.get("query"),
            table=table,
            sql=result.get("sql"),
            summary=result.get("sql_explanation"),
            chart_type=chart_type,
            chart_recommendations=chart_recommendations,
            error=result.get("error"),
        )


class NL2BI:
    """Ask questions in plain English, get tables, charts, and answers back."""

    def __init__(
        self,
        db_url: str,
        llm: str = "openai",
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize NL2BI.

        Args:
            db_url: SQLAlchemy connection string for the target database
            llm: LLM provider to use ("openai", "anthropic", or "local")
            api_key: API key for the chosen provider
            **kwargs: Passed through to NL2BIOrchestrator (e.g. max_sql_retries)
        """
        if llm not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported llm provider: {llm!r}. Choose from {_SUPPORTED_PROVIDERS}")
        if llm != "openai":
            raise ValueError(f"llm={llm!r} is not implemented yet - only 'openai' is currently supported")

        self.llm = llm
        self._orchestrator = NL2BIOrchestrator(
            connection_string=db_url,
            openai_api_key=api_key,
            **kwargs,
        )

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
        result = self._orchestrator.query(
            natural_language_query,
            execute=execute,
            recommend_charts=recommend_charts,
        )
        return QueryResult.from_orchestrator_result(result)
