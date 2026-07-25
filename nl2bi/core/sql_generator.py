"""
SQL generation from natural language queries using LLMs.
"""

from typing import Optional, Tuple
import json
import os
from openai import OpenAI
from nl2bi.core import SchemaExtractor


class SQLGenerator:
    """Convert natural language queries to SQL."""

    def __init__(
        self,
        schema_extractor: SchemaExtractor,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize SQL generator.

        Args:
            schema_extractor: SchemaExtractor instance with database schema
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: LLM model to use
        """
        self.schema_extractor = schema_extractor
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)

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

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        payload = json.loads(response.choices[0].message.content)
        return payload.get("sql", ""), payload.get("explanation", "")
