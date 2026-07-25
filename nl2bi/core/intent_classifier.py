"""
Classify a natural language query into one of a fixed set of BI question types.
"""

from typing import Optional
from enum import Enum
from nl2bi.core import llm_client


class QuestionType(str, Enum):
    """BI question types a query can be routed to."""
    FILTER = "filter"
    KPI = "kpi"
    GROUPING = "grouping"
    TOPN = "topn"
    COMPARISON = "comparison"
    CROSS_ENTITY = "cross_entity"
    RISK_ALERT = "risk_alert"
    FINANCIAL = "financial"
    DRILLDOWN = "drilldown"
    RECOMMENDATION = "recommendation"


_SYSTEM_PROMPT = f"""You classify business-intelligence questions into exactly one type.

Types: {", ".join(t.value for t in QuestionType)}

Respond with ONLY a JSON object of the form:
{{"question_type": "<one of the types above>"}}
"""


class IntentClassifier:
    """Classify a query's intent to steer SQL generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "openai",
    ):
        self.api_key = api_key
        self.provider = provider
        self.model = model or llm_client.default_model_for(provider)

    def classify(self, query: str) -> QuestionType:
        """
        Classify a natural language query into a QuestionType.

        Falls back to QuestionType.FILTER (the most generic type) if the LLM
        returns something unrecognized - same fail-open pattern ChartFinder
        uses for unrecognized chart types.
        """
        payload = llm_client.get_json_completion(
            self.provider, self.api_key, self.model, _SYSTEM_PROMPT, query
        )
        try:
            return QuestionType(str(payload.get("question_type", "")).strip().lower())
        except ValueError:
            return QuestionType.FILTER
