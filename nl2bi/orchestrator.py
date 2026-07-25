"""
Main orchestrator that coordinates SQL generation, execution, and visualization.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from sqlalchemy import create_engine

from nl2bi.core import SchemaExtractor
from nl2bi.core.sql_generator import SQLGenerator
from nl2bi.core.chart_finder import ChartFinder, ChartRecommendation
from nl2bi.core.validator import validate_readonly


class NL2BIOrchestrator:
    """Main orchestrator for NL to BI conversion."""

    def __init__(
        self,
        connection_string: str,
        openai_api_key: Optional[str] = None,
        max_sql_retries: int = 2,
        provider: str = "openai",
    ):
        """
        Initialize orchestrator.

        Args:
            connection_string: SQLAlchemy connection string
            openai_api_key: API key for the chosen provider
            max_sql_retries: Number of times to ask the LLM to fix SQL that
                fails to execute, feeding back the execution error each time
            provider: LLM provider - "openai", "anthropic", or "local" (Ollama)
        """
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        self.max_sql_retries = max_sql_retries

        # Initialize components
        self.schema_extractor = SchemaExtractor(connection_string)
        self.schema_extractor.extract_schema()

        self.sql_generator = SQLGenerator(
            self.schema_extractor,
            api_key=openai_api_key,
            provider=provider,
        )

        self.chart_finder = ChartFinder(api_key=openai_api_key, provider=provider)
    
    def query(
        self,
        natural_language_query: str,
        execute: bool = True,
        recommend_charts: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a natural language query end-to-end.
        
        Args:
            natural_language_query: Natural language query
            execute: Whether to execute the SQL query
            recommend_charts: Whether to recommend visualizations
        
        Returns:
            Dictionary with results, SQL, recommendations, and data
        """
        result = {
            "query": natural_language_query,
            "sql": None,
            "sql_explanation": None,
            "data": None,
            "columns": None,
            "chart_recommendations": [],
            "error": None,
        }

        # Generate SQL, retrying with execution feedback if it fails to run
        sql, explanation = None, None
        previous_sql, previous_error = None, None

        for attempt in range(self.max_sql_retries + 1):
            try:
                sql, explanation = self.sql_generator.generate_sql(
                    natural_language_query,
                    previous_sql=previous_sql,
                    error=previous_error,
                )
            except Exception as e:
                result["error"] = f"SQL generation failed: {str(e)}"
                return result

            is_readonly, reason = validate_readonly(sql)
            if not is_readonly:
                previous_sql, previous_error = sql, (
                    f"SQL rejected: {reason}. Only a single read-only SELECT/WITH "
                    "query is permitted."
                )
                if attempt == self.max_sql_retries:
                    result["error"] = f"SQL rejected after {attempt + 1} attempt(s): {reason}"
                    return result
                continue

            if not execute:
                break

            try:
                df = pd.read_sql(sql, self.engine)
                break
            except Exception as e:
                previous_sql, previous_error = sql, str(e)
                if attempt == self.max_sql_retries:
                    result["error"] = (
                        f"Query execution failed after {attempt + 1} attempt(s): {str(e)}"
                    )
                    return result

        result["sql"] = sql
        result["sql_explanation"] = explanation

        if execute:
            result["data"] = df.to_dict(orient="records")
            result["columns"] = df.columns.tolist()

        # Recommend charts if we have data
        if recommend_charts and result["data"] and result["columns"]:
            try:
                recommendations = self.chart_finder.recommend_charts(
                    natural_language_query,
                    result["columns"],
                )
                result["chart_recommendations"] = [
                    {
                        "type": rec.chart_type.value,
                        "title": rec.title,
                        "x_column": rec.x_column,
                        "y_column": rec.y_column,
                        "group_by": rec.group_by,
                        "reasoning": rec.reasoning,
                    }
                    for rec in recommendations
                ]
            except Exception as e:
                # Non-fatal error - continue even if charts fail
                pass
        
        return result
    
    def generate_sql(self, natural_language_query: str) -> Tuple[str, str]:
        """
        Generate SQL without executing.
        
        Args:
            natural_language_query: Natural language query
        
        Returns:
            Tuple of (sql, explanation)
        """
        return self.sql_generator.generate_sql(natural_language_query)
    
    def find_relevant_charts(
        self,
        query: str,
        columns: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Find relevant charts for a query.
        
        Args:
            query: Natural language query
            columns: Available columns
        
        Returns:
            List of chart recommendations
        """
        recommendations = self.chart_finder.recommend_charts(query, columns)
        return [
            {
                "type": rec.chart_type.value,
                "title": rec.title,
                "x_column": rec.x_column,
                "y_column": rec.y_column,
                "group_by": rec.group_by,
                "reasoning": rec.reasoning,
            }
            for rec in recommendations
        ]
    
    def extract_schema(self) -> Dict[str, Any]:
        """
        Extract and return database schema.
        
        Returns:
            Schema dictionary
        """
        schema = self.schema_extractor.extract_schema()
        return {
            table_name: {
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "nullable": col.nullable,
                        "primary_key": col.primary_key,
                        "foreign_key": col.foreign_key,
                    }
                    for col in table_info.columns
                ],
                "description": table_info.description,
            }
            for table_name, table_info in schema.items()
        }
    
    def add_table_description(self, table_name: str, description: str) -> None:
        """Add description to a table."""
        self.schema_extractor.add_table_description(table_name, description)
    
    def add_column_description(
        self, table_name: str, column_name: str, description: str
    ) -> None:
        """Add description to a column."""
        self.schema_extractor.add_column_description(table_name, column_name, description)
