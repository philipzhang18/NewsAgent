import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import nltk
from textblob import TextBlob
import openai

from ..models.news_models import NewsArticle, SentimentType
from ..config.settings import settings

logger = logging.getLogger(__name__)

class NewsProcessor:
    """Process and analyze news articles."""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self._download_nltk_data()
    
    def _download_nltk_data(self):
        """Download required NLTK data."""
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
        except Exception as e:
            logger.warning(f"Could not download NLTK data: {str(e)}")
    
    async def process_article(self, article: NewsArticle) -> NewsArticle:
        """Process a single news article."""
        try:
            logger.info(f"Processing article: {article.title[:50]}...")
            
            # Basic text processing
            article = self._clean_content(article)
            article = self._extract_metadata(article)
            
            # Content analysis
            if settings.ENABLE_SENTIMENT_ANALYSIS:
                article = await self._analyze_sentiment(article)
            
            if settings.ENABLE_BIAS_DETECTION:
                article = await self._detect_bias(article)
            
            # 5W1H extraction
            article = await self._extract_5w1h(article)
            
            # Generate summary
            article = await self._generate_summary(article)
            
            # Mark as processed
            article.is_processed = True
            
            logger.info(f"Successfully processed article: {article.title[:50]}...")
            return article
            
        except Exception as e:
            logger.error(f"Error processing article {article.id}: {str(e)}")
            return article
    
    def _clean_content(self, article: NewsArticle) -> NewsArticle:
        """Clean and normalize article content."""
        try:
            # Remove extra whitespace
            article.content = re.sub(r'\s+', ' ', article.content.strip())
            article.title = re.sub(r'\s+', ' ', article.title.strip())
            
            # Remove HTML tags if present
            article.content = re.sub(r'<[^>]+>', '', article.content)
            article.title = re.sub(r'<[^>]+>', '', article.title)
            
            # Update word count
            article.word_count = len(article.content.split())
            
            # Calculate reading time (average 200 words per minute)
            article.reading_time = max(1, article.word_count // 200)
            
        except Exception as e:
            logger.warning(f"Error cleaning content: {str(e)}")
        
        return article
    
    def _extract_metadata(self, article: NewsArticle) -> NewsArticle:
        """Extract basic metadata from article."""
        try:
            # Extract tags from content if not already present
            if not article.tags:
                # Simple keyword extraction
                words = article.content.lower().split()
                stop_words = set(nltk.corpus.stopwords.words('english'))
                keywords = [word for word in words if word.isalpha() and word not in stop_words and len(word) > 3]
                
                # Get most common keywords
                from collections import Counter
                word_counts = Counter(keywords)
                article.tags = [word for word, count in word_counts.most_common(5)]
            
            # Extract language if not set
            if not article.language:
                try:
                    blob = TextBlob(article.content)
                    article.language = blob.detect_language()
                except:
                    article.language = 'en'
                    
        except Exception as e:
            logger.warning(f"Error extracting metadata: {str(e)}")
        
        return article
    
    async def _analyze_sentiment(self, article: NewsArticle) -> NewsArticle:
        """Analyze article sentiment using OpenAI."""
        try:
            prompt = f"""
            Analyze the sentiment of the following news article. 
            Return only one word: positive, negative, neutral, or mixed.
            
            Title: {article.title}
            Content: {article.content[:1000]}
            """
            
            response = await self.openai_client.chat.completions.acreate(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            
            sentiment_text = response.choices[0].message.content.strip().lower()
            
            # Map to sentiment type
            sentiment_map = {
                'positive': SentimentType.POSITIVE,
                'negative': SentimentType.NEGATIVE,
                'neutral': SentimentType.NEUTRAL,
                'mixed': SentimentType.MIXED
            }
            
            article.sentiment = sentiment_map.get(sentiment_text, SentimentType.NEUTRAL)
            
            # Calculate sentiment score using TextBlob as backup
            blob = TextBlob(article.content)
            article.sentiment_score = blob.sentiment.polarity
            
        except Exception as e:
            logger.warning(f"Error analyzing sentiment: {str(e)}")
            # Fallback to TextBlob
            try:
                blob = TextBlob(article.content)
                article.sentiment_score = blob.sentiment.polarity
                
                if article.sentiment_score > 0.1:
                    article.sentiment = SentimentType.POSITIVE
                elif article.sentiment_score < -0.1:
                    article.sentiment = SentimentType.NEGATIVE
                else:
                    article.sentiment = SentimentType.NEUTRAL
            except:
                article.sentiment = SentimentType.NEUTRAL
        
        return article
    
    async def _detect_bias(self, article: NewsArticle) -> NewsArticle:
        """Detect potential bias in the article."""
        try:
            prompt = f"""
            Analyze the following news article for potential bias, exaggeration, or unreliable information.
            Return a score from 0.0 (completely unbiased/reliable) to 1.0 (highly biased/unreliable).
            Return only the number.
            
            Title: {article.title}
            Content: {article.content[:1000]}
            """
            
            response = await self.openai_client.chat.completions.acreate(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            
            bias_score = float(response.choices[0].message.content.strip())
            article.bias_score = min(max(bias_score, 0.0), 1.0)
            
            # Calculate credibility score (inverse of bias)
            article.credibility_score = 1.0 - article.bias_score
            
        except Exception as e:
            logger.warning(f"Error detecting bias: {str(e)}")
            article.bias_score = 0.5
            article.credibility_score = 0.5
        
        return article
    
    async def _extract_5w1h(self, article: NewsArticle) -> NewsArticle:
        """Extract 5W1H information from article."""
        try:
            prompt = f"""
            Extract the 5W1H information from this news article:
            - Who: People, organizations, or entities involved
            - What: What happened or what is the main event
            - When: When did it happen (date/time)
            - Where: Where did it happen (location)
            - Why: Why did it happen (reason/cause)
            - How: How did it happen (method/process)
            
            Return in this exact format:
            Who: [names separated by commas]
            What: [description]
            When: [date/time]
            Where: [location]
            Why: [reason]
            How: [method]
            
            Article:
            {article.title}
            {article.content[:1500]}
            """
            
            response = await self.openai_client.chat.completions.acreate(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            lines = result.split('\n')
            for line in lines:
                if line.startswith('Who:'):
                    article.who = [name.strip() for name in line[4:].split(',') if name.strip()]
                elif line.startswith('What:'):
                    article.what = line[5:].strip()
                elif line.startswith('When:'):
                    article.when = self._parse_date(line[5:].strip())
                elif line.startswith('Where:'):
                    article.where = line[6:].strip()
                elif line.startswith('Why:'):
                    article.why = line[4:].strip()
                elif line.startswith('How:'):
                    article.how = line[4:].strip()
                    
        except Exception as e:
            logger.warning(f"Error extracting 5W1H: {str(e)}")
        
        return article
    
    async def _generate_summary(self, article: NewsArticle) -> NewsArticle:
        """Generate a summary of the article."""
        try:
            # Only generate summary for longer articles
            if article.word_count < 100:
                article.summary = article.content
                return article
            
            prompt = f"""
            Create a concise summary of this news article in 2-3 sentences.
            Focus on the key facts and main points.
            
            Article:
            {article.title}
            {article.content[:2000]}
            """
            
            response = await self.openai_client.chat.completions.acreate(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            article.summary = response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning(f"Error generating summary: {str(e)}")
            # Fallback: use first few sentences
            sentences = article.content.split('.')
            article.summary = '. '.join(sentences[:3]) + '.'
        
        return article
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        try:
            # Try common date formats
            date_formats = [
                '%Y-%m-%d',
                '%B %d, %Y',
                '%d %B %Y',
                '%Y/%m/%d',
                '%d/%m/%Y'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return None
        except Exception:
            return None
    
    async def process_batch(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Process a batch of articles."""
        processed_articles = []
        
        for article in articles:
            try:
                processed_article = await self.process_article(article)
                processed_articles.append(processed_article)
            except Exception as e:
                logger.error(f"Error processing article {article.id}: {str(e)}")
                processed_articles.append(article)
        
        return processed_articles






