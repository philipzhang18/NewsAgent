"""Per-source collection diagnostics and improvement hints."""

from typing import Any, Dict, List

IMPROVEMENT_HINTS = {
    "rss_feed_unreachable": (
        "RSS feed URL unreachable or returned non-200. "
        "Verify URL in sources_config.json; try opening the feed in a browser."
    ),
    "rss_parse_empty": (
        "Feed parsed but returned zero entries. The feed may be empty or use an unsupported format."
    ),
    "newsapi_key_missing": (
        "Set NEWS_API_KEY in .env. Get a key at https://newsapi.org/register"
    ),
    "newsapi_key_invalid": (
        "NewsAPI rejected the API key (401). Check NEWS_API_KEY in .env."
    ),
    "newsapi_rate_limit": (
        "NewsAPI rate limit exceeded (free tier: 100 req/day dev). Wait or upgrade plan."
    ),
    "guardian_key_missing": (
        "Set GUARDIAN_API_KEY in .env. Get a key at https://open-platform.theguardian.com/access/"
    ),
    "nytimes_key_missing": (
        "Set NYTIMES_API_KEY in .env. Get a key at https://developer.nytimes.com/get-started"
    ),
    "api_auth_failed": (
        "API authentication failed. Check the API key in .env is correct and not expired."
    ),
    "api_rate_limit": (
        "API rate limit exceeded. Reduce collection frequency or upgrade API tier."
    ),
    "api_no_results": (
        "API returned zero results. Try broadening the search query or check date range."
    ),
    "reddit_credentials_missing": (
        "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT in .env. "
        "Create app at https://www.reddit.com/prefs/apps"
    ),
    "reddit_auth_failed": (
        "Reddit authentication failed. Verify client id/secret and user agent string."
    ),
    "source_disabled": (
        "Source is marked inactive. Enable it in Sources UI or sources_config.json."
    ),
    "network_error": (
        "Network timeout or connection error. Check internet, firewall, and proxy settings."
    ),
}


def build_diagnostic(
    source_name: str,
    source_type: str,
    success: bool,
    articles_count: int = 0,
    error: str = None,
    hint_key: str = None,
    response_ms: float = None,
    extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    hint = IMPROVEMENT_HINTS.get(hint_key, "") if hint_key else ""
    if error and not hint:
        hint = IMPROVEMENT_HINTS.get("network_error", "")
    return {
        "source_name": source_name,
        "source_type": source_type,
        "success": success,
        "articles_collected": articles_count,
        "error": error,
        "improvement": hint,
        "response_ms": round(response_ms, 1) if response_ms else None,
        **(extra or {}),
    }
