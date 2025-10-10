# Data Visualization Guide

## Overview

NewsAgent provides powerful data visualization capabilities using Plotly and Dash for interactive charts and analytics dashboards.

## Features

### Interactive Dashboard
- Real-time data updates
- Customizable time ranges
- Auto-refresh capabilities
- Multiple chart types
- Responsive design

### Available Visualizations

1. **Sentiment Distribution** - Pie chart showing positive/neutral/negative sentiment breakdown
2. **Sentiment Timeline** - Area chart showing sentiment trends over time
3. **Source Distribution** - Bar chart showing article counts by source
4. **Collection Trends** - Line chart showing daily article collection volume
5. **Keyword Frequency** - Horizontal bar chart showing most common keywords
6. **Bias Distribution** - Histogram showing bias score distribution
7. **Processing Statistics** - Bar chart showing processing metrics

## Integration

### Flask Integration

```python
from flask import Flask
from src.dash_app import create_dash_app
from src.api.visualization_api import init_visualization_api

# Initialize Flask app
app = Flask(__name__)

# Initialize visualization API
init_visualization_api(app)

# Create Dash dashboard
dash_app = create_dash_app(app)

# Dashboard available at /dashboard/
```

### Standalone Dash App

```python
from src.dash_app import create_dash_app
from flask import Flask

app = Flask(__name__)
dash_app = create_dash_app(app)

if __name__ == '__main__':
    app.run(debug=True)
```

## API Endpoints

All visualization endpoints support rate limiting and return Plotly figure data.

### Sentiment Distribution
```http
GET /api/visualization/sentiment/distribution?days=7
```

Response:
```json
{
  "success": true,
  "figure": {
    "data": [...],
    "layout": {...}
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Sentiment Timeline
```http
GET /api/visualization/sentiment/timeline?days=30
```

### Source Distribution
```http
GET /api/visualization/sources/distribution?days=7
```

### Collection Trends
```http
GET /api/visualization/collection/trends?days=30
```

### Keyword Frequency
```http
GET /api/visualization/keywords/frequency?days=7&top_n=20
```

### Bias Distribution
```http
GET /api/visualization/bias/distribution?days=7
```

### Processing Statistics
```http
GET /api/visualization/processing/statistics
```

## Dashboard Usage

### Accessing the Dashboard

Navigate to: `http://localhost:5000/dashboard/`

### Controls

#### Time Range Selector
- Last 24 Hours
- Last 7 Days
- Last 30 Days
- Last 90 Days

Changes the time range for all applicable charts.

#### Auto Refresh
- Off
- Every 30 seconds
- Every 1 minute
- Every 5 minutes

Automatically refreshes all charts at the selected interval.

### Chart Interactions

All Plotly charts support:
- **Zoom**: Click and drag to zoom into a region
- **Pan**: Shift + click and drag to pan
- **Reset**: Double-click to reset view
- **Hover**: Hover over data points for details
- **Download**: Click camera icon to save as PNG
- **Selection**: Click legend items to toggle series

## Programmatic Usage

### Using Visualization Service

```python
from src.services.visualization_service import visualization_service

# Get sentiment distribution
fig = await visualization_service.get_sentiment_distribution(days=7)

# Get sentiment timeline
fig = await visualization_service.get_sentiment_timeline(days=30)

# Get source distribution
fig = await visualization_service.get_source_distribution(days=7)

# Get collection trends
fig = await visualization_service.get_collection_trends(days=30)

# Get keyword frequency
fig = await visualization_service.get_keyword_frequency(days=7, top_n=20)

# Get bias distribution
fig = await visualization_service.get_bias_distribution(days=7)

# Get processing statistics
fig = await visualization_service.get_processing_statistics()
```

### Saving Charts

```python
# Save as HTML
fig.write_html('chart.html')

# Save as image (requires kaleido)
fig.write_image('chart.png')
fig.write_image('chart.jpg')
fig.write_image('chart.pdf')

# Save as JSON
fig.write_json('chart.json')
```

### Customizing Charts

```python
# Update layout
fig.update_layout(
    title='Custom Title',
    showlegend=False,
    height=600,
    template='plotly_dark'
)

# Update traces
fig.update_traces(
    marker=dict(size=12),
    line=dict(width=3)
)

# Add annotations
fig.add_annotation(
    text="Important event",
    x="2024-01-15",
    y=100,
    showarrow=True
)
```

