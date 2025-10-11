"""
Enhanced Dash application with intelligent search and interactive features.
"""

import logging
from dash import Dash, html, dcc, Input, Output, State, callback, dash_table, ctx
import plotly.graph_objects as go
from flask import Flask
import pandas as pd
from datetime import datetime, timezone, timedelta

from src.services.visualization_service import visualization_service
from src.services.storage_service import storage_service

logger = logging.getLogger(__name__)


def create_enhanced_dash_app(flask_app: Flask) -> Dash:
    """
    Create enhanced Dash application with search and filtering.

    Args:
        flask_app: Flask application instance

    Returns:
        Dash application instance
    """
    dash_app = Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True
    )

    # Enhanced layout with search
    dash_app.layout = html.Div([
        # Header
        html.Div([
            html.H1('📰 NewsAgent Intelligence Dashboard', className='dashboard-title'),
            html.P('AI-powered news collection, analysis, and search', className='dashboard-subtitle')
        ], className='dashboard-header'),

        # Search and Filter Panel
        html.Div([
            # Search bar
            html.Div([
                html.Label('🔍 Smart Search:', style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                dcc.Input(
                    id='search-input',
                    type='text',
                    placeholder='Search by title, content, keywords, or source... (Press Enter or click Search)',
                    debounce=True,
                    style={'width': '100%', 'padding': '10px', 'fontSize': '14px', 'borderRadius': '5px', 'border': '1px solid #ddd'}
                ),
            ], style={'flex': '2', 'marginRight': '10px'}),

            # Sentiment filter
            html.Div([
                html.Label('Sentiment:', style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                dcc.Dropdown(
                    id='sentiment-filter',
                    options=[
                        {'label': 'All', 'value': 'all'},
                        {'label': '😊 Positive', 'value': 'positive'},
                        {'label': '😐 Neutral', 'value': 'neutral'},
                        {'label': '😟 Negative', 'value': 'negative'},
                        {'label': '🤔 Mixed', 'value': 'mixed'}
                    ],
                    value='all',
                    clearable=False,
                    style={'fontSize': '14px'}
                )
            ], style={'flex': '1', 'marginRight': '10px'}),

            # Time range
            html.Div([
                html.Label('Time Range:', style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                dcc.Dropdown(
                    id='time-range-selector',
                    options=[
                        {'label': 'Last 24 Hours', 'value': 1},
                        {'label': 'Last 7 Days', 'value': 7},
                        {'label': 'Last 30 Days', 'value': 30},
                        {'label': 'Last 90 Days', 'value': 90}
                    ],
                    value=7,
                    clearable=False,
                    style={'fontSize': '14px'}
                )
            ], style={'flex': '1', 'marginRight': '10px'}),

            # Search button
            html.Div([
                html.Label('⠀', style={'marginBottom': '5px'}),  # Spacer
                html.Button('Search', id='search-button', n_clicks=0,
                           style={'width': '100%', 'padding': '10px', 'fontSize': '14px',
                                  'backgroundColor': '#667eea', 'color': 'white',
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer'})
            ], style={'flex': '0.5'})
        ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '20px', 'padding': '20px',
                  'backgroundColor': 'white', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),

        # Tabs for different views
        dcc.Tabs(id='view-tabs', value='articles', children=[
            dcc.Tab(label='📄 Articles', value='articles', style={'fontSize': '14px'}),
            dcc.Tab(label='📊 Analytics', value='analytics', style={'fontSize': '14px'}),
        ], style={'marginBottom': '20px'}),

        # Content area
        html.Div(id='tab-content'),

        # Auto-refresh interval
        dcc.Interval(id='interval-component', interval=60000, n_intervals=0, disabled=True),

        # Store for search results
        dcc.Store(id='search-results-store'),
        dcc.Store(id='selected-article-store'),

        # Modal for article details
        html.Div(id='article-modal', style={'display': 'none'})
    ], className='dashboard-container', style={'padding': '20px', 'backgroundColor': '#f8f9fa'})

    register_enhanced_callbacks(dash_app)
    logger.info("Enhanced Dash application created")
    return dash_app


def register_enhanced_callbacks(dash_app: Dash):
    """Register enhanced callbacks with search functionality."""

    @dash_app.callback(
        Output('tab-content', 'children'),
        Input('view-tabs', 'value'),
        Input('search-results-store', 'data')
    )
    def render_tab_content(active_tab, search_results):
        """Render content based on active tab."""
        if active_tab == 'articles':
            return render_articles_view(search_results)
        else:
            return render_analytics_view()

    @dash_app.callback(
        Output('search-results-store', 'data'),
        [Input('search-button', 'n_clicks'),
         Input('search-input', 'n_submit')],  # Also trigger on Enter key
        State('search-input', 'value'),
        State('sentiment-filter', 'value'),
        State('time-range-selector', 'value')
    )
    def perform_search(n_clicks, n_submit, search_text, sentiment, days):
        """Execute intelligent search with keyword support."""
        import asyncio
        import requests
        from src.config.settings import settings

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # First try to get from storage
            filters = {}

            # Time filter
            if days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                filters['collected_at'] = {'$gte': cutoff}

            # Sentiment filter
            if sentiment and sentiment != 'all':
                filters['sentiment'] = sentiment

            # Build parameters for get_articles
            cutoff_date = None
            if days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get articles from storage
            articles = loop.run_until_complete(
                storage_service.get_articles(
                    limit=100,
                    sentiment=sentiment if sentiment != 'all' else None,
                    start_date=cutoff_date
                )
            )

            # If no articles in storage and search text provided, try NewsAPI
            if not articles and search_text and settings.NEWS_API_KEY:
                try:
                    params = {
                        'apiKey': settings.NEWS_API_KEY,
                        'q': search_text,
                        'language': 'en',
                        'sortBy': 'publishedAt',
                        'pageSize': 50
                    }

                    resp = requests.get(
                        'https://newsapi.org/v2/everything',
                        params=params,
                        timeout=10
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        newsapi_articles = data.get('articles', [])

                        # Convert NewsAPI articles to NewsArticle model and save to database
                        from src.models.news_models import NewsArticle
                        import hashlib
                        import uuid

                        saved_articles = []
                        for item in newsapi_articles[:50]:
                            try:
                                # Generate unique ID from URL
                                article_id = hashlib.md5(item.get('url', '').encode()).hexdigest() if item.get('url') else str(uuid.uuid4())

                                # Create NewsArticle object
                                article = NewsArticle(
                                    id=article_id,
                                    title=item.get('title', ''),
                                    content=item.get('content', '') or item.get('description', ''),
                                    summary=item.get('description', ''),
                                    url=item.get('url', ''),
                                    source_name=item.get('source', {}).get('name', 'NewsAPI'),
                                    published_at=datetime.fromisoformat(item.get('publishedAt', '').replace('Z', '+00:00')) if item.get('publishedAt') else datetime.now(timezone.utc),
                                    collected_at=datetime.now(timezone.utc),
                                    sentiment='neutral',
                                    category=None,
                                    keywords=[]
                                )

                                # Save to database (async)
                                loop.run_until_complete(storage_service.save_article(article))

                                # Add to results
                                saved_articles.append({
                                    'id': article.id,
                                    'title': article.title,
                                    'source': article.source_name,
                                    'published': article.published_at.isoformat()[:10] if article.published_at else '',
                                    'sentiment': 'neutral',
                                    'summary': article.summary or (article.content[:200] + '...' if article.content else ''),
                                    'url': article.url,
                                    'content': article.content or ''
                                })

                            except Exception as article_error:
                                logger.warning(f"Error saving article: {str(article_error)}")
                                continue

                        logger.info(f"Saved {len(saved_articles)} articles from NewsAPI to database")
                        return saved_articles
                except Exception as e:
                    logger.warning(f"NewsAPI search failed: {str(e)}")

            # Text search in stored articles if provided
            if search_text and articles:
                search_lower = search_text.lower()
                filtered = []
                for article in articles:
                    if (search_lower in article.title.lower() or
                        search_lower in article.content.lower() or
                        search_lower in article.source_name.lower() or
                        any(search_lower in str(kw).lower() for kw in (article.keywords or []))):
                        filtered.append(article)
                articles = filtered

            # Convert to dict for storage
            results = []
            for article in articles[:50]:  # Limit to 50 results
                results.append({
                    'id': article.id,
                    'title': article.title,
                    'source': article.source_name,
                    'published': article.published_at.isoformat()[:10] if article.published_at else '',
                    'sentiment': article.sentiment.value if hasattr(article.sentiment, 'value') else str(article.sentiment),
                    'summary': article.summary or article.content[:200] + '...' if article.content else '',
                    'url': article.url,
                    'content': article.content or ''
                })

            return results if results else []

        finally:
            loop.close()

    def render_articles_view(search_results):
        """Render articles list view."""
        if not search_results:
            return html.Div([
                html.Div([
                    html.I(className='fas fa-search', style={'fontSize': '48px', 'color': '#ccc', 'marginBottom': '20px'}),
                    html.H3('No articles found', style={'color': '#666', 'marginTop': '20px'}),
                    html.P('Try one of the following:', style={'marginBottom': '15px'}),
                    html.Ul([
                        html.Li('Enter a keyword (e.g., "AI", "climate", "technology") and click Search'),
                        html.Li('Try a broader search term'),
                        html.Li('Adjust the time range filter'),
                        html.Li('Change or remove the sentiment filter')
                    ], style={'textAlign': 'left', 'maxWidth': '400px', 'margin': '0 auto', 'color': '#666'}),
                    html.Div([
                        html.P('💡 Tip: The search will query NewsAPI for latest articles if no local data is found',
                              style={'marginTop': '20px', 'padding': '15px', 'backgroundColor': '#EFF6FF',
                                    'borderRadius': '8px', 'color': '#1E40AF', 'fontSize': '14px'})
                    ])
                ], style={'textAlign': 'center', 'padding': '60px', 'backgroundColor': 'white',
                         'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'})
            ])

        # Create article cards
        article_cards = []
        for article in search_results:
            sentiment_emoji = {
                'positive': '😊',
                'neutral': '😐',
                'negative': '😟',
                'mixed': '🤔'
            }.get(article['sentiment'], '😐')

            sentiment_color = {
                'positive': '#10B981',
                'neutral': '#6B7280',
                'negative': '#EF4444',
                'mixed': '#F59E0B'
            }.get(article['sentiment'], '#6B7280')

            card = html.Div([
                html.Div([
                    html.H3(article['title'], style={'margin': '0 0 10px 0', 'color': '#333'}),
                    html.Div([
                        html.Span(f"📰 {article['source']}",
                                 style={'marginRight': '15px', 'color': '#666'}),
                        html.Span(f"📅 {article['published'][:10] if article['published'] else 'N/A'}",
                                 style={'marginRight': '15px', 'color': '#666'}),
                        html.Span(f"{sentiment_emoji} {article['sentiment'].title()}",
                                 style={'color': sentiment_color, 'fontWeight': 'bold'})
                    ], style={'marginBottom': '10px', 'fontSize': '14px'}),
                    html.P(article['summary'], style={'color': '#555', 'lineHeight': '1.6'}),
                    html.Div([
                        html.A('Read Full Article →', href=article['url'], target='_blank',
                              style={'color': '#667eea', 'textDecoration': 'none', 'fontWeight': 'bold'})
                    ])
                ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px',
                         'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 'marginBottom': '15px',
                         'transition': 'box-shadow 0.3s ease',
                         'borderLeft': f'4px solid {sentiment_color}'})
            ], id={'type': 'article-card', 'index': article['id']})
            article_cards.append(card)

        return html.Div([
            html.Div([
                html.H4(f'Found {len(search_results)} articles',
                       style={'margin': '0', 'color': '#333'}),
            ], style={'marginBottom': '20px', 'padding': '15px', 'backgroundColor': 'white',
                     'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
            html.Div(article_cards)
        ])

    def render_analytics_view():
        """Render analytics charts view."""
        return html.Div([
            # Charts grid
            html.Div([
                # Row 1
                html.Div([
                    html.Div([
                        dcc.Loading(
                            children=[dcc.Graph(id='sentiment-distribution-chart')],
                            type='circle'
                        )
                    ], className='chart-container'),
                    html.Div([
                        dcc.Loading(
                            children=[dcc.Graph(id='sentiment-timeline-chart')],
                            type='circle'
                        )
                    ], className='chart-container')
                ], className='chart-row'),

                # Row 2
                html.Div([
                    html.Div([
                        dcc.Loading(
                            children=[dcc.Graph(id='source-distribution-chart')],
                            type='circle'
                        )
                    ], className='chart-container'),
                    html.Div([
                        dcc.Loading(
                            children=[dcc.Graph(id='keyword-frequency-chart')],
                            type='circle'
                        )
                    ], className='chart-container')
                ], className='chart-row')
            ])
        ])

    # Chart callbacks
    @dash_app.callback(
        Output('sentiment-distribution-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_sentiment_distribution(days, n):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                visualization_service.get_sentiment_distribution(days=days)
            )
        finally:
            loop.close()

    @dash_app.callback(
        Output('sentiment-timeline-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_sentiment_timeline(days, n):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                visualization_service.get_sentiment_timeline(days=days)
            )
        finally:
            loop.close()

    @dash_app.callback(
        Output('source-distribution-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_source_distribution(days, n):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                visualization_service.get_source_distribution(days=days)
            )
        finally:
            loop.close()

    @dash_app.callback(
        Output('keyword-frequency-chart', 'figure'),
        Input('time-range-selector', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def update_keyword_frequency(days, n):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                visualization_service.get_keyword_frequency(days=days, top_n=20)
            )
        finally:
            loop.close()

    logger.info("Enhanced callbacks registered")
