"""
Historical data interface — serves stored data by date during backtesting.
Falls back to live data for anything not in the DB.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from cryptoagents.dataflows.interface import DataInterface

DB_PATH = "./crypto_history.db"


class HistoricalDataInterface(DataInterface):
    def __init__(self, config: dict = None, db_path: str = DB_PATH, as_of_date: str = None):
        super().__init__(config)
        self.db_path = db_path
        self.as_of_date = as_of_date  # "YYYY-MM-DD" — the current backtest date

    def set_date(self, date: str):
        self.as_of_date = date[:10]

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ── Price ─────────────────────────────────────────────────────────────────

    def get_current_price(self, symbol: str) -> float:
        if not self.as_of_date:
            return super().get_current_price(symbol)
        row = self._query_one(
            "SELECT close FROM ohlcv WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
            (symbol, self.as_of_date)
        )
        return float(row[0]) if row else super().get_current_price(symbol)

    def get_ohlcv(self, symbol: str, interval: str = "1d", limit: int = 100) -> pd.DataFrame:
        if not self.as_of_date:
            return super().get_ohlcv(symbol, interval, limit)
        conn = self._conn()
        df = pd.read_sql(
            "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?",
            conn, params=(symbol, self.as_of_date, limit)
        )
        conn.close()
        if df.empty:
            return super().get_ohlcv(symbol, interval, limit)
        return df.sort_values("timestamp").reset_index(drop=True)

    # ── Technical Indicators ──────────────────────────────────────────────────

    def get_technical_indicators(self, symbol: str) -> dict:
        if not self.as_of_date:
            return super().get_technical_indicators(symbol)
        row = self._query_one(
            "SELECT * FROM technical_indicators WHERE symbol=? AND timestamp<=? "
            "ORDER BY timestamp DESC LIMIT 1",
            (symbol, self.as_of_date)
        )
        if not row:
            return super().get_technical_indicators(symbol)

        cols = ["symbol", "timestamp", "rsi", "macd", "macd_signal", "macd_hist",
                "bb_upper", "bb_lower", "bb_mid", "bb_position", "atr", "atr_pct",
                "obv", "ema20", "ema50", "ema200", "price_vs_ema20", "price_vs_ema50"]
        d = dict(zip(cols, row))
        return {k: v for k, v in d.items() if k not in ("symbol", "timestamp")}

    # ── Fear & Greed ──────────────────────────────────────────────────────────

    def get_fear_greed_index(self) -> dict:
        if not self.as_of_date:
            return super().get_fear_greed_index()
        row = self._query_one(
            "SELECT value, classification FROM fear_greed WHERE timestamp<=? "
            "ORDER BY timestamp DESC LIMIT 1",
            (self.as_of_date,)
        )
        if not row:
            return super().get_fear_greed_index()
        return {"value": row[0], "value_classification": row[1], "timestamp": self.as_of_date}

    # ── Market Data ───────────────────────────────────────────────────────────

    def get_market_data(self, symbol: str) -> dict:
        if not self.as_of_date:
            return super().get_market_data(symbol)
        row = self._query_one(
            "SELECT market_cap, volume_24h, price_change_pct_24h FROM market_data "
            "WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
            (symbol, self.as_of_date)
        )
        if not row:
            return super().get_market_data(symbol)
        return {
            "market_cap": row[0],
            "total_volume": row[1],
            "price_change_percentage_24h": row[2],
        }

    # ── Funding Rate ──────────────────────────────────────────────────────────

    def get_funding_rate(self, symbol: str) -> dict:
        if not self.as_of_date:
            return super().get_funding_rate(symbol)
        row = self._query_one(
            "SELECT rate FROM funding_rate WHERE symbol=? AND timestamp<=? "
            "ORDER BY timestamp DESC LIMIT 1",
            (symbol, self.as_of_date)
        )
        if not row:
            return super().get_funding_rate(symbol)
        return {"symbol": symbol, "fundingRate": row[0], "timestamp": self.as_of_date}

    # ── 24h Stats (derived from OHLCV) ────────────────────────────────────────

    def get_24h_stats(self, symbol: str) -> dict:
        if not self.as_of_date:
            return super().get_24h_stats(symbol)
        row = self._query_one(
            "SELECT open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
            (symbol, self.as_of_date)
        )
        if not row:
            return super().get_24h_stats(symbol)
        open_, high, low, close, volume = row
        change_pct = ((close - open_) / open_ * 100) if open_ else 0
        return {
            "symbol": symbol, "openPrice": open_, "highPrice": high,
            "lowPrice": low, "lastPrice": close, "volume": volume,
            "priceChangePercent": round(change_pct, 2),
        }

    # ── Helper ────────────────────────────────────────────────────────────────

    def _query_one(self, sql: str, params: tuple) -> Optional[tuple]:
        try:
            conn = self._conn()
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            conn.close()
            return row
        except Exception:
            return None
