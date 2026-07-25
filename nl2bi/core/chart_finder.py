"""
Chart type recommendations based on data characteristics and query intent.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import os
from openai import OpenAI


class ChartType(str, Enum):
    """Supported chart types."""
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    PIE = "pie"
    HISTOGRAM = "histogram"
    BOX = "box"
    HEATMAP = "heatmap"
    AREA = "area"
    TABLE = "table"


@dataclass
class ChartRecommendation:
    """Chart recommendation with metadata."""
    chart_type: ChartType
    title: str
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    group_by: Optional[str] = None
    reasoning: Optional[str] = None


class ChartFinder:
    """Find appropriate chart types for queries and data."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize chart finder.

        Args:
            api_key: OpenAI API key
            model: LLM model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def recommend_charts(
        self,
        query: str,
        columns: List[str],
        sample_data: Optional[Dict[str, Any]] = None,
    ) -> List[ChartRecommendation]:
        """
        Recommend chart types for a query.

        Args:
            query: Natural language query
            columns: Available columns in result set
            sample_data: Optional sample data for analysis

        Returns:
            List of chart recommendations
        """
        system_prompt = """You are a data visualization expert. Recommend appropriate chart types.

Consider:
1. The type of question being asked (comparison, trend, distribution, etc.)
2. Available columns and their data types
3. Number of dimensions (1D, 2D, 3D)
4. Cardinality of categorical fields

Respond with ONLY a JSON object of the form:
{"recommendations": [
  {"chart_type": "<bar|line|scatter|pie|histogram|box|heatmap|area|table>",
   "title": "<suggested title>",
   "x_column": "<column name or null>",
   "y_column": "<column name or null>",
   "group_by": "<column name or null>",
   "reasoning": "<why this chart works>"}
]}
"""

        user_prompt = f"""Query: {query}

Available columns: {', '.join(columns)}

{f'Sample data structure: {sample_data}' if sample_data else ''}

Recommend the best 2-3 chart types for visualizing this query result."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        payload = json.loads(response.choices[0].message.content)
        return [
            self._parse_recommendation(rec)
            for rec in payload.get("recommendations", [])
            if rec.get("chart_type")
        ]

    def _parse_recommendation(self, rec: Dict[str, Any]) -> ChartRecommendation:
        """Convert a single JSON recommendation into a ChartRecommendation."""
        try:
            chart_type = ChartType(str(rec["chart_type"]).strip().lower())
        except ValueError:
            chart_type = ChartType.TABLE

        return ChartRecommendation(
            chart_type=chart_type,
            title=rec.get("title") or "Chart",
            x_column=rec.get("x_column") or None,
            y_column=rec.get("y_column") or None,
            group_by=rec.get("group_by") or None,
            reasoning=rec.get("reasoning") or "",
        )

    def get_chart_config(self, recommendation: ChartRecommendation) -> Dict[str, Any]:
        """
        Convert recommendation to chart configuration.

        Returns:
            Dictionary with chart config (e.g., for Plotly, Matplotlib)
        """
        return {
            "type": recommendation.chart_type.value,
            "title": recommendation.title,
            "x": recommendation.x_column,
            "y": recommendation.y_column,
            "color": recommendation.group_by,
        }
