"""
Utility functions for NL2BI.
"""

from typing import Optional, List
import os
from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env file."""
    load_dotenv()


def get_openai_key() -> str:
    """Get OpenAI API key from environment."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return key


def format_sql(sql: str) -> str:
    """
    Format SQL query for readability.
    
    Args:
        sql: Raw SQL query
    
    Returns:
        Formatted SQL
    """
    # Simple formatting - could be expanded
    keywords = [
        "SELECT", "FROM", "WHERE", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
        "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP",
    ]
    
    formatted = sql
    for keyword in keywords:
        formatted = formatted.replace(f" {keyword} ", f"\n{keyword} ")
    
    return formatted


def validate_columns(
    provided_columns: List[str],
    required_columns: List[str],
) -> bool:
    """
    Check if required columns are available.
    
    Args:
        provided_columns: Available columns
        required_columns: Required columns
    
    Returns:
        True if all required columns are available
    """
    return all(col in provided_columns for col in required_columns)


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to max length with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
