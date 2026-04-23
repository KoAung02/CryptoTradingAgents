import os
import requests
from .cache import get_cache

BASE = "https://api.coingecko.com/api/v3"
TTL_SHORT = 300
TTL_MEDIUM = 3600
TTL_LONG = 21600

SYMBOL_TO_ID = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "ADAUSDT": "cardano", "XRPUSDT": "ripple",
    "DOTUSDT": "polkadot", "DOGEUSDT": "dogecoin", "AVAXUSDT": "avalanche-2",
    "MATICUSDT": "matic-network", "LINKUSDT": "chainlink", "UNIUSDT": "uniswap",
    "LTCUSDT": "litecoin", "ATOMUSDT": "cosmos", "NEARUSDT": "near",
    "ARBUSDT": "arbitrum", "OPUSDT": "optimism", "INJUSDT": "injective-protocol",
    "SUIUSDT": "sui", "APTUSDT": "aptos",
}


def _coin_id(symbol: str) -> str:
    return SYMBOL_TO_ID.get(symbol.upper(), symbol.lower().replace("usdt", ""))


def _get(path: str, params: dict = None) -> dict | list:
    api_key = os.getenv("COINGECKO_API_KEY", "")
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}
    r = requests.get(f"{BASE}{path}", params=params, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def get_market_data(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("cg_market", symbol=symbol)
    if cached:
        return cached

    coin_id = _coin_id(symbol)
    try:
        data = _get(f"/coins/{coin_id}", params={
            "localization": "false", "tickers": "false",
            "market_data": "true", "community_data": "false",
            "developer_data": "false"
        })
        md = data["market_data"]
        result = {
            "current_price_usd": md["current_price"].get("usd", 0),
            "market_cap_usd": md["market_cap"].get("usd", 0),
            "market_cap_rank": data.get("market_cap_rank", 0),
            "total_volume_usd": md["total_volume"].get("usd", 0),
            "price_change_24h_pct": md.get("price_change_percentage_24h", 0),
            "price_change_7d_pct": md.get("price_change_percentage_7d", 0),
            "price_change_30d_pct": md.get("price_change_percentage_30d", 0),
            "ath_usd": md["ath"].get("usd", 0),
            "ath_change_pct": md.get("ath_change_percentage", {}).get("usd", 0),
            "circulating_supply": md.get("circulating_supply", 0),
            "total_supply": md.get("total_supply", 0),
            "max_supply": md.get("max_supply"),
        }
    except Exception as e:
        result = {"error": str(e), "symbol": symbol}

    cache.set(result, TTL_SHORT, "cg_market", symbol=symbol)
    return result


def get_price_history(symbol: str, days: int = 30) -> dict:
    cache = get_cache()
    cached = cache.get("cg_history", symbol=symbol, days=days)
    if cached:
        return cached

    coin_id = _coin_id(symbol)
    try:
        data = _get(f"/coins/{coin_id}/market_chart", params={
            "vs_currency": "usd", "days": days
        })
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        result = {
            "prices": [[int(p[0]), float(p[1])] for p in prices[-30:]],
            "volumes": [[int(v[0]), float(v[1])] for v in volumes[-30:]],
            "days": days,
        }
    except Exception as e:
        result = {"error": str(e)}

    cache.set(result, TTL_MEDIUM, "cg_history", symbol=symbol, days=days)
    return result


def get_trending() -> list:
    cache = get_cache()
    cached = cache.get("cg_trending")
    if cached:
        return cached

    try:
        data = _get("/search/trending")
        result = [
            {
                "name": c["item"]["name"],
                "symbol": c["item"]["symbol"],
                "rank": c["item"].get("market_cap_rank", 0),
            }
            for c in data.get("coins", [])[:7]
        ]
    except Exception:
        result = []

    cache.set(result, TTL_MEDIUM, "cg_trending")
    return result


def get_global_market() -> dict:
    cache = get_cache()
    cached = cache.get("cg_global")
    if cached:
        return cached

    try:
        data = _get("/global")["data"]
        result = {
            "total_market_cap_usd": data["total_market_cap"].get("usd", 0),
            "total_volume_24h_usd": data["total_volume"].get("usd", 0),
            "btc_dominance_pct": round(data.get("market_cap_percentage", {}).get("btc", 0), 2),
            "eth_dominance_pct": round(data.get("market_cap_percentage", {}).get("eth", 0), 2),
            "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd", 0),
            "active_cryptocurrencies": data.get("active_cryptocurrencies", 0),
        }
    except Exception as e:
        result = {"error": str(e)}

    cache.set(result, TTL_MEDIUM, "cg_global")
    return result
