"""
Downloads and stores historical data to SQLite for use in backtesting.

Usage:
    python -m cryptoagents.dataflows.historical_downloader --symbol BTCUSDT --start 2024-01-01 --end 2024-03-31
"""

import sqlite3
import time
import argparse
from datetime import datetime, timedelta

import requests
import pandas as pd

DB_PATH = "./crypto_history.db"


# ── DB Setup ──────────────────────────────────────────────────────────────────

def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str = DB_PATH):
    conn = get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT, timestamp TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL,
            PRIMARY KEY (symbol, timestamp)
        );
        CREATE TABLE IF NOT EXISTS fear_greed (
            timestamp TEXT PRIMARY KEY,
            value INTEGER, classification TEXT
        );
        CREATE TABLE IF NOT EXISTS market_data (
            symbol TEXT, timestamp TEXT,
            market_cap REAL, volume_24h REAL, price_change_pct_24h REAL,
            circulating_supply REAL,
            PRIMARY KEY (symbol, timestamp)
        );
        CREATE TABLE IF NOT EXISTS funding_rate (
            symbol TEXT, timestamp TEXT, rate REAL,
            PRIMARY KEY (symbol, timestamp)
        );
        CREATE TABLE IF NOT EXISTS technical_indicators (
            symbol TEXT, timestamp TEXT,
            rsi REAL, macd REAL, macd_signal REAL, macd_hist REAL,
            bb_upper REAL, bb_lower REAL, bb_mid REAL, bb_position REAL,
            atr REAL, atr_pct REAL, obv REAL,
            ema20 REAL, ema50 REAL, ema200 REAL,
            price_vs_ema20 REAL, price_vs_ema50 REAL,
            PRIMARY KEY (symbol, timestamp)
        );
    """)
    conn.commit()
    conn.close()


# ── Binance OHLCV ─────────────────────────────────────────────────────────────

def download_ohlcv(symbol: str, start: str, end: str, interval: str = "1d", db_path: str = DB_PATH):
    print(f"[OHLCV] Downloading {symbol} {interval} {start} → {end}")
    start_ms = int(datetime.strptime(start, "%Y-%m-%d").timestamp() * 1000)
    end_ms = int(datetime.strptime(end, "%Y-%m-%d").timestamp() * 1000)

    url = "https://api.binance.com/api/v3/klines"
    all_rows = []
    current_ms = start_ms

    while current_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_ms,
            "endTime": end_ms,
            "limit": 1000,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break

        for row in data:
            ts = datetime.utcfromtimestamp(row[0] / 1000).strftime("%Y-%m-%d")
            all_rows.append((symbol, ts, float(row[1]), float(row[2]), float(row[3]),
                             float(row[4]), float(row[5])))

        current_ms = data[-1][0] + 1
        time.sleep(0.2)

    conn = get_conn(db_path)
    conn.executemany(
        "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?)", all_rows
    )
    conn.commit()
    conn.close()
    print(f"[OHLCV] Saved {len(all_rows)} rows")


# ── Technical Indicators ──────────────────────────────────────────────────────

def compute_and_store_indicators(symbol: str, db_path: str = DB_PATH):
    import ta
    import numpy as np

    print(f"[Indicators] Computing for {symbol}")
    conn = get_conn(db_path)
    df = pd.read_sql(
        "SELECT * FROM ohlcv WHERE symbol=? ORDER BY timestamp",
        conn, params=(symbol,)
    )
    conn.close()

    if df.empty or len(df) < 30:
        print("[Indicators] Not enough data")
        return

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    df["rsi"] = ta.momentum.RSIIndicator(close).rsi()
    macd_obj = ta.trend.MACD(close)
    df["macd"] = macd_obj.macd()
    df["macd_signal"] = macd_obj.macd_signal()
    df["macd_hist"] = macd_obj.macd_diff()
    bb = ta.volatility.BollingerBands(close)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_position"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    atr_obj = ta.volatility.AverageTrueRange(high, low, close)
    df["atr"] = atr_obj.average_true_range()
    df["atr_pct"] = df["atr"] / close * 100
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    df["ema20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(close, window=200).ema_indicator()
    df["price_vs_ema20"] = (close - df["ema20"]) / df["ema20"] * 100
    df["price_vs_ema50"] = (close - df["ema50"]) / df["ema50"] * 100

    rows = []
    for _, row in df.iterrows():
        rows.append((
            symbol, row["timestamp"],
            _safe(row, "rsi"), _safe(row, "macd"), _safe(row, "macd_signal"),
            _safe(row, "macd_hist"), _safe(row, "bb_upper"), _safe(row, "bb_lower"),
            _safe(row, "bb_mid"), _safe(row, "bb_position"), _safe(row, "atr"),
            _safe(row, "atr_pct"), _safe(row, "obv"), _safe(row, "ema20"),
            _safe(row, "ema50"), _safe(row, "ema200"), _safe(row, "price_vs_ema20"),
            _safe(row, "price_vs_ema50"),
        ))

    conn = get_conn(db_path)
    conn.executemany("INSERT OR REPLACE INTO technical_indicators VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"[Indicators] Saved {len(rows)} rows")


def _safe(row, col):
    val = row.get(col)
    if val is None:
        return None
    try:
        import math
        return None if math.isnan(float(val)) else round(float(val), 6)
    except Exception:
        return None


# ── Fear & Greed ──────────────────────────────────────────────────────────────

def download_fear_greed(start: str, end: str, db_path: str = DB_PATH):
    print(f"[F&G] Downloading Fear & Greed {start} → {end}")
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    days = (end_dt - start_dt).days + 30

    url = f"https://api.alternative.me/fng/?limit={days}&format=json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    rows = []
    for entry in data:
        ts = datetime.utcfromtimestamp(int(entry["timestamp"])).strftime("%Y-%m-%d")
        if start <= ts <= end:
            rows.append((ts, int(entry["value"]), entry["value_classification"]))

    conn = get_conn(db_path)
    conn.executemany("INSERT OR REPLACE INTO fear_greed VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"[F&G] Saved {len(rows)} rows")


# ── CoinGecko Market Data ─────────────────────────────────────────────────────

COINGECKO_IDS = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin", "AVAXUSDT": "avalanche-2", "DOTUSDT": "polkadot",
    "MATICUSDT": "matic-network",
}


def download_market_data(symbol: str, start: str, end: str, db_path: str = DB_PATH):
    coin_id = COINGECKO_IDS.get(symbol.upper())
    if not coin_id:
        print(f"[MarketData] No CoinGecko ID for {symbol}, skipping")
        return

    print(f"[MarketData] Downloading {symbol} market data {start} → {end}")
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end, "%Y-%m-%d").timestamp()) + 86400

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {"vs_currency": "usd", "from": start_ts, "to": end_ts}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[MarketData] Error: {e}")
        return

    prices = {datetime.utcfromtimestamp(p[0] / 1000).strftime("%Y-%m-%d"): p[1]
              for p in data.get("prices", [])}
    market_caps = {datetime.utcfromtimestamp(p[0] / 1000).strftime("%Y-%m-%d"): p[1]
                   for p in data.get("market_caps", [])}
    volumes = {datetime.utcfromtimestamp(p[0] / 1000).strftime("%Y-%m-%d"): p[1]
               for p in data.get("total_volumes", [])}

    rows = []
    all_dates = sorted(set(prices) | set(market_caps) | set(volumes))
    prev_price = None
    for date in all_dates:
        price = prices.get(date)
        change = ((price - prev_price) / prev_price * 100) if prev_price and price else 0.0
        rows.append((symbol, date, market_caps.get(date), volumes.get(date), change, None))
        prev_price = price

    conn = get_conn(db_path)
    conn.executemany("INSERT OR REPLACE INTO market_data VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"[MarketData] Saved {len(rows)} rows")
    time.sleep(1.5)  # CoinGecko rate limit


# ── Funding Rate ──────────────────────────────────────────────────────────────

def download_funding_rates(symbol: str, start: str, end: str, db_path: str = DB_PATH):
    print(f"[Funding] Downloading {symbol} funding rates {start} → {end}")
    start_ms = int(datetime.strptime(start, "%Y-%m-%d").timestamp() * 1000)
    end_ms = int(datetime.strptime(end, "%Y-%m-%d").timestamp() * 1000) + 86400000

    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    all_rows = []
    current_ms = start_ms

    while current_ms < end_ms:
        params = {"symbol": symbol, "startTime": current_ms, "endTime": end_ms, "limit": 1000}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Funding] Error: {e}")
            break

        if not data:
            break

        for row in data:
            ts = datetime.utcfromtimestamp(row["fundingTime"] / 1000).strftime("%Y-%m-%d")
            all_rows.append((symbol, ts, float(row["fundingRate"])))

        current_ms = data[-1]["fundingTime"] + 1
        time.sleep(0.2)

    conn = get_conn(db_path)
    conn.executemany("INSERT OR REPLACE INTO funding_rate VALUES (?,?,?)", all_rows)
    conn.commit()
    conn.close()
    print(f"[Funding] Saved {len(all_rows)} rows")


# ── Main ──────────────────────────────────────────────────────────────────────

def download_all(symbol: str, start: str, end: str, db_path: str = DB_PATH):
    init_db(db_path)
    download_ohlcv(symbol, start, end, db_path=db_path)
    compute_and_store_indicators(symbol, db_path=db_path)
    download_fear_greed(start, end, db_path=db_path)
    download_market_data(symbol, start, end, db_path=db_path)
    download_funding_rates(symbol, start, end, db_path=db_path)
    print(f"\n[Done] Historical data saved to {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-03-31")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()
    download_all(args.symbol, args.start, args.end, args.db)
