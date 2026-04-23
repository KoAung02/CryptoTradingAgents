"""
Fundamentals using CoinGecko (free) as the data source.
CoinGecko covers market data, supply, developer activity for most assets.
"""
from .cache import get_cache
from .coingecko_client import get_market_data, get_price_history


def get_asset_metrics(symbol: str) -> dict:
    market = get_market_data(symbol)
    history = get_price_history(symbol, days=30)

    prices = [p[1] for p in history.get("prices", [])]
    roi_30d = 0.0
    if len(prices) >= 2:
        roi_30d = round((prices[-1] - prices[0]) / prices[0] * 100, 2)

    return {
        "market_cap_usd": market.get("market_cap_usd", 0),
        "market_cap_rank": market.get("market_cap_rank", 0),
        "circulating_supply": market.get("circulating_supply", 0),
        "total_supply": market.get("total_supply", 0),
        "max_supply": market.get("max_supply"),
        "ath_usd": market.get("ath_usd", 0),
        "ath_change_pct": market.get("ath_change_pct", 0),
        "roi_30d_pct": roi_30d,
        "price_change_7d_pct": market.get("price_change_7d_pct", 0),
        "source": "coingecko (free)",
    }


def get_protocol_revenue(symbol: str, window: str = "30d") -> dict:
    from .defillama_client import get_protocol_revenue as defillama_revenue
    return defillama_revenue(symbol)
