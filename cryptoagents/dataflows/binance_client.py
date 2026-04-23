import requests
import pandas as pd
from datetime import datetime, timezone
from .cache import get_cache

BASE = "https://api.binance.com"
FAPI = "https://fapi.binance.com"
DAPI = "https://dapi.binance.com"

TTL_REALTIME = 30
TTL_SHORT = 300
TTL_MEDIUM = 3600


def _get(url: str, params: dict = None) -> dict | list:
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> pd.DataFrame:
    cache = get_cache()
    cached = cache.get("ohlcv", symbol=symbol, interval=interval, limit=limit)
    if cached:
        return pd.DataFrame(cached)

    data = _get(f"{BASE}/api/v3/klines", {
        "symbol": symbol, "interval": interval, "limit": limit
    })
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    result = df[["open_time", "open", "high", "low", "close", "volume"]].to_dict("records")
    for r in result:
        r["open_time"] = str(r["open_time"])
    cache.set(result, TTL_SHORT, "ohlcv", symbol=symbol, interval=interval, limit=limit)
    return pd.DataFrame(result)


def get_current_price(symbol: str) -> float:
    cache = get_cache()
    cached = cache.get("price", symbol=symbol)
    if cached:
        return cached

    data = _get(f"{BASE}/api/v3/ticker/price", {"symbol": symbol})
    price = float(data["price"])
    cache.set(price, TTL_REALTIME, "price", symbol=symbol)
    return price


def get_order_book_depth(symbol: str, levels: int = 20) -> dict:
    cache = get_cache()
    cached = cache.get("orderbook", symbol=symbol, levels=levels)
    if cached:
        return cached

    data = _get(f"{BASE}/api/v3/depth", {"symbol": symbol, "limit": levels})
    bids = [[float(p), float(q)] for p, q in data["bids"]]
    asks = [[float(p), float(q)] for p, q in data["asks"]]

    top_bid = bids[0][0] if bids else 0
    top_ask = asks[0][0] if asks else 0
    bid_liquidity = sum(p * q for p, q in bids)
    ask_liquidity = sum(p * q for p, q in asks)

    result = {
        "top_bid": top_bid,
        "top_ask": top_ask,
        "spread": round(top_ask - top_bid, 8),
        "bid_liquidity_usd": round(bid_liquidity, 2),
        "ask_liquidity_usd": round(ask_liquidity, 2),
        "bid_ask_ratio": round(bid_liquidity / ask_liquidity, 3) if ask_liquidity else 0,
    }
    cache.set(result, TTL_REALTIME, "orderbook", symbol=symbol, levels=levels)
    return result


def get_funding_rate(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("funding", symbol=symbol)
    if cached:
        return cached

    try:
        data = _get(f"{FAPI}/fapi/v1/fundingRate", {"symbol": symbol, "limit": 8})
        rates = [float(d["fundingRate"]) for d in data]
        result = {
            "latest_rate": rates[-1] if rates else 0,
            "avg_8period": round(sum(rates) / len(rates), 6) if rates else 0,
            "annualized_pct": round(rates[-1] * 3 * 365 * 100, 2) if rates else 0,
        }
    except Exception:
        result = {"latest_rate": 0, "avg_8period": 0, "annualized_pct": 0, "note": "futures data unavailable"}

    cache.set(result, TTL_SHORT, "funding", symbol=symbol)
    return result


def get_open_interest(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("oi", symbol=symbol)
    if cached:
        return cached

    try:
        data = _get(f"{FAPI}/fapi/v1/openInterest", {"symbol": symbol})
        result = {
            "open_interest": float(data["openInterest"]),
            "timestamp": data["time"],
        }
    except Exception:
        result = {"open_interest": 0, "note": "futures OI unavailable"}

    cache.set(result, TTL_SHORT, "oi", symbol=symbol)
    return result


def get_long_short_ratio(symbol: str, period: str = "1d") -> dict:
    cache = get_cache()
    cached = cache.get("lsr", symbol=symbol, period=period)
    if cached:
        return cached

    try:
        data = _get(f"{FAPI}/futures/data/globalLongShortAccountRatio", {
            "symbol": symbol, "period": period, "limit": 1
        })
        if data:
            result = {
                "long_account_ratio": float(data[0]["longAccount"]),
                "short_account_ratio": float(data[0]["shortAccount"]),
                "ls_ratio": float(data[0]["longShortRatio"]),
            }
        else:
            result = {"note": "no data"}
    except Exception:
        result = {"note": "long/short ratio unavailable"}

    cache.set(result, TTL_SHORT, "lsr", symbol=symbol, period=period)
    return result


def get_24h_stats(symbol: str) -> dict:
    cache = get_cache()
    cached = cache.get("stats24h", symbol=symbol)
    if cached:
        return cached

    data = _get(f"{BASE}/api/v3/ticker/24hr", {"symbol": symbol})
    result = {
        "price_change_pct": float(data["priceChangePercent"]),
        "high": float(data["highPrice"]),
        "low": float(data["lowPrice"]),
        "volume": float(data["volume"]),
        "quote_volume": float(data["quoteVolume"]),
        "trades": int(data["count"]),
    }
    cache.set(result, TTL_SHORT, "stats24h", symbol=symbol)
    return result
