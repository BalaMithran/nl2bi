"""
SQL generation from natural language queries using LLMs.
"""

from typing import Optional, Tuple
import os
from nl2bi.core import SchemaExtractor
from nl2bi.core import llm_client
from nl2bi.core.intent_classifier import QuestionType

_QUESTION_TYPE_HINTS = {
    QuestionType.FILTER: "This is a filter question - likely needs a WHERE clause.",
    QuestionType.KPI: "This is a KPI question - likely needs an aggregate (COUNT/SUM/AVG).",
    QuestionType.GROUPING: "This is a grouping question - likely needs GROUP BY.",
    QuestionType.TOPN: "This is a top-N question - likely needs ORDER BY ... LIMIT N.",
    QuestionType.COMPARISON: "This is a comparison question - likely needs multiple aggregates or a self-join.",
    QuestionType.CROSS_ENTITY: "This spans multiple entities - likely needs a JOIN across tables.",
    QuestionType.RISK_ALERT: "This is a risk/alert question - likely needs a threshold-based WHERE clause.",
    QuestionType.FINANCIAL: "This is a financial question - be precise with monetary aggregation and rounding.",
    QuestionType.DRILLDOWN: "This is a drilldown question - likely needs a more granular GROUP BY than a prior query.",
    QuestionType.RECOMMENDATION: "This is a recommendation question - likely needs ranking by a derived score.",
}


class SQLGenerator:
    """Convert natural language queries to SQL."""

    def __init__(
        self,
        schema_extractor: SchemaExtractor,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "openai",
    ):
        """
        Initialize SQL generator.

        Args:
            schema_extractor: SchemaExtractor instance with database schema
            api_key: API key for the chosen provider (defaults to OPENAI_API_KEY env var)
            model: LLM model to use (defaults to a sensible model for the provider)
            provider: LLM provider - "openai", "anthropic", or "local" (Ollama)
        """
        self.schema_extractor = schema_extractor
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.provider = provider
        self.model = model or llm_client.default_model_for(provider)

    def generate_sql(
        self,
        query: str,
        previous_sql: Optional[str] = None,
        error: Optional[str] = None,
        question_type: Optional[QuestionType] = None,
        history_context: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generate SQL from a natural language query.

        Args:
            query: Natural language query
            previous_sql: A prior SQL attempt that failed to execute, if any
            error: The execution error raised by `previous_sql`, if any
            question_type: Classified question type, used to nudge the prompt
            history_context: Prior turns / similar past queries, for multi-turn conversations

        Returns:
            Tuple of (sql_query, explanation)
        """
        schema_info = self.schema_extractor.get_relevant_schema_string(query)

        system_prompt = """You are an expert SQL developer. Convert natural language queries to SQL.

Rules:
1. Use the provided schema to write accurate SQL
2. Only use tables and columns that exist in the schema
3. Write clean, optimized SQL
4. Assume the database is PostgreSQL unless stated otherwise
5. Include table aliases for readability

Respond with ONLY a JSON object of the form:
{"sql": "<the SQL query>", "explanation": "<brief explanation of what the query does>"}
"""

        user_prompt = f"""Database Schema:
{schema_info}

User Query: {query}

Generate SQL for this query."""

        if question_type is not None:
            user_prompt += f"\n\n{_QUESTION_TYPE_HINTS[question_type]}"

        if history_context:
            user_prompt += f"\n\nConversation context:\n{history_context}"

        if previous_sql and error:
            user_prompt += f"""

A previous attempt failed to execute:
SQL: {previous_sql}
Error: {error}

Fix the query so it executes successfully against the schema above."""

        payload = llm_client.get_json_completion(
            self.provider, self.api_key, self.model, system_prompt, user_prompt
        )
        return payload.get("sql", ""), payload.get("explanation", "")
