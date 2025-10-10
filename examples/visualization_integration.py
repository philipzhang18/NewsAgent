"""
Example script demonstrating how to integrate Dash dashboard with Flask app.
"""

from flask import Flask
from src.dash_app import create_dash_app
from src.api.visualization_api import init_visualization_api

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

# Initialize visualization API endpoints
init_visualization_api(app)

# Create and integrate Dash application
dash_app = create_dash_app(app)

# The Dash app is now available at /dashboard/
# Visualization API endpoints are available at /api/visualization/*

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
