import requests
from .cache import get_cache

BASE = "https://api.llama.fi"
TTL = 86400

SYMBOL_TO_PROTOCOL = {
    "ETHUSDT": "ethereum", "BNBUSDT": "bnb-chain", "AVAXUSDT": "avalanche",
    "SOLUSDT": "solana", "MATICUSDT": "polygon", "ARBUSDT": "arbitrum",
    "OPUSDT": "optimism", "NEARUSDT": "near", "APTUSDT": "aptos",
    "UNIUSDT": "uniswap", "LINKUSDT": None, "INJUSDT": None,
}


def get_tvl(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("tvl", symbol=symbol)
    if cached:
        return cached

    protocol = SYMBOL_TO_PROTOCOL.get(symbol.upper())
    if not protocol:
        result = {"tvl_usd": None, "note": "TVL not applicable for this asset"}
        cache.set(result, TTL, "tvl", symbol=symbol)
        return result

    try:
        data = requests.get(f"{BASE}/tvl/{protocol}", timeout=10).json()
        result = {"tvl_usd": float(data) if isinstance(data, (int, float)) else 0}
    except Exception as e:
        result = {"tvl_usd": None, "error": str(e)}

    cache.set(result, TTL, "tvl", symbol=symbol)
    return result


def get_protocol_revenue(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("revenue", symbol=symbol)
    if cached:
        return cached

    protocol = SYMBOL_TO_PROTOCOL.get(symbol.upper())
    if not protocol:
        result = {"revenue_usd_30d": None, "note": "Revenue not applicable"}
        cache.set(result, TTL, "revenue", symbol=symbol)
        return result

    try:
        data = requests.get(f"{BASE}/summary/fees/{protocol}", timeout=10).json()
        result = {
            "revenue_usd_30d": data.get("total30d", 0),
            "revenue_usd_7d": data.get("total7d", 0),
            "revenue_usd_1d": data.get("total1d", 0),
        }
    except Exception as e:
        result = {"revenue_usd_30d": None, "error": str(e)}

    cache.set(result, TTL, "revenue", symbol=symbol)
    return result


def get_chain_tvl_history(symbol: str) -> list:
    cache = get_cache()
    cached = cache.get("tvl_history", symbol=symbol)
    if cached:
        return cached

    protocol = SYMBOL_TO_PROTOCOL.get(symbol.upper())
    if not protocol:
        return []

    try:
        data = requests.get(f"{BASE}/v2/historicalChainTvl/{protocol}", timeout=10).json()
        result = [{"date": d["date"], "tvl": d["tvl"]} for d in data[-30:]]
    except Exception:
        result = []

    cache.set(result, TTL, "tvl_history", symbol=symbol)
    return result
