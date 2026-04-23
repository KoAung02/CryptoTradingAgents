"""
Central data interface — routes tool calls to the right free data client.
"""
from . import (
    binance_client as binance,
    coingecko_client as coingecko,
    glassnode_client as onchain,
    lunarcrush_client as social,
    santiment_client as santiment,
    cryptopanic_client as news,
    alternative_me_client as fng_client,
    defillama_client as defi,
    messari_client as fundamentals,
)
import pandas as pd


class DataInterface:
    def __init__(self, config: dict = None):
        self.config = config or {}

    # ── Price / Market ────────────────────────────────────────────────────────

    def get_current_price(self, symbol: str) -> float:
        return binance.get_current_price(symbol)

    def get_ohlcv(self, symbol: str, interval: str = "1d", limit: int = 100) -> pd.DataFrame:
        return binance.get_ohlcv(symbol, interval, limit)

    def get_order_book_depth(self, symbol: str, levels: int = 20) -> dict:
        return binance.get_order_book_depth(symbol, levels)

    def get_funding_rate(self, symbol: str) -> dict:
        return binance.get_funding_rate(symbol)

    def get_open_interest(self, symbol: str) -> dict:
        return binance.get_open_interest(symbol)

    def get_long_short_ratio(self, symbol: str) -> dict:
        return binance.get_long_short_ratio(symbol)

    def get_24h_stats(self, symbol: str) -> dict:
        return binance.get_24h_stats(symbol)

    # ── CoinGecko Market ──────────────────────────────────────────────────────

    def get_market_data(self, symbol: str) -> dict:
        return coingecko.get_market_data(symbol)

    def get_global_market(self) -> dict:
        return coingecko.get_global_market()

    def get_trending(self) -> list:
        return coingecko.get_trending()

    # ── Technical Indicators ──────────────────────────────────────────────────

    def get_technical_indicators(self, symbol: str) -> dict:
        import ta
        import numpy as np
        df = self.get_ohlcv(symbol, interval="1d", limit=200)
        if df.empty or len(df) < 30:
            return {"error": "Insufficient OHLCV data"}

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
        macd_obj = ta.trend.MACD(close)
        macd = macd_obj.macd().iloc[-1]
        macd_signal = macd_obj.macd_signal().iloc[-1]
        macd_hist = macd_obj.macd_diff().iloc[-1]
        bb = ta.volatility.BollingerBands(close)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_mid = bb.bollinger_mavg().iloc[-1]
        atr = ta.volatility.AverageTrueRange(high, low, close).average_true_range().iloc[-1]
        obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume().iloc[-1]
        ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]
        ema200 = ta.trend.EMAIndicator(close, window=200).ema_indicator().iloc[-1] if len(df) >= 200 else None

        current_price = float(close.iloc[-1])

        return {
            "rsi": round(float(rsi), 2),
            "macd": round(float(macd), 4),
            "macd_signal": round(float(macd_signal), 4),
            "macd_hist": round(float(macd_hist), 4),
            "bb_upper": round(float(bb_upper), 4),
            "bb_lower": round(float(bb_lower), 4),
            "bb_mid": round(float(bb_mid), 4),
            "bb_position": round((current_price - float(bb_lower)) / (float(bb_upper) - float(bb_lower)), 3),
            "atr": round(float(atr), 4),
            "atr_pct": round(float(atr) / current_price * 100, 2),
            "obv": round(float(obv), 0),
            "ema20": round(float(ema20), 4),
            "ema50": round(float(ema50), 4),
            "ema200": round(float(ema200), 4) if ema200 else None,
            "price_vs_ema20": round((current_price - float(ema20)) / float(ema20) * 100, 2),
            "price_vs_ema50": round((current_price - float(ema50)) / float(ema50) * 100, 2),
        }

    def get_volume_profile(self, symbol: str, window: int = 30) -> dict:
        df = self.get_ohlcv(symbol, interval="1d", limit=window)
        if df.empty:
            return {}
        close = df["close"].astype(float)
        volume = df["volume"].astype(float)
        avg_vol = volume.mean()
        recent_vol = volume.iloc[-5:].mean()
        return {
            "avg_volume_30d": round(float(avg_vol), 0),
            "recent_5d_avg": round(float(recent_vol), 0),
            "volume_trend": "INCREASING" if recent_vol > avg_vol * 1.1 else "DECREASING" if recent_vol < avg_vol * 0.9 else "STABLE",
            "high_30d": round(float(close.max()), 4),
            "low_30d": round(float(close.min()), 4),
        }

    def get_liquidation_heatmap(self, symbol: str) -> dict:
        stats = binance.get_24h_stats(symbol)
        price = self.get_current_price(symbol)
        return {
            "note": "Liquidation heatmap requires paid data; using price-derived estimates",
            "current_price": price,
            "24h_high": stats.get("high", 0),
            "24h_low": stats.get("low", 0),
            "estimated_long_liq_zone": round(price * 0.93, 2),
            "estimated_short_liq_zone": round(price * 1.07, 2),
        }

    # ── On-Chain ──────────────────────────────────────────────────────────────

    def get_active_addresses(self, symbol: str, window: str = "24h") -> dict:
        return onchain.get_active_addresses(symbol, window)

    def get_exchange_netflow(self, symbol: str, window: str = "24h") -> dict:
        return onchain.get_exchange_netflow(symbol, window)

    def get_whale_transactions(self, symbol: str, threshold_usd: float = 1_000_000) -> dict:
        return onchain.get_whale_transactions(symbol, threshold_usd)

    def get_miner_outflow(self, symbol: str) -> dict:
        return onchain.get_miner_outflow(symbol)

    def get_nvt_ratio(self, symbol: str) -> dict:
        return onchain.get_nvt_ratio(symbol)

    def get_sopr(self, symbol: str) -> dict:
        return onchain.get_sopr(symbol)

    def get_stablecoin_supply_ratio(self, symbol: str) -> dict:
        return onchain.get_stablecoin_supply_ratio(symbol)

    def get_token_unlocks(self, symbol: str, days_ahead: int = 30) -> dict:
        return onchain.get_token_unlocks(symbol, days_ahead)

    # ── DeFi ──────────────────────────────────────────────────────────────────

    def get_tvl(self, symbol: str) -> dict:
        return defi.get_tvl(symbol)

    def get_protocol_revenue(self, symbol: str, window: str = "30d") -> dict:
        return defi.get_protocol_revenue(symbol)

    # ── Social / Sentiment ────────────────────────────────────────────────────

    def get_fear_greed_index(self) -> dict:
        return fng_client.get_fear_greed_index()

    def get_social_volume(self, symbol: str, window: str = "24h") -> dict:
        return social.get_social_volume(symbol, window)

    def get_social_dominance(self, symbol: str) -> dict:
        return social.get_social_metrics(symbol)

    def get_twitter_sentiment(self, symbol: str, window: str = "24h") -> dict:
        return social.get_twitter_sentiment(symbol, window)

    def get_reddit_sentiment(self, symbol: str, subreddit: str = "") -> dict:
        return social.get_reddit_sentiment(symbol, subreddit)

    def get_influencer_sentiment(self, symbol: str) -> dict:
        return social.get_influencer_sentiment(symbol)

    def get_galaxy_score(self, symbol: str) -> dict:
        return social.get_galaxy_score(symbol)

    def get_google_trends(self, symbol: str, window: str = "7d") -> dict:
        return social.get_google_trends(symbol, window)

    def get_github_activity(self, symbol: str) -> dict:
        return santiment.get_github_activity(symbol)

    # ── News ──────────────────────────────────────────────────────────────────

    def get_crypto_news(self, symbol: str, limit: int = 10, days_back: int = 3) -> list:
        return news.get_crypto_news(symbol, limit, days_back)

    def get_narrative_trends(self) -> list:
        return news.get_narrative_trends()

    def get_macro_events(self, days_ahead: int = 14) -> list:
        return _mock_macro_events()

    def get_regulatory_news(self, region: str = "US") -> list:
        return _mock_regulatory_news()

    def get_protocol_events(self, symbol: str, days_ahead: int = 30) -> list:
        return []

    def get_exchange_listings(self, symbol: str, days_back: int = 30) -> list:
        return []

    def get_hack_or_exploit_news(self, days_back: int = 30) -> list:
        return []

    # ── Fundamentals ──────────────────────────────────────────────────────────

    def get_asset_metrics(self, symbol: str) -> dict:
        return fundamentals.get_asset_metrics(symbol)

    def get_portfolio_state(self) -> dict:
        return {
            "available_capital_usd": 10000.0,
            "open_positions": [],
            "total_portfolio_value_usd": 10000.0,
            "portfolio_heat_pct": 0.0,
            "note": "Paper trading mode — connect to exchange for live data",
        }


def _mock_macro_events() -> list:
    return [
        {"event": "FOMC Meeting", "date": "upcoming", "impact": "HIGH", "note": "Watch for rate guidance"},
        {"event": "US CPI Release", "date": "upcoming", "impact": "MEDIUM"},
        {"event": "US Jobs Report (NFP)", "date": "upcoming", "impact": "MEDIUM"},
    ]


def _mock_regulatory_news() -> list:
    return [
        {"region": "US", "event": "SEC ongoing crypto enforcement actions", "sentiment": "NEGATIVE"},
        {"region": "EU", "event": "MiCA regulations in effect", "sentiment": "NEUTRAL"},
        {"region": "ASIA", "event": "Hong Kong crypto licensing expanding", "sentiment": "POSITIVE"},
    ]
