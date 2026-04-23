import requests
from .cache import get_cache

BASE = "https://api.alternative.me"
TTL = 3600


def get_fear_greed_index(limit: int = 7) -> dict:
    cache = get_cache()
    cached = cache.get("fear_greed", limit=limit)
    if cached:
        return cached

    try:
        data = requests.get(f"{BASE}/fng/", params={"limit": limit}, timeout=10).json()
        entries = data.get("data", [])
        latest = entries[0] if entries else {}
        result = {
            "value": int(latest.get("value", 50)),
            "classification": latest.get("value_classification", "Neutral"),
            "timestamp": latest.get("timestamp", ""),
            "history": [
                {"value": int(e["value"]), "classification": e["value_classification"]}
                for e in entries
            ],
        }
    except Exception as e:
        result = {"value": 50, "classification": "Neutral", "error": str(e)}

    cache.set(result, TTL, "fear_greed", limit=limit)
    return result
