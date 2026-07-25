"""
Read-only SQL guardrail - rejects anything that isn't a single SELECT/WITH statement.
"""

from typing import Optional, Tuple
import sqlglot
from sqlglot import exp

_FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
)


def validate_readonly(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Verify a SQL string is a single read-only SELECT/WITH statement.

    Args:
        sql: SQL query to validate

    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    try:
        statements = sqlglot.parse(sql)
    except Exception as e:
        return False, f"could not parse SQL: {e}"

    statements = [s for s in statements if s is not None]
    if not statements:
        return False, "no SQL statement found"
    if len(statements) > 1:
        return False, "multiple statements are not allowed"

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return False, f"only SELECT/WITH statements are allowed, got {type(statement).__name__}"

    for node in statement.walk():
        node = node[0] if isinstance(node, tuple) else node
        if isinstance(node, _FORBIDDEN_NODES):
            return False, f"{type(node).__name__} is not allowed in a read-only query"

    return True, None
