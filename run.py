#!/usr/bin/env python3
"""
News Agent - Main Entry Point
"""

import asyncio
import logging
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import app
from src.config.settings import settings

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('news_agent.log')
        ]
    )

def main():
    """Main entry point."""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Validate settings
        if not settings.validate():
            logger.error("Invalid configuration. Please check your environment variables.")
            logger.error("Required: OPENAI_API_KEY, NEWS_API_KEY")
            sys.exit(1)
        
        logger.info("Starting News Agent application...")
        logger.info(f"Debug mode: {settings.DEBUG}")
        logger.info(f"Log level: {settings.LOG_LEVEL}")
        
        # Run the Flask app
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=settings.DEBUG
        )
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()






