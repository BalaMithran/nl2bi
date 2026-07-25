"""
Unit tests for NL2BI package.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from nl2bi.core import SchemaExtractor, ColumnInfo, TableInfo
from nl2bi.core.sql_generator import SQLGenerator
from nl2bi.core.chart_finder import ChartFinder, ChartType
from nl2bi.core.validator import validate_readonly


class TestSchemaExtractor:
    """Test schema extraction functionality."""

    @patch('nl2bi.core.create_engine')
    def test_initialization(self, mock_engine):
        """Test SchemaExtractor initialization."""
        extractor = SchemaExtractor("sqlite:///test.db")
        assert extractor.engine is not None
        assert extractor.schema == {}
        assert extractor._extracted is False
    
    def test_column_info_creation(self):
        """Test ColumnInfo dataclass."""
        col = ColumnInfo(
            name="id",
            type="INTEGER",
            nullable=False,
            primary_key=True,
        )
        assert col.name == "id"
        assert col.primary_key is True
    
    def test_table_info_creation(self):
        """Test TableInfo dataclass."""
        cols = [
            ColumnInfo("id", "INTEGER", False, True),
            ColumnInfo("name", "VARCHAR", True, False),
        ]
        table = TableInfo("users", cols)
        assert table.name == "users"
        assert len(table.columns) == 2


class TestSQLGenerator:
    """Test SQL generation functionality."""
    
    @patch('nl2bi.core.sql_generator.SchemaExtractor')
    @patch('nl2bi.core.sql_generator.OpenAI')
    def test_initialization(self, mock_openai, mock_schema):
        """Test SQLGenerator initialization."""
        generator = SQLGenerator(mock_schema, api_key="test-key")
        assert generator.schema_extractor == mock_schema
        assert generator.api_key == "test-key"
        assert generator.model == "gpt-4o-mini"
    
    @patch('nl2bi.core.sql_generator.OpenAI')
    def test_generate_sql_parses_json_response(self, mock_openai_cls):
        """generate_sql should parse the JSON-mode response into (sql, explanation)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content='{"sql": "SELECT * FROM users", "explanation": "lists users"}'
            ))]
        )

        generator = SQLGenerator(Mock(), api_key="test")
        generator.schema_extractor.get_schema_string.return_value = "Table: users"

        sql, explanation = generator.generate_sql("show me users")
        assert sql == "SELECT * FROM users"
        assert explanation == "lists users"

    @patch('nl2bi.core.sql_generator.OpenAI')
    def test_generate_sql_includes_previous_error_in_retry_prompt(self, mock_openai_cls):
        """A retry attempt should surface the prior SQL and error to the LLM."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content='{"sql": "SELECT id FROM users", "explanation": "fixed"}'
            ))]
        )

        generator = SQLGenerator(Mock(), api_key="test")
        generator.schema_extractor.get_schema_string.return_value = "Table: users"

        generator.generate_sql(
            "show me users",
            previous_sql="SELECT * FROM userz",
            error='relation "userz" does not exist',
        )

        sent_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        sent_prompt = sent_messages[1]["content"]
        assert "SELECT * FROM userz" in sent_prompt
        assert "does not exist" in sent_prompt


class TestSQLValidator:
    """Test the read-only SQL guardrail."""

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM users",
        "SELECT id, name FROM users WHERE id = 1",
        "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        "SELECT * FROM t WHERE x IN (SELECT id FROM other)",
    ])
    def test_valid_readonly_queries_pass(self, sql):
        is_valid, reason = validate_readonly(sql)
        assert is_valid is True
        assert reason is None

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM users; DROP TABLE users;",
        "INSERT INTO users VALUES (1, 'x')",
        "UPDATE users SET name = 'x'",
        "DELETE FROM users",
        "DROP TABLE users",
        "not valid sql at all ((",
    ])
    def test_destructive_or_invalid_queries_are_rejected(self, sql):
        is_valid, reason = validate_readonly(sql)
        assert is_valid is False
        assert reason is not None

    def test_dml_hidden_in_cte_is_rejected(self):
        """DML inside a CTE (e.g. Postgres's DELETE ... RETURNING) must not slip through."""
        is_valid, reason = validate_readonly(
            "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x"
        )
        assert is_valid is False
        assert reason is not None


class TestOrchestratorGuardrail:
    """Test that the orchestrator enforces the read-only guardrail before executing."""

    @patch('nl2bi.orchestrator.pd')
    @patch('nl2bi.orchestrator.ChartFinder')
    @patch('nl2bi.orchestrator.SQLGenerator')
    @patch('nl2bi.orchestrator.SchemaExtractor')
    @patch('nl2bi.orchestrator.create_engine')
    def test_destructive_sql_never_reaches_execution(
        self, mock_create_engine, mock_schema_cls, mock_sql_gen_cls, mock_chart_cls, mock_pd
    ):
        """A DROP TABLE returned by the LLM should be rejected, never passed to pd.read_sql."""
        from nl2bi.orchestrator import NL2BIOrchestrator

        mock_sql_gen_cls.return_value.generate_sql.return_value = (
            "DROP TABLE users", "deletes the users table"
        )

        orchestrator = NL2BIOrchestrator(
            "sqlite:///test.db", openai_api_key="test", max_sql_retries=0
        )
        result = orchestrator.query("delete all the users")

        mock_pd.read_sql.assert_not_called()
        assert result["error"] is not None
        assert "rejected" in result["error"].lower()


class TestChartFinder:
    """Test chart recommendation functionality."""
    
    @patch('nl2bi.core.chart_finder.OpenAI')
    def test_initialization(self, mock_openai):
        """Test ChartFinder initialization."""
        finder = ChartFinder(api_key="test-key")
        assert finder.api_key == "test-key"
        assert finder.model == "gpt-4o-mini"
    
    def test_chart_type_enum(self):
        """Test ChartType enum."""
        assert ChartType.BAR.value == "bar"
        assert ChartType.LINE.value == "line"
        assert ChartType.PIE.value == "pie"
    
    def test_parse_recommendation(self):
        """Test parsing a single JSON recommendation."""
        finder = ChartFinder(api_key="test")

        rec = finder._parse_recommendation({
            "chart_type": "line",
            "title": "Sales Over Time",
            "x_column": "date",
            "y_column": "revenue",
            "reasoning": "Shows trends over time",
        })
        assert rec.chart_type == ChartType.LINE
        assert rec.title == "Sales Over Time"
        assert rec.x_column == "date"
        assert rec.y_column == "revenue"

    def test_parse_recommendation_unknown_chart_type_falls_back_to_table(self):
        """Test unrecognized chart_type values fall back to TABLE."""
        finder = ChartFinder(api_key="test")

        rec = finder._parse_recommendation({"chart_type": "not-a-real-type", "title": "X"})
        assert rec.chart_type == ChartType.TABLE


class TestChartRecommendation:
    """Test chart recommendation data class."""
    
    def test_recommendation_creation(self):
        """Test creating a chart recommendation."""
        from nl2bi.core.chart_finder import ChartRecommendation
        
        rec = ChartRecommendation(
            chart_type=ChartType.BAR,
            title="Top 10 Products",
            x_column="product",
            y_column="sales",
            reasoning="Comparison across categories",
        )
        
        assert rec.chart_type == ChartType.BAR
        assert rec.title == "Top 10 Products"
        assert rec.x_column == "product"


class TestUtils:
    """Test utility functions."""
    
    def test_format_sql(self):
        """Test SQL formatting."""
        from nl2bi.utils import format_sql
        
        sql = "SELECT * FROM users WHERE id = 1"
        formatted = format_sql(sql)
        assert "FROM" in formatted
        assert "WHERE" in formatted
    
    def test_validate_columns(self):
        """Test column validation."""
        from nl2bi.utils import validate_columns
        
        provided = ["id", "name", "email"]
        required = ["id", "name"]
        assert validate_columns(provided, required) is True
        
        required = ["id", "phone"]
        assert validate_columns(provided, required) is False
    
    def test_truncate_text(self):
        """Test text truncation."""
        from nl2bi.utils import truncate_text
        
        text = "This is a long text that should be truncated"
        truncated = truncate_text(text, max_length=20)
        assert len(truncated) == 20
        assert truncated.endswith("...")
        
        short_text = "Short"
        assert truncate_text(short_text) == short_text


# Integration tests would go here
class TestIntegration:
    """Integration tests (requires test database)."""
    
    @pytest.mark.skip(reason="Requires test database setup")
    def test_end_to_end_workflow(self):
        """Test complete NL2BI workflow."""
        # This would require setting up a test database
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
