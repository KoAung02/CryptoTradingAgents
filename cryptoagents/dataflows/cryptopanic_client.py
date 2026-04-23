import os
import requests
from .cache import get_cache

BASE = "https://cryptopanic.com/api/v1"
TTL = 3600

SYMBOL_MAP = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "ADAUSDT": "ADA", "XRPUSDT": "XRP",
    "DOTUSDT": "DOT", "DOGEUSDT": "DOGE", "AVAXUSDT": "AVAX",
    "LINKUSDT": "LINK", "UNIUSDT": "UNI", "ARBUSDT": "ARB",
    "OPUSDT": "OP", "NEARUSDT": "NEAR", "INJUSDT": "INJ",
}


def get_crypto_news(symbol: str, limit: int = 10, days_back: int = 3) -> list:
    cache = get_cache()
    cached = cache.get("news", symbol=symbol, limit=limit)
    if cached:
        return cached

    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
    ticker = SYMBOL_MAP.get(symbol.upper(), symbol.replace("USDT", ""))

    params = {
        "auth_token": api_key,
        "currencies": ticker,
        "public": "true",
        "filter": "important",
        "kind": "news",
    }

    try:
        r = requests.get(f"{BASE}/posts/", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results_raw = data.get("results", [])[:limit]
        result = [
            {
                "title": item.get("title", ""),
                "published_at": item.get("published_at", ""),
                "source": item.get("source", {}).get("title", ""),
                "url": item.get("url", ""),
                "votes": item.get("votes", {}),
            }
            for item in results_raw
        ]
    except Exception:
        result = _mock_news(ticker)

    cache.set(result, TTL, "news", symbol=symbol, limit=limit)
    return result


def _mock_news(ticker: str) -> list:
    return [
        {
            "title": f"{ticker} sees increased institutional interest amid market uncertainty",
            "published_at": "2025-01-01T00:00:00Z",
            "source": "CoinDesk",
            "url": "",
            "votes": {"positive": 12, "negative": 2},
        },
        {
            "title": f"Analysts divided on {ticker} short-term outlook",
            "published_at": "2025-01-01T00:00:00Z",
            "source": "CoinTelegraph",
            "url": "",
            "votes": {"positive": 5, "negative": 5},
        },
    ]


def get_narrative_trends() -> list:
    cache = get_cache()
    cached = cache.get("narratives")
    if cached:
        return cached

    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
    params = {"auth_token": api_key, "public": "true", "filter": "trending", "kind": "news"}

    try:
        r = requests.get(f"{BASE}/posts/", params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("results", [])[:5]
        result = [{"title": i.get("title", ""), "source": i.get("source", {}).get("title", "")} for i in items]
    except Exception:
        result = [
            {"title": "AI tokens continue momentum amid ChatGPT rivalry narratives", "source": "mock"},
            {"title": "Real World Assets (RWA) tokenization gaining traction", "source": "mock"},
            {"title": "Layer 2 scaling solutions see record TVL growth", "source": "mock"},
        ]

    cache.set(result, TTL, "narratives")
    return result
