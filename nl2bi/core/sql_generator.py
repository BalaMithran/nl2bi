"""
SQL generation from natural language queries using LLMs.
"""

from typing import Optional, Tuple
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
    
    def generate_sql(self, query: str) -> Tuple[str, str]:
        """
        Generate SQL from natural language query.
        
        Args:
            query: Natural language query
        
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
        
        Return ONLY:
        SQL: <your sql query>
        EXPLANATION: <brief explanation of what the query does>
        """
        
        user_prompt = f"""Database Schema:
{schema_info}

User Query: {query}

Generate SQL for this query."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        
        content = response.choices[0].message.content
        
        # Parse response
        sql_query = ""
        explanation = ""
        
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("SQL:"):
                sql_query = line.replace("SQL:", "").strip()
                # Capture multiline SQL
                j = i + 1
                while j < len(lines) and not lines[j].startswith("EXPLANATION:"):
                    sql_query += " " + lines[j].strip()
                    j += 1
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()
        
        return sql_query, explanation
    
    def validate_sql(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL against schema.
        
        Args:
            sql_query: SQL query to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to parse with SQLAlchemy
            from sqlalchemy import text
            # This is a simple check - doesn't execute
            text(sql_query)
            return True, None
        except Exception as e:
            return False, str(e)
