"""
SQL generation from natural language queries using LLMs.
"""

from typing import Optional, Tuple
import os
from nl2bi.core import SchemaExtractor
from nl2bi.core import llm_client


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
    ) -> Tuple[str, str]:
        """
        Generate SQL from a natural language query.

        Args:
            query: Natural language query
            previous_sql: A prior SQL attempt that failed to execute, if any
            error: The execution error raised by `previous_sql`, if any

        Returns:
            Tuple of (sql_query, explanation)
        """
        schema_info = self.schema_extractor.get_schema_string()

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
