"""
Chart type recommendations based on data characteristics and query intent.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
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
        
        Return recommendations in this format:
        1. CHART_TYPE: <type>
           TITLE: <suggested title>
           X_COLUMN: <column name or omit if not applicable>
           Y_COLUMN: <column name or omit if not applicable>
           GROUP_BY: <column name or omit if not applicable>
           REASONING: <why this chart works>
        """
        
        user_prompt = f"""Query: {query}

Available columns: {', '.join(columns)}

{f'Sample data structure: {sample_data}' if sample_data else ''}

Recommend the best 2-3 chart types for visualizing this query result."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        
        content = response.choices[0].message.content
        recommendations = self._parse_recommendations(content, columns)
        
        return recommendations
    
    def _parse_recommendations(
        self, content: str, columns: List[str]
    ) -> List[ChartRecommendation]:
        """Parse LLM response into chart recommendations."""
        recommendations = []
        
        blocks = content.split("\n\n")
        for block in blocks:
            if not block.strip():
                continue
            
            rec = self._parse_recommendation_block(block, columns)
            if rec:
                recommendations.append(rec)
        
        return recommendations
    
    def _parse_recommendation_block(
        self, block: str, available_columns: List[str]
    ) -> Optional[ChartRecommendation]:
        """Parse a single recommendation block."""
        lines = block.strip().split("\n")
        
        chart_type = None
        title = "Chart"
        x_col = None
        y_col = None
        group_by = None
        reasoning = ""
        
        for line in lines:
            if "CHART_TYPE:" in line:
                ct = line.split("CHART_TYPE:")[-1].strip().lower()
                try:
                    chart_type = ChartType(ct)
                except ValueError:
                    chart_type = ChartType.TABLE
            elif "TITLE:" in line:
                title = line.split("TITLE:")[-1].strip()
            elif "X_COLUMN:" in line:
                x_col = line.split("X_COLUMN:")[-1].strip() or None
            elif "Y_COLUMN:" in line:
                y_col = line.split("Y_COLUMN:")[-1].strip() or None
            elif "GROUP_BY:" in line:
                group_by = line.split("GROUP_BY:")[-1].strip() or None
            elif "REASONING:" in line:
                reasoning = line.split("REASONING:")[-1].strip()
        
        if chart_type:
            return ChartRecommendation(
                chart_type=chart_type,
                title=title,
                x_column=x_col,
                y_column=y_col,
                group_by=group_by,
                reasoning=reasoning,
            )
        
        return None
    
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
