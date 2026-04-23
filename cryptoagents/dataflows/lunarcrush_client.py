"""
Social sentiment using free sources:
- CryptoPanic for news sentiment signals
- Alternative.me Fear & Greed as sentiment baseline
- Reddit via public JSON API (no auth needed for public subreddits)
"""
import requests
import os
from .cache import get_cache
from .alternative_me_client import get_fear_greed_index

TTL = 3600

SUBREDDITS = {
    "BTCUSDT": "Bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "BNBTrader", "ADAUSDT": "cardano", "XRPUSDT": "XRP",
    "DOGEUSDT": "dogecoin", "AVAXUSDT": "Avax", "LINKUSDT": "LINKTrader",
}

SYMBOL_MAP = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "ADAUSDT": "ADA", "XRPUSDT": "XRP",
    "DOGEUSDT": "DOGE", "AVAXUSDT": "AVAX",
}


def get_social_metrics(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("social_metrics", symbol=symbol)
    if cached:
        return cached

    fng = get_fear_greed_index(limit=1)
    reddit = _reddit_stats(symbol)
    cryptopanic_sentiment = _cryptopanic_sentiment(symbol)

    fng_val = fng.get("value", 50)
    result = {
        "fear_greed_value": fng_val,
        "fear_greed_class": fng.get("classification", "Neutral"),
        "reddit_hot_count": reddit.get("hot_count", 0),
        "reddit_sentiment": reddit.get("sentiment", "NEUTRAL"),
        "news_sentiment": cryptopanic_sentiment,
        "overall_sentiment_score": round((fng_val + reddit.get("score", 50)) / 2, 1),
    }

    cache.set(result, TTL, "social_metrics", symbol=symbol)
    return result


def _reddit_stats(symbol: str) -> dict:
    subreddit = SUBREDDITS.get(symbol.upper(), "CryptoCurrency")
    try:
        headers = {"User-Agent": "CryptoAgents/1.0"}
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": 25},
            headers=headers,
            timeout=10
        )
        posts = r.json().get("data", {}).get("children", [])
        hot_count = len(posts)
        scores = [p["data"].get("score", 0) for p in posts]
        avg_score = sum(scores) / len(scores) if scores else 0
        upvote_ratios = [p["data"].get("upvote_ratio", 0.5) for p in posts]
        avg_ratio = sum(upvote_ratios) / len(upvote_ratios) if upvote_ratios else 0.5
        sentiment = "BULLISH" if avg_ratio > 0.72 else "BEARISH" if avg_ratio < 0.45 else "NEUTRAL"
        return {
            "hot_count": hot_count,
            "avg_post_score": round(avg_score, 0),
            "avg_upvote_ratio": round(avg_ratio, 3),
            "sentiment": sentiment,
            "score": round(avg_ratio * 100, 1),
        }
    except Exception:
        return {"hot_count": 0, "sentiment": "NEUTRAL", "score": 50}


def _cryptopanic_sentiment(symbol: str) -> str:
    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
    ticker = SYMBOL_MAP.get(symbol.upper(), symbol.replace("USDT", ""))
    try:
        params = {"auth_token": api_key, "currencies": ticker, "public": "true"}
        r = requests.get("https://cryptopanic.com/api/v1/posts/", params=params, timeout=10)
        items = r.json().get("results", [])[:10]
        if not items:
            return "NEUTRAL"
        positive = sum(1 for i in items if i.get("votes", {}).get("positive", 0) > i.get("votes", {}).get("negative", 0))
        ratio = positive / len(items)
        return "BULLISH" if ratio > 0.6 else "BEARISH" if ratio < 0.4 else "NEUTRAL"
    except Exception:
        return "NEUTRAL"


def get_social_volume(symbol: str, window: str = "24h") -> dict:
    metrics = get_social_metrics(symbol)
    return {
        "reddit_hot_posts": metrics.get("reddit_hot_count", 0),
        "overall_sentiment": metrics.get("reddit_sentiment", "NEUTRAL"),
        "source": "reddit (free)",
    }


def get_influencer_sentiment(symbol: str) -> dict:
    metrics = get_social_metrics(symbol)
    score = metrics.get("overall_sentiment_score", 50)
    return {
        "sentiment_score": score,
        "interpretation": "BULLISH" if score > 60 else "BEARISH" if score < 40 else "NEUTRAL",
        "source": "fear_greed + reddit composite",
    }


def get_galaxy_score(symbol: str) -> dict:
    metrics = get_social_metrics(symbol)
    score = metrics.get("overall_sentiment_score", 50)
    return {
        "galaxy_score": score,
        "interpretation": "STRONG" if score > 60 else "WEAK" if score < 40 else "AVERAGE",
        "source": "composite free sources",
    }


def get_twitter_sentiment(symbol: str, window: str = "24h") -> dict:
    metrics = get_social_metrics(symbol)
    fng = metrics.get("fear_greed_value", 50)
    bullish = round(fng / 100, 2)
    return {
        "bullish_ratio": bullish,
        "bearish_ratio": round(1 - bullish, 2),
        "proxy_source": "fear_greed_index",
        "note": "Twitter API requires paid access; using Fear & Greed as proxy",
    }


def get_reddit_sentiment(symbol: str, subreddit: str = "") -> dict:
    return _reddit_stats(symbol)


def get_google_trends(symbol: str, window: str = "7d") -> dict:
    return {
        "note": "Google Trends requires pytrends; install with: pip install pytrends",
        "trend_score": 50,
        "direction": "UNKNOWN",
    }
