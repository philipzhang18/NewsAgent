"""
Data visualization service using Plotly for interactive charts.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import plotly.graph_objects as go
import plotly.express as px
from collections import Counter

from src.services.storage_service import storage_service

logger = logging.getLogger(__name__)


class VisualizationService:
    """Service for generating data visualizations."""

    def __init__(self):
        """Initialize visualization service."""
        self.color_scheme = {
            'positive': '#10B981',  # Green
            'neutral': '#6B7280',   # Gray
            'negative': '#EF4444',  # Red
            'primary': '#3B82F6',   # Blue
            'secondary': '#8B5CF6', # Purple
            'accent': '#F59E0B'     # Amber
        }

        logger.info("Visualization service initialized")

    async def get_sentiment_distribution(self, days: int = 7) -> go.Figure:
        """
        Create sentiment distribution pie chart.

        Args:
            days: Number of days to include

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Count sentiments
            sentiments = {'positive': 0, 'neutral': 0, 'negative': 0}

            for article in articles:
                if hasattr(article, 'sentiment_score'):
                    score = article.sentiment_score
                    if score > 0.1:
                        sentiments['positive'] += 1
                    elif score < -0.1:
                        sentiments['negative'] += 1
                    else:
                        sentiments['neutral'] += 1

            # Create pie chart
            fig = go.Figure(data=[go.Pie(
                labels=['Positive', 'Neutral', 'Negative'],
                values=[sentiments['positive'], sentiments['neutral'], sentiments['negative']],
                marker=dict(colors=[
                    self.color_scheme['positive'],
                    self.color_scheme['neutral'],
                    self.color_scheme['negative']
                ]),
                hole=0.3
            )])

            fig.update_layout(
                title=f'Sentiment Distribution (Last {days} Days)',
                showlegend=True,
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating sentiment distribution: {e}")
            return self._create_error_figure("Failed to load sentiment data")

    async def get_sentiment_timeline(self, days: int = 30) -> go.Figure:
        """
        Create sentiment timeline chart.

        Args:
            days: Number of days to include

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Group by date
            daily_sentiments = {}

            for article in articles:
                date = article.collected_at.date()
                if date not in daily_sentiments:
                    daily_sentiments[date] = {'positive': 0, 'neutral': 0, 'negative': 0, 'total': 0}

                if hasattr(article, 'sentiment_score'):
                    score = article.sentiment_score
                    if score > 0.1:
                        daily_sentiments[date]['positive'] += 1
                    elif score < -0.1:
                        daily_sentiments[date]['negative'] += 1
                    else:
                        daily_sentiments[date]['neutral'] += 1
                    daily_sentiments[date]['total'] += 1

            # Sort dates
            dates = sorted(daily_sentiments.keys())
            positive_counts = [daily_sentiments[d]['positive'] for d in dates]
            neutral_counts = [daily_sentiments[d]['neutral'] for d in dates]
            negative_counts = [daily_sentiments[d]['negative'] for d in dates]

            # Create stacked area chart
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=dates, y=positive_counts,
                name='Positive',
                mode='lines',
                stackgroup='one',
                fillcolor=self.color_scheme['positive'],
                line=dict(color=self.color_scheme['positive'])
            ))

            fig.add_trace(go.Scatter(
                x=dates, y=neutral_counts,
                name='Neutral',
                mode='lines',
                stackgroup='one',
                fillcolor=self.color_scheme['neutral'],
                line=dict(color=self.color_scheme['neutral'])
            ))

            fig.add_trace(go.Scatter(
                x=dates, y=negative_counts,
                name='Negative',
                mode='lines',
                stackgroup='one',
                fillcolor=self.color_scheme['negative'],
                line=dict(color=self.color_scheme['negative'])
            ))

            fig.update_layout(
                title=f'Sentiment Timeline (Last {days} Days)',
                xaxis_title='Date',
                yaxis_title='Number of Articles',
                hovermode='x unified',
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating sentiment timeline: {e}")
            return self._create_error_figure("Failed to load sentiment timeline")

    async def get_source_distribution(self, days: int = 7) -> go.Figure:
        """
        Create source distribution bar chart.

        Args:
            days: Number of days to include

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Count by source
            source_counts = Counter([article.source_name for article in articles])
            sources = list(source_counts.keys())
            counts = list(source_counts.values())

            # Create bar chart
            fig = go.Figure(data=[go.Bar(
                x=sources,
                y=counts,
                marker=dict(color=self.color_scheme['primary'])
            )])

            fig.update_layout(
                title=f'Articles by Source (Last {days} Days)',
                xaxis_title='Source',
                yaxis_title='Number of Articles',
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating source distribution: {e}")
            return self._create_error_figure("Failed to load source data")

    async def get_collection_trends(self, days: int = 30) -> go.Figure:
        """
        Create collection trends line chart.

        Args:
            days: Number of days to include

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Group by date
            daily_counts = Counter([article.collected_at.date() for article in articles])
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[d] for d in dates]

            # Create line chart
            fig = go.Figure(data=[go.Scatter(
                x=dates,
                y=counts,
                mode='lines+markers',
                name='Articles Collected',
                line=dict(color=self.color_scheme['primary'], width=2),
                marker=dict(size=8)
            )])

            fig.update_layout(
                title=f'Daily Collection Trends (Last {days} Days)',
                xaxis_title='Date',
                yaxis_title='Articles Collected',
                hovermode='x unified',
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating collection trends: {e}")
            return self._create_error_figure("Failed to load collection trends")

    async def get_keyword_frequency(self, days: int = 7, top_n: int = 20) -> go.Figure:
        """
        Create keyword frequency bar chart.

        Args:
            days: Number of days to include
            top_n: Number of top keywords to show

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Collect all keywords
            all_keywords = []
            for article in articles:
                if hasattr(article, 'keywords') and article.keywords:
                    all_keywords.extend(article.keywords)

            # Count frequency
            keyword_counts = Counter(all_keywords)
            top_keywords = keyword_counts.most_common(top_n)

            keywords = [k[0] for k in top_keywords]
            counts = [k[1] for k in top_keywords]

            # Create horizontal bar chart
            fig = go.Figure(data=[go.Bar(
                y=keywords[::-1],  # Reverse for better display
                x=counts[::-1],
                orientation='h',
                marker=dict(color=self.color_scheme['accent'])
            )])

            fig.update_layout(
                title=f'Top {top_n} Keywords (Last {days} Days)',
                xaxis_title='Frequency',
                yaxis_title='Keyword',
                height=600
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating keyword frequency: {e}")
            return self._create_error_figure("Failed to load keyword data")

    async def get_bias_distribution(self, days: int = 7) -> go.Figure:
        """
        Create bias distribution chart.

        Args:
            days: Number of days to include

        Returns:
            Plotly figure
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            articles = await storage_service.query_articles({
                'collected_at': {'$gte': cutoff_date}
            })

            # Collect bias scores
            bias_scores = []
            for article in articles:
                if hasattr(article, 'bias_score') and article.bias_score is not None:
                    bias_scores.append(article.bias_score)

            if not bias_scores:
                return self._create_error_figure("No bias data available")

            # Create histogram
            fig = go.Figure(data=[go.Histogram(
                x=bias_scores,
                nbinsx=30,
                marker=dict(color=self.color_scheme['secondary'])
            )])

            fig.update_layout(
                title=f'Bias Score Distribution (Last {days} Days)',
                xaxis_title='Bias Score',
                yaxis_title='Number of Articles',
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating bias distribution: {e}")
            return self._create_error_figure("Failed to load bias data")

    async def get_processing_statistics(self) -> go.Figure:
        """
        Create processing statistics chart.

        Returns:
            Plotly figure
        """
        try:
            from src.services.news_processor_service import processor_service

            stats = processor_service.get_statistics()

            # Create bar chart for statistics
            metrics = ['Processed', 'Failed', 'Retries', 'In Queue']
            values = [
                stats['statistics'].get('total_processed', 0),
                stats['statistics'].get('total_failed', 0),
                stats['statistics'].get('total_retries', 0),
                stats['queue_size']
            ]

            fig = go.Figure(data=[go.Bar(
                x=metrics,
                y=values,
                marker=dict(color=[
                    self.color_scheme['positive'],
                    self.color_scheme['negative'],
                    self.color_scheme['accent'],
                    self.color_scheme['primary']
                ])
            )])

            fig.update_layout(
                title='Processing Statistics',
                xaxis_title='Metric',
                yaxis_title='Count',
                height=400
            )

            return fig

        except Exception as e:
            logger.error(f"Error creating processing statistics: {e}")
            return self._create_error_figure("Failed to load processing statistics")

    def _create_error_figure(self, message: str) -> go.Figure:
        """
        Create an error placeholder figure.

        Args:
            message: Error message to display

        Returns:
            Plotly figure
        """
        fig = go.Figure()

        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color='red')
        )

        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400
        )

        return fig


# Global instance
visualization_service = VisualizationService()
