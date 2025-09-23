from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceType(Enum):
	RSS = "rss"
	API = "api"
	WEB_SCRAPING = "web_scraping"
	SOCIAL_MEDIA = "social_media"
	TWITTER = "twitter"
	REDDIT = "reddit"


class SentimentType(Enum):
	POSITIVE = "positive"
	NEGATIVE = "negative"
	NEUTRAL = "neutral"
	MIXED = "mixed"


@dataclass
class NewsArticle:
	id: str
	title: str
	content: str
	summary: Optional[str] = None
	url: str = ""
	source_name: str = ""
	source_type: SourceType = SourceType.API
	published_at: Optional[datetime] = None
	collected_at: datetime = field(default_factory=datetime.utcnow)
	language: str = "en"
	category: Optional[str] = None
	tags: List[str] = field(default_factory=list)
	sentiment: Optional[SentimentType] = None
	sentiment_score: Optional[float] = None
	bias_score: Optional[float] = None
	credibility_score: Optional[float] = None
	who: List[str] = field(default_factory=list)
	what: Optional[str] = None
	when: Optional[datetime] = None
	where: Optional[str] = None
	why: Optional[str] = None
	how: Optional[str] = None
	word_count: int = 0
	reading_time: Optional[int] = None
	image_urls: List[str] = field(default_factory=list)
	video_urls: List[str] = field(default_factory=list)
	is_processed: bool = False
	is_verified: bool = False
	is_duplicate: bool = False

	def to_dict(self) -> Dict[str, Any]:
		return {
			"id": self.id,
			"title": self.title,
			"content": self.content,
			"summary": self.summary,
			"url": self.url,
			"source_name": self.source_name,
			"source_type": self.source_type.value,
			"published_at": self.published_at.isoformat() if self.published_at else None,
			"collected_at": self.collected_at.isoformat(),
			"language": self.language,
			"category": self.category,
			"tags": self.tags,
			"sentiment": self.sentiment.value if self.sentiment else None,
			"sentiment_score": self.sentiment_score,
			"bias_score": self.bias_score,
			"credibility_score": self.credibility_score,
			"who": self.who,
			"what": self.what,
			"when": self.when.isoformat() if self.when else None,
			"where": self.where,
			"why": self.why,
			"how": self.how,
			"word_count": self.word_count,
			"reading_time": self.reading_time,
			"image_urls": self.image_urls,
			"video_urls": self.video_urls,
			"is_processed": self.is_processed,
			"is_verified": self.is_verified,
			"is_duplicate": self.is_duplicate,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "NewsArticle":
		data = dict(data)
		if data.get("published_at"):
			data["published_at"] = datetime.fromisoformat(data["published_at"])  # type: ignore[arg-type]
		if data.get("when"):
			data["when"] = datetime.fromisoformat(data["when"])  # type: ignore[arg-type]
		if data.get("collected_at"):
			data["collected_at"] = datetime.fromisoformat(data["collected_at"])  # type: ignore[arg-type]
		if data.get("source_type") and isinstance(data["source_type"], str):
			data["source_type"] = SourceType(data["source_type"])  # type: ignore[arg-type]
		if data.get("sentiment") and isinstance(data["sentiment"], str):
			data["sentiment"] = SentimentType(data["sentiment"])  # type: ignore[arg-type]
		return cls(**data)  # type: ignore[arg-type]


@dataclass
class NewsSource:
	name: str
	url: str
	source_type: SourceType
	is_active: bool = True
	last_collected: Optional[datetime] = None
	collection_interval: int = 300
	max_articles: int = 100
	categories: List[str] = field(default_factory=list)
	language: str = "en"
	country: Optional[str] = None

	def to_dict(self) -> Dict[str, Any]:
		return {
			"name": self.name,
			"url": self.url,
			"source_type": self.source_type.value,
			"is_active": self.is_active,
			"last_collected": self.last_collected.isoformat() if self.last_collected else None,
			"collection_interval": self.collection_interval,
			"max_articles": self.max_articles,
			"categories": self.categories,
			"language": self.language,
			"country": self.country,
		}


@dataclass
class NewsCollection:
	id: str
	source_name: str
	collected_at: datetime = field(default_factory=datetime.utcnow)
	articles: List[NewsArticle] = field(default_factory=list)
	total_articles: int = 0
	successful_articles: int = 0
	failed_articles: int = 0
	processing_time: Optional[float] = None

	def to_dict(self) -> Dict[str, Any]:
		return {
			"id": self.id,
			"source_name": self.source_name,
			"collected_at": self.collected_at.isoformat(),
			"articles": [a.to_dict() for a in self.articles],
			"total_articles": self.total_articles,
			"successful_articles": self.successful_articles,
			"failed_articles": self.failed_articles,
			"processing_time": self.processing_time,
		}
