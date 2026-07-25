"""
Main orchestrator that coordinates SQL generation, execution, and visualization.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from sqlalchemy import text, create_engine

from nl2bi.core import SchemaExtractor
from nl2bi.core.sql_generator import SQLGenerator
from nl2bi.core.chart_finder import ChartFinder, ChartRecommendation


class NL2BIOrchestrator:
    """Main orchestrator for NL to BI conversion."""
    
    def __init__(self, connection_string: str, openai_api_key: Optional[str] = None):
        """
        Initialize orchestrator.
        
        Args:
            connection_string: SQLAlchemy connection string
            openai_api_key: OpenAI API key
        """
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        
        # Initialize components
        self.schema_extractor = SchemaExtractor(connection_string)
        self.schema_extractor.extract_schema()
        
        self.sql_generator = SQLGenerator(
            self.schema_extractor,
            api_key=openai_api_key,
        )
        
        self.chart_finder = ChartFinder(api_key=openai_api_key)
    
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
        
        # Generate SQL
        try:
            sql, explanation = self.sql_generator.generate_sql(
                natural_language_query
            )
            result["sql"] = sql
            result["sql_explanation"] = explanation
        except Exception as e:
            result["error"] = f"SQL generation failed: {str(e)}"
            return result
        
        # Validate SQL
        is_valid, error = self.sql_generator.validate_sql(sql)
        if not is_valid:
            result["error"] = f"SQL validation failed: {error}"
            return result
        
        # Execute query if requested
        if execute:
            try:
                df = pd.read_sql(sql, self.engine)
                result["data"] = df.to_dict(orient="records")
                result["columns"] = df.columns.tolist()
            except Exception as e:
                result["error"] = f"Query execution failed: {str(e)}"
                return result
        
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
