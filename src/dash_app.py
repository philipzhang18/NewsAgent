"""
Dash application for interactive data visualization dashboard.
"""

import logging
from dash import Dash, html, dcc, Input, Output, callback
import plotly.graph_objects as go
from flask import Flask

from src.services.visualization_service import visualization_service

logger = logging.getLogger(__name__)


def create_dash_app(flask_app: Flask) -> Dash:
    """
    Create and configure Dash application.

    Args:
        flask_app: Flask application instance

    Returns:
        Dash application instance
    """
    # Create Dash app
    dash_app = Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True
    )

    # Define layout
    dash_app.layout = html.Div([
        html.Div([
            html.H1('NewsAgent Analytics Dashboard', className='dashboard-title'),
            html.P('Real-time news collection and analysis insights', className='dashboard-subtitle')
        ], className='dashboard-header'),

        # Control panel
        html.Div([
            html.Div([
                html.Label('Time Range:'),
                dcc.Dropdown(
                    id='time-range-selector',
                    options=[
                        {'label': 'Last 24 Hours', 'value': 1},
                        {'label': 'Last 7 Days', 'value': 7},
                        {'label': 'Last 30 Days', 'value': 30},
                        {'label': 'Last 90 Days', 'value': 90}
                    ],
                    value=7,
                    clearable=False
                )
            ], className='control-item'),

            html.Div([
                html.Label('Auto Refresh:'),
                dcc.Dropdown(
                    id='refresh-interval-selector',
                    options=[
                        {'label': 'Off', 'value': 0},
                        {'label': 'Every 30s', 'value': 30000},
                        {'label': 'Every 1 min', 'value': 60000},
                        {'label': 'Every 5 min', 'value': 300000}
                    ],
                    value=0,
                    clearable=False
                )
            ], className='control-item'),
        ], className='control-panel'),

        # Auto-refresh interval
        dcc.Interval(
            id='interval-component',
            interval=60000,  # Default 1 minute
            n_intervals=0,
            disabled=True
        ),

        # Charts grid
        html.Div([
            # Row 1: Sentiment distribution and timeline
            html.Div([
                html.Div([
                    dcc.Loading(
                        id='loading-sentiment-dist',
                        children=[dcc.Graph(id='sentiment-distribution-chart')],
                        type='circle'
                    )
                ], className='chart-container'),

                html.Div([
                    dcc.Loading(
                        id='loading-sentiment-timeline',
                        children=[dcc.Graph(id='sentiment-timeline-chart')],
                        type='circle'
                    )
                ], className='chart-container')
            ], className='chart-row'),

            # Row 2: Source distribution and collection trends
            html.Div([
                html.Div([
                    dcc.Loading(
                        id='loading-source-dist',
                        children=[dcc.Graph(id='source-distribution-chart')],
                        type='circle'
                    )
                ], className='chart-container'),

                html.Div([
                    dcc.Loading(
                        id='loading-collection-trends',
                        children=[dcc.Graph(id='collection-trends-chart')],
                        type='circle'
                    )
                ], className='chart-container')
            ], className='chart-row'),

            # Row 3: Keyword frequency and bias distribution
            html.Div([
                html.Div([
                    dcc.Loading(
                        id='loading-keyword-freq',
                        children=[dcc.Graph(id='keyword-frequency-chart')],
                        type='circle'
                    )
                ], className='chart-container'),

                html.Div([
                    dcc.Loading(
                        id='loading-bias-dist',
                        children=[dcc.Graph(id='bias-distribution-chart')],
                        type='circle'
                    )
                ], className='chart-container')
            ], className='chart-row'),

            # Row 4: Processing statistics
            html.Div([
                html.Div([
                    dcc.Loading(
                        id='loading-processing-stats',
                        children=[dcc.Graph(id='processing-statistics-chart')],
                        type='circle'
                    )
                ], className='chart-container-full')
            ], className='chart-row')
        ], className='charts-grid'),

        # Footer
        html.Div([
            html.P('Powered by NewsAgent | Data updates automatically'),
        ], className='dashboard-footer')
    ], className='dashboard-container')

    # Register callbacks
    register_callbacks(dash_app)

    logger.info("Dash application created and configured")

    return dash_app


def register_callbacks(dash_app: Dash):
    """
    Register Dash callbacks for interactive updates.

    Args:
        dash_app: Dash application instance
    """

    @dash_app.callback(
        Output('interval-component', 'interval'),
        Output('interval-component', 'disabled'),
        Input('refresh-interval-selector', 'value')
    )
    def update_refresh_interval(interval_value):
        """Update auto-refresh interval."""
        if interval_value == 0:
            return 60000, True  # Disabled
        return interval_value, False

    @dash_app.callback(
        Output('sentiment-distribution-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_sentiment_distribution(days, n):
        """Update sentiment distribution chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_sentiment_distribution(days=days)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('sentiment-timeline-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_sentiment_timeline(days, n):
        """Update sentiment timeline chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_sentiment_timeline(days=days)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('source-distribution-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_source_distribution(days, n):
        """Update source distribution chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_source_distribution(days=days)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('collection-trends-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_collection_trends(days, n):
        """Update collection trends chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_collection_trends(days=days)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('keyword-frequency-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_keyword_frequency(days, n):
        """Update keyword frequency chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_keyword_frequency(days=days, top_n=20)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('bias-distribution-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_bias_distribution(days, n):
        """Update bias distribution chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_bias_distribution(days=days)
            )
            return fig
        finally:
            loop.close()

    @dash_app.callback(
        Output('processing-statistics-chart', 'figure'),
        Input('interval-component', 'n_intervals')
    )
    def update_processing_statistics(n):
        """Update processing statistics chart."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            fig = loop.run_until_complete(
                visualization_service.get_processing_statistics()
            )
            return fig
        finally:
            loop.close()

    logger.info("Dash callbacks registered")
