"""
Unit tests for NL2BI package.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from nl2bi.core.schema import SchemaExtractor, ColumnInfo, TableInfo
from nl2bi.core.sql_generator import SQLGenerator
from nl2bi.core.chart_finder import ChartFinder, ChartType


class TestSchemaExtractor:
    """Test schema extraction functionality."""
    
    @patch('nl2bi.core.schema.create_engine')
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
    
    @patch('nl2bi.core.sql_generator.text')
    def test_validate_sql_valid(self, mock_text):
        """Test validation of valid SQL."""
        generator = SQLGenerator(Mock(), api_key="test")
        is_valid, error = generator.validate_sql("SELECT * FROM users")
        assert is_valid is True
        assert error is None
    
    @patch('nl2bi.core.sql_generator.text')
    def test_validate_sql_invalid(self, mock_text):
        """Test validation of invalid SQL."""
        mock_text.side_effect = Exception("Syntax error")
        generator = SQLGenerator(Mock(), api_key="test")
        is_valid, error = generator.validate_sql("INVALID SQL HERE")
        assert is_valid is False
        assert error is not None


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
    
    def test_parse_recommendation_block(self):
        """Test parsing recommendation block."""
        finder = ChartFinder(api_key="test")
        
        block = """CHART_TYPE: line
TITLE: Sales Over Time
X_COLUMN: date
Y_COLUMN: revenue
REASONING: Shows trends over time"""
        
        rec = finder._parse_recommendation_block(block, ["date", "revenue"])
        assert rec.chart_type == ChartType.LINE
        assert rec.title == "Sales Over Time"
        assert rec.x_column == "date"
        assert rec.y_column == "revenue"


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