## Styling

### Custom CSS

Dashboard styles are defined in `src/static/css/dashboard.css`.

Key customization areas:
- Color scheme
- Layout dimensions
- Responsive breakpoints
- Component styles

### Color Scheme

The default color scheme:
```python
color_scheme = {
    'positive': '#10B981',  # Green
    'neutral': '#6B7280',   # Gray
    'negative': '#EF4444',  # Red
    'primary': '#3B82F6',   # Blue
    'secondary': '#8B5CF6', # Purple
    'accent': '#F59E0B'     # Amber
}
```

Modify in `src/services/visualization_service.py`.

## Performance Optimization

### Caching

Implement caching for expensive queries:

```python
from src.services.cache_service import cache_service

# Cache visualization data
@cache_service.cached(ttl=300)  # 5 minutes
async def get_cached_visualization(days):
    return await visualization_service.get_sentiment_distribution(days)
```

### Data Sampling

For large datasets, use sampling:

```python
# In storage queries
articles = await storage_service.query_articles(
    filters,
    limit=1000,
    sample=True  # Random sampling
)
```

### Async Loading

Charts load independently with loading spinners:
```python
dcc.Loading(
    id='loading-chart',
    children=[dcc.Graph(id='chart')],
    type='circle'
)
```

## Troubleshooting

### Dashboard Not Loading

1. Check Flask app is running
2. Verify `/dashboard/` URL
3. Check browser console for errors
4. Ensure all dependencies installed:
   ```bash
   pip install plotly dash
   ```

### Charts Not Updating

1. Verify data exists in database
2. Check time range selection
3. Review browser console for errors
4. Check API endpoints responding:
   ```bash
   curl http://localhost:5000/api/visualization/health
   ```

### Slow Performance

1. Reduce time range
2. Implement caching
3. Use data sampling
4. Optimize database queries
5. Increase auto-refresh interval

### Styling Issues

1. Clear browser cache
2. Check CSS file loaded
3. Verify static file serving
4. Use browser dev tools

## Advanced Usage

### Custom Visualizations

Create custom visualization functions:

```python
class CustomVisualizationService(VisualizationService):
    async def get_custom_chart(self):
        # Your custom logic
        data = await self.fetch_custom_data()

        fig = go.Figure(data=[
            go.Scatter(x=data['x'], y=data['y'])
        ])

        fig.update_layout(title='Custom Chart')
        return fig
```

### Adding New Charts

1. Add method to `VisualizationService`
2. Add callback to `dash_app.py`
3. Add graph component to layout
4. Create API endpoint (optional)

Example:

```python
# In visualization_service.py
async def get_new_chart(self):
    # Implementation
    pass

# In dash_app.py
@dash_app.callback(
    Output('new-chart', 'figure'),
    Input('time-range-selector', 'value')
)
def update_new_chart(days):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            visualization_service.get_new_chart()
        )
    finally:
        loop.close()
```

### Export Data

Export visualization data for external use:

```python
# Export to CSV
import pandas as pd

data = await storage_service.query_articles(filters)
df = pd.DataFrame([article.to_dict() for article in data])
df.to_csv('export.csv', index=False)

# Export to Excel
df.to_excel('export.xlsx', index=False)

# Export to JSON
df.to_json('export.json', orient='records')
```

## Production Deployment

### Configuration

```python
# config.py
DASH_CONFIG = {
    'suppress_callback_exceptions': False,
    'serve_locally': True,
    'url_base_pathname': '/dashboard/',
    'requests_pathname_prefix': '/dashboard/'
}
```

### Security

1. Enable authentication for dashboard
2. Use HTTPS in production
3. Set CSP headers
4. Rate limit API endpoints (already implemented)

### Scaling

1. Use caching layer (Redis)
2. Implement CDN for static assets
3. Use database read replicas
4. Enable query optimization
5. Consider separate visualization server

## References

- [Plotly Documentation](https://plotly.com/python/)
- [Dash Documentation](https://dash.plotly.com/)
- [Plotly Figure Reference](https://plotly.com/python/reference/)
- [Dash Component Gallery](https://dash.gallery/)
