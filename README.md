# NL2BI - Natural Language to Business Intelligence

Convert natural language queries to SQL, business insights, and visualizations. A Python toolkit that bridges the gap between plain English and complex database queries.

## Features

- **Natural Language to SQL**: Convert English queries to optimized SQL automatically
- **Schema Extraction**: Discover and manage database schema information
- **Chart Recommendations**: Get intelligent visualization suggestions for your data
- **Multi-LLM Support**: Works with OpenAI and extensible for other LLM providers
- **Schema Documentation**: Add descriptions to tables and columns for better context

## Installation

### From PyPI (when published)
```bash
pip install nl2bi
```

### Local Development
```bash
# Clone the repository
git clone https://github.com/yourusername/nl2bi.git
cd nl2bi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

```python
from nl2bi import NL2BIOrchestrator

# Initialize with your database
orchestrator = NL2BIOrchestrator(
    connection_string="postgresql://user:password@localhost/mydb"
)

# Ask a question in natural language
result = orchestrator.query("What are the top 10 customers by revenue?")

# Access results
print(result["sql"])  # Generated SQL query
print(result["data"])  # Query results as list of dicts
print(result["chart_recommendations"])  # Suggested visualizations
```

## Core Components

### SchemaExtractor

Extracts and manages database schema information.

```python
from nl2bi.core.schema import SchemaExtractor

extractor = SchemaExtractor("postgresql://user:password@localhost/mydb")
schema = extractor.extract_schema()

# Add descriptions for better context
extractor.add_table_description("users", "Customer data including profiles")
extractor.add_column_description("users", "email", "Customer email address")

# Get human-readable schema string
schema_str = extractor.get_schema_string()
```

### SQLGenerator

Generates SQL from natural language queries using LLMs.

```python
from nl2bi.core.sql_generator import SQLGenerator
from nl2bi.core.schema import SchemaExtractor

schema = SchemaExtractor("postgresql://user:password@localhost/mydb")
generator = SQLGenerator(schema)

sql, explanation = generator.generate_sql("Show me sales by region")
print(f"SQL: {sql}")
print(f"Explanation: {explanation}")

# Validate generated SQL
is_valid, error = generator.validate_sql(sql)
```

### ChartFinder

Recommends appropriate visualizations for query results.

```python
from nl2bi.core.chart_finder import ChartFinder

chart_finder = ChartFinder()

recommendations = chart_finder.recommend_charts(
    query="What are sales trends over time?",
    columns=["date", "sales", "region"],
)

for rec in recommendations:
    print(f"Chart: {rec.chart_type}")
    print(f"Title: {rec.title}")
    print(f"Why: {rec.reasoning}")
```

### NL2BIOrchestrator

Coordinates all components for end-to-end processing.

```python
from nl2bi import NL2BIOrchestrator

orchestrator = NL2BIOrchestrator(
    connection_string="postgresql://user:password@localhost/mydb"
)

# Full workflow: SQL generation → validation → execution → chart recommendations
result = orchestrator.query(
    natural_language_query="Show me monthly revenue by product",
    execute=True,
    recommend_charts=True,
)

print(f"SQL: {result['sql']}")
print(f"Rows: {len(result['data'])}")
print(f"Charts: {len(result['chart_recommendations'])}")
```

## Configuration

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Or create a `.env` file:

```
OPENAI_API_KEY=your-api-key-here
```

## Supported Databases

- PostgreSQL
- MySQL
- SQLite
- SQL Server
- Oracle
- Any SQLAlchemy-supported database

## API Reference

### NL2BIOrchestrator

#### `query(natural_language_query, execute=True, recommend_charts=True)`

Process a natural language query end-to-end.

**Parameters:**
- `natural_language_query` (str): The query in plain English
- `execute` (bool): Whether to execute the SQL query
- `recommend_charts` (bool): Whether to recommend visualizations

**Returns:**
```python
{
    "query": str,                    # Original query
    "sql": str,                      # Generated SQL
    "sql_explanation": str,          # Explanation of SQL
    "data": List[Dict],              # Query results
    "columns": List[str],            # Column names
    "chart_recommendations": List,   # Visualization suggestions
    "error": Optional[str],          # Any errors encountered
}
```

#### `generate_sql(natural_language_query)`

Generate SQL without executing.

**Returns:** Tuple[sql, explanation]

#### `find_relevant_charts(query, columns)`

Get chart recommendations for a query.

**Returns:** List of chart recommendation dictionaries

#### `extract_schema()`

Get the database schema.

**Returns:** Dictionary describing all tables and columns

#### `add_table_description(table_name, description)`

Add a description to a table for better LLM context.

#### `add_column_description(table_name, column_name, description)`

Add a description to a column.

## Examples

See the `examples/` directory for more detailed usage patterns:

- `basic_usage.py` - Getting started with NL2BI
- More examples coming soon!

## Advanced Features

### Custom Schema Descriptions

Provide context about your data for better results:

```python
orchestrator.add_table_description(
    "transactions",
    "Financial transactions including purchases, refunds, and adjustments"
)

orchestrator.add_column_description(
    "transactions", "amount",
    "Transaction amount in USD, negative for refunds"
)
```

### Error Handling

```python
result = orchestrator.query("your query")

if result["error"]:
    print(f"Error: {result['error']}")
else:
    # Process results
    for row in result["data"]:
        print(row)
```

### SQL Formatting

```python
from nl2bi.utils import format_sql

formatted = format_sql(result["sql"])
print(formatted)
```

## Models Supported

The package works with:
- **GPT-4o-mini** (default, cost-effective)
- **GPT-4** (higher quality)
- Easily extensible for other LLM providers

## Limitations

- Generated SQL depends on schema clarity and LLM quality
- Complex multi-step queries may need refinement
- Chart recommendations are suggestions, not always perfect
- Requires proper database permissions for schema extraction

## Future Roadmap

- [ ] Support for multiple LLM providers (Anthropic, Cohere, etc.)
- [ ] Caching for repeated queries
- [ ] SQL query optimization suggestions
- [ ] Interactive SQL refinement interface
- [ ] Chart generation (Plotly integration)
- [ ] Query result caching
- [ ] Multi-database federation
- [ ] Cost estimation for queries

## Contributing

Contributions welcome! Areas for improvement:

- Better chart type detection
- Support for more databases
- Query optimization
- Performance improvements
- Documentation

## License

MIT

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Built with:** Python, SQLAlchemy, OpenAI API, Pandas
