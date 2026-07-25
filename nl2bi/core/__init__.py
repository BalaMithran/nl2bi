"""
Schema extraction from databases - discovers tables, columns, relationships.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re
from sqlalchemy import inspect, create_engine
from sqlalchemy.engine import Engine


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    type: str
    nullable: bool
    primary_key: bool
    foreign_key: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TableInfo:
    """Information about a database table."""
    name: str
    columns: List[ColumnInfo]
    description: Optional[str] = None
    row_count: Optional[int] = None


class SchemaExtractor:
    """Extract and manage database schema information."""
    
    def __init__(self, connection_string: str):
        """
        Initialize with database connection string.
        
        Args:
            connection_string: SQLAlchemy connection string
        """
        self.engine: Engine = create_engine(connection_string)
        self.schema: Dict[str, TableInfo] = {}
        self._extracted = False
    
    def extract_schema(self) -> Dict[str, TableInfo]:
        """
        Extract schema from connected database.
        
        Returns:
            Dictionary mapping table names to TableInfo objects
        """
        if self._extracted:
            return self.schema
        
        inspector = inspect(self.engine)
        
        for table_name in inspector.get_table_names():
            columns = []
            
            for col in inspector.get_columns(table_name):
                col_type = str(col['type'])
                pk = col.get('primary_key', False)
                nullable = col.get('nullable', True)
                
                column_info = ColumnInfo(
                    name=col['name'],
                    type=col_type,
                    nullable=nullable,
                    primary_key=pk,
                )
                columns.append(column_info)
            
            # Get foreign keys
            fk_map = self._extract_foreign_keys(table_name, inspector)
            for col in columns:
                if col.name in fk_map:
                    col.foreign_key = fk_map[col.name]
            
            self.schema[table_name] = TableInfo(
                name=table_name,
                columns=columns,
            )
        
        self._extracted = True
        return self.schema
    
    def _extract_foreign_keys(self, table_name: str, inspector) -> Dict[str, str]:
        """Extract foreign key relationships for a table."""
        fk_map = {}
        
        try:
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                local_col = fk['constrained_columns'][0]
                remote_table = fk['referred_table']
                remote_col = fk['referred_columns'][0]
                fk_map[local_col] = f"{remote_table}.{remote_col}"
        except Exception:
            pass
        
        return fk_map
    
    def _table_to_string(self, table_info: TableInfo) -> str:
        """Format a single table's schema as LLM-readable text."""
        lines = [f"\nTable: {table_info.name}"]
        if table_info.description:
            lines.append(f"  ({table_info.description})")
        for col in table_info.columns:
            fk_info = f" -> {col.foreign_key}" if col.foreign_key else ""
            pk_info = " [PRIMARY KEY]" if col.primary_key else ""
            null_info = "" if col.nullable else " [NOT NULL]"
            desc_info = f" - {col.description}" if col.description else ""
            lines.append(
                f"  - {col.name}: {col.type}{pk_info}{null_info}{fk_info}{desc_info}"
            )
        return "\n".join(lines)

    def get_schema_string(self) -> str:
        """
        Get human-readable schema description for LLM context.

        Returns:
            Formatted schema string
        """
        if not self._extracted:
            self.extract_schema()

        return "\n".join(self._table_to_string(t) for t in self.schema.values())

    def get_relevant_schema_string(self, query: str, top_k: int = 15) -> str:
        """
        Get schema text for only the tables most relevant to a query.

        Scores tables by lexical token overlap between the query and each
        table's name/columns, to avoid dumping the full schema into every
        prompt on large databases.

        Args:
            query: Natural language query to score tables against
            top_k: Maximum number of tables to include

        Returns:
            Formatted schema string for the top-k most relevant tables
        """
        if not self._extracted:
            self.extract_schema()

        if len(self.schema) <= top_k:
            return self.get_schema_string()

        # ponytail: lexical keyword overlap, not embeddings. Upgrade to the
        # vector store (nl2bi.core.vector_store, Phase 7) if schemas have low
        # lexical overlap with how users phrase questions (e.g. "churn" never
        # appearing in a column named cancelled_at).
        query_tokens = set(re.findall(r"\w+", query.lower()))

        scored = []
        for table_info in self.schema.values():
            table_tokens = set(re.findall(r"\w+", table_info.name.lower()))
            for col in table_info.columns:
                table_tokens |= set(re.findall(r"\w+", col.name.lower()))
            score = len(query_tokens & table_tokens)
            scored.append((score, table_info))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_tables = [table for _, table in scored[:top_k]]
        return "\n".join(self._table_to_string(t) for t in top_tables)
    
    def add_table_description(self, table_name: str, description: str) -> None:
        """Add human-readable description to a table."""
        if table_name in self.schema:
            self.schema[table_name].description = description
    
    def add_column_description(
        self, table_name: str, column_name: str, description: str
    ) -> None:
        """Add human-readable description to a column."""
        if table_name in self.schema:
            for col in self.schema[table_name].columns:
                if col.name == column_name:
                    col.description = description
                    break
    
    def get_tables(self) -> List[str]:
        """Get list of table names."""
        if not self._extracted:
            self.extract_schema()
        return list(self.schema.keys())
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get info about a specific table."""
        if not self._extracted:
            self.extract_schema()
        return self.schema.get(table_name)
