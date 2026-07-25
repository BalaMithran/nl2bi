"""
Schema extraction from databases - discovers tables, columns, relationships.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import re
from openai import OpenAI
from sqlalchemy import inspect, create_engine
from sqlalchemy.engine import Engine
from nl2bi.core.vector_store import EMBEDDING_MODEL, _cosine_similarity


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
    
    def __init__(self, connection_string: str, api_key: Optional[str] = None):
        """
        Initialize with database connection string.

        Args:
            connection_string: SQLAlchemy connection string
            api_key: OpenAI API key, used for embedding-based schema retrieval.
                Without one, get_relevant_schema_string() falls back to lexical
                keyword overlap.
        """
        self.engine: Engine = create_engine(connection_string)
        self.schema: Dict[str, TableInfo] = {}
        self._extracted = False
        self.glossary: Dict[str, Tuple[str, Optional[str]]] = {}
        self.api_key = api_key
        self._table_embeddings: Dict[str, List[float]] = {}
        self._embeddings_ready: Optional[bool] = None
    
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

    def _glossary_string(self) -> str:
        """Format the business-term glossary as LLM-readable text, if any terms exist."""
        if not self.glossary:
            return ""
        lines = ["\nBusiness terms:"]
        for term, (maps_to, description) in self.glossary.items():
            desc_info = f" - {description}" if description else ""
            lines.append(f"  - {term} -> {maps_to}{desc_info}")
        return "\n".join(lines)

    def get_schema_string(self) -> str:
        """
        Get human-readable schema description for LLM context.

        Returns:
            Formatted schema string
        """
        if not self._extracted:
            self.extract_schema()

        tables = "\n".join(self._table_to_string(t) for t in self.schema.values())
        return tables + self._glossary_string()

    def get_relevant_schema_string(self, query: str, top_k: int = 15) -> str:
        """
        Get schema text for only the tables most relevant to a query.

        Ranks tables by embedding similarity when an api_key is configured,
        falling back to lexical token overlap if no key is set or the
        embedding call fails for any reason - this keeps the method usable
        offline/without a key, same fail-open pattern as IntentClassifier.

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

        query_tokens = set(re.findall(r"\w+", query.lower()))
        boosted_tables = self._glossary_boosted_tables(query_tokens)

        if self._ensure_table_embeddings():
            top_tables = self._rank_by_embedding(query, boosted_tables, top_k)
        else:
            top_tables = self._rank_by_lexical_overlap(query_tokens, boosted_tables, top_k)

        return "\n".join(self._table_to_string(t) for t in top_tables) + self._glossary_string()

    def _glossary_boosted_tables(self, query_tokens: set) -> set:
        """Table names whose business-term glossary entry matches the query.

        Business terms let a query match a table even with zero literal
        column-name/embedding overlap (e.g. "churn" -> subscriptions.cancelled_at).
        """
        boosted = set()
        for term, (maps_to, _description) in self.glossary.items():
            if set(re.findall(r"\w+", term.lower())) & query_tokens:
                boosted.add(maps_to.split(".")[0])
        return boosted

    def _ensure_table_embeddings(self) -> bool:
        """Lazily embed every table's schema text, once per instance.

        Returns False (cached for the instance's lifetime, no retries) if no
        api_key is set or the embedding call fails - callers should fall
        back to lexical scoring in that case.
        """
        if self._embeddings_ready is not None:
            return self._embeddings_ready
        if not self.api_key:
            self._embeddings_ready = False
            return False
        try:
            client = OpenAI(api_key=self.api_key)
            table_names = list(self.schema.keys())
            texts = [self._table_to_string(self.schema[name]) for name in table_names]
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            self._table_embeddings = {
                name: item.embedding for name, item in zip(table_names, response.data)
            }
            self._embeddings_ready = True
        except Exception:
            self._embeddings_ready = False
        return self._embeddings_ready

    def _rank_by_embedding(
        self, query: str, boosted_tables: set, top_k: int
    ) -> List[TableInfo]:
        try:
            client = OpenAI(api_key=self.api_key)
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
            query_embedding = response.data[0].embedding
        except Exception:
            query_tokens = set(re.findall(r"\w+", query.lower()))
            return self._rank_by_lexical_overlap(query_tokens, boosted_tables, top_k)

        scored = []
        for table_info in self.schema.values():
            score = _cosine_similarity(query_embedding, self._table_embeddings[table_info.name])
            if table_info.name in boosted_tables:
                score += 1.0  # a glossary match always outranks pure similarity noise
            scored.append((score, table_info))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [table for _, table in scored[:top_k]]

    def _rank_by_lexical_overlap(
        self, query_tokens: set, boosted_tables: set, top_k: int
    ) -> List[TableInfo]:
        # ponytail: lexical keyword overlap. Only reached without an api_key
        # or when the embedding call fails - the primary path above is
        # embedding similarity.
        scored = []
        for table_info in self.schema.values():
            table_tokens = set(re.findall(r"\w+", table_info.name.lower()))
            for col in table_info.columns:
                table_tokens |= set(re.findall(r"\w+", col.name.lower()))
            score = len(query_tokens & table_tokens)
            if table_info.name in boosted_tables:
                score += 1
            scored.append((score, table_info))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [table for _, table in scored[:top_k]]
    
    def add_business_term(
        self, term: str, maps_to: str, description: Optional[str] = None
    ) -> None:
        """
        Map a business term to a schema element, e.g. "churn" -> "subscriptions.cancelled_at".

        Args:
            term: Business term as users would phrase it
            maps_to: "table" or "table.column" the term maps to
            description: Optional extra context for the LLM
        """
        self.glossary[term] = (maps_to, description)

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
