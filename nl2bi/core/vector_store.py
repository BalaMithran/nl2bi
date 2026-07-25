"""
Lightweight embedding store - JSON-persisted, linear-scan cosine similarity.
"""

from typing import Any, Dict, List, Optional
import json
import math
import os
from openai import OpenAI

_EMBEDDING_MODEL = "text-embedding-3-small"


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SimpleVectorStore:
    """
    Minimal embedding store: add(text, metadata), search(query, top_k).

    # ponytail: linear-scan cosine similarity over an in-memory list, no ANN
    # index. Fine for low-thousands of short strings (schema/query history);
    # swap for a real vector DB if the corpus grows past that.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._entries: List[Dict[str, Any]] = []

    def _embed(self, text: str) -> List[float]:
        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=_EMBEDDING_MODEL, input=text)
        return response.data[0].embedding

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Embed and store a piece of text with optional metadata."""
        self._entries.append({
            "text": text,
            "embedding": self._embed(text),
            "metadata": metadata or {},
        })

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return the top_k stored entries most similar to the query."""
        if not self._entries:
            return []
        query_embedding = self._embed(query)
        scored = [
            (_cosine_similarity(query_embedding, entry["embedding"]), entry)
            for entry in self._entries
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def save(self, path: str) -> None:
        """Persist all entries to a JSON file."""
        with open(path, "w") as f:
            json.dump(self._entries, f)

    def load(self, path: str) -> None:
        """Load entries from a JSON file, replacing anything in memory."""
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            self._entries = json.load(f)
