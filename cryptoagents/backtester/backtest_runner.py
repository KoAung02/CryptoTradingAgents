"""
Backtest runner — iterates over historical dates, calls CryptoAgentsGraph
for each candle, simulates trade execution, and returns a results dict.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from cryptoagents.graph.crypto_graph import CryptoAgentsGraph
from cryptoagents.backtester.metrics import compute_metrics

HISTORICAL_DB = "./crypto_history.db"


class BacktestRunner:
    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
        initial_capital: float = 10_000.0,
        config: dict = None,
        debug: bool = False,
    ):
        self.symbol = symbol.upper()
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.initial_capital = initial_capital
        self.config = config or {}
        self.debug = debug
        self.use_historical = os.path.exists(HISTORICAL_DB)

        self._graph = CryptoAgentsGraph(config=self.config, debug=debug)

        if self.use_historical:
            from cryptoagents.dataflows.historical_interface import HistoricalDataInterface
            self._hist_interface = HistoricalDataInterface(config=self.config, db_path=HISTORICAL_DB)
            print(f"[Backtest] Using historical data from {HISTORICAL_DB}")
        else:
            self._hist_interface = None
            print("[Backtest] No historical DB found — using live data (less accurate)")

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self) -> dict:
        timestamps = self._generate_timestamps()
        capital = self.initial_capital
        trades = []
        equity_curve = [{"timestamp": self.start_date, "equity": capital}]

        open_trade: Optional[dict] = None

        for ts in timestamps:
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            date_str = ts.strftime("%Y-%m-%d")

            if self._hist_interface:
                self._hist_interface.set_date(date_str)
                self._graph.config["_historical_interface"] = self._hist_interface

            try:
                state, decision = self._graph.propagate(self.symbol, ts_str)
            except Exception as e:
                if self.debug:
                    print(f"[Backtest] Error at {ts_str}: {e}")
                continue

            action = decision.get("action", "HOLD").upper()
            close_price = self._get_historical_close(date_str)
            entry_price = decision.get("entry") or self._get_price_from_state(state) or close_price
            stop_loss = decision.get("stop_loss")
            take_profit = decision.get("take_profit_1")

            # Enforce minimum stop distance — LLM often sets tight round-number stops
            # that get wiped by normal intraday wicks. Floor: 7% for BTC, 8% for others.
            if stop_loss and entry_price:
                min_stop_pct = 0.07 if "BTC" in self.symbol else 0.08
                floor_stop = entry_price * (1 - min_stop_pct)
                if stop_loss > floor_stop:
                    stop_loss = round(floor_stop, 2)

            # Enforce minimum TP at 2× stop distance (2:1 R:R floor).
            # Prevents LLM from targeting 5% gain while risking 7% loss.
            if entry_price and stop_loss:
                stop_dist = entry_price - stop_loss
                min_tp = entry_price + 2 * stop_dist
                if not take_profit or take_profit < min_tp:
                    take_profit = round(min_tp, 2)
            confidence = decision.get("confidence") or 5
            llm_size = decision.get("position_size_pct") or 5.0
            if confidence >= 8:
                size_pct = max(llm_size, 20.0) / 100
            elif confidence >= 6:
                size_pct = max(llm_size, 10.0) / 100
            else:
                size_pct = min(llm_size, 5.0) / 100

            # Scale up during confirmed bull trends — strong trend overrides LLM conservatism
            trend_mult = self._get_trend_multiplier(date_str)
            size_pct = min(size_pct * trend_mult, 0.25)

            if self.debug:
                print(f"[Backtest] {date_str} | action={action} | price=${close_price} | entry=${entry_price}")

            # Close open trade only on explicit SELL — HOLD means keep current position
            if open_trade and action == "SELL":
                exit_price = close_price or entry_price or open_trade["entry_price"]
                pnl, ret_pct = self._calc_pnl(open_trade, exit_price, capital)
                capital += pnl
                closed = {**open_trade, "exit_price": exit_price, "pnl": pnl,
                          "return_pct": ret_pct, "exit_timestamp": ts_str}
                trades.append(closed)

                # Store in memory
                self._graph.reflect_and_remember(state, {
                    "entry_price": open_trade["entry_price"],
                    "exit_price": exit_price,
                    "lessons_learned": f"Closed at {ts_str} on {action} signal",
                })
                open_trade = None

            # Open new trade on BUY
            just_opened = False
            if action == "BUY" and open_trade is None and entry_price:
                position_value = capital * size_pct
                open_trade = {
                    "timestamp": ts_str,
                    "action": "BUY",
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "position_value": position_value,
                    "size_pct": size_pct,
                    "highest_close": entry_price,
                }
                just_opened = True

            # Check stop/TP for open trade (skip same candle as entry — low precedes close)
            if open_trade and not just_opened:
                current_price = close_price or open_trade["entry_price"]
                daily_low = self._get_historical_low(date_str)

                # Trailing stop: trail 10% below the highest close since entry
                if current_price > open_trade.get("highest_close", 0):
                    open_trade["highest_close"] = current_price
                trail_pct = 0.10 if "BTC" in self.symbol else 0.12
                trail_stop = round(open_trade["highest_close"] * (1 - trail_pct), 2)
                if trail_stop > (open_trade.get("stop_loss") or 0):
                    open_trade["stop_loss"] = trail_stop

                sl = open_trade.get("stop_loss")
                tp = open_trade.get("take_profit")

                hit_stop = sl and (daily_low or current_price) <= sl
                hit_tp = tp and current_price >= tp

                if hit_stop or hit_tp:
                    exit_price = sl if hit_stop else tp
                    pnl, ret_pct = self._calc_pnl(open_trade, exit_price, capital)
                    capital += pnl
                    reason = "Stop Loss" if hit_stop else "Take Profit"
                    closed = {**open_trade, "exit_price": exit_price, "pnl": pnl,
                              "return_pct": ret_pct, "exit_timestamp": ts_str,
                              "exit_reason": reason}
                    trades.append(closed)
                    self._graph.reflect_and_remember(state, {
                        "entry_price": open_trade["entry_price"],
                        "exit_price": exit_price,
                        "lessons_learned": f"Hit {reason} at {ts_str}",
                    })
                    open_trade = None

            equity_curve.append({"timestamp": ts_str, "equity": capital})

        # Force-close any open trade at end using actual last close price
        if open_trade:
            last_price = self._get_historical_close(self.end_date) or open_trade["entry_price"]
            pnl, ret_pct = self._calc_pnl(open_trade, last_price, capital)
            capital += pnl
            trades.append({**open_trade, "exit_price": last_price, "pnl": pnl,
                           "return_pct": ret_pct, "exit_timestamp": timestamps[-1].strftime("%Y-%m-%d"),
                           "exit_reason": "End of backtest"})

        metrics = compute_metrics(trades, self.initial_capital, capital, equity_curve)

        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "interval": self.interval,
            "initial_capital": self.initial_capital,
            "final_capital": capital,
            "trades": trades,
            "equity_curve": equity_curve,
            "metrics": metrics,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _generate_timestamps(self) -> list[datetime]:
        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.end_date, "%Y-%m-%d")

        delta_map = {"1h": timedelta(hours=1), "4h": timedelta(hours=4), "1d": timedelta(days=1)}
        delta = delta_map.get(self.interval, timedelta(days=1))

        timestamps = []
        current = start
        while current <= end:
            timestamps.append(current)
            current += delta
        return timestamps

    def _get_historical_close(self, date_str: str) -> Optional[float]:
        if not self._hist_interface:
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(HISTORICAL_DB)
            row = conn.execute(
                "SELECT close FROM ohlcv WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
                (self.symbol, date_str)
            ).fetchone()
            conn.close()
            return float(row[0]) if row else None
        except Exception:
            return None

    def _get_historical_low(self, date_str: str) -> Optional[float]:
        if not self._hist_interface:
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(HISTORICAL_DB)
            row = conn.execute(
                "SELECT low FROM ohlcv WHERE symbol=? AND timestamp=?",
                (self.symbol, date_str)
            ).fetchone()
            conn.close()
            return float(row[0]) if row else None
        except Exception:
            return None

    def _get_trend_multiplier(self, date_str: str) -> float:
        """Scale position size by recent 20-day trend strength from OHLCV history.
        Strong bull (+15%+) → 2×, mild bull (+5-15%) → 1.5×, flat → 1×, bearish → 0.7×."""
        try:
            import sqlite3
            from datetime import timedelta
            lookback = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=20)).strftime("%Y-%m-%d")
            conn = sqlite3.connect(HISTORICAL_DB)
            rows = conn.execute(
                "SELECT close FROM ohlcv WHERE symbol=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp",
                (self.symbol, lookback, date_str),
            ).fetchall()
            conn.close()
            if len(rows) < 5:
                return 1.0
            trend_pct = (float(rows[-1][0]) - float(rows[0][0])) / float(rows[0][0]) * 100
            if trend_pct >= 15:
                return 2.0
            elif trend_pct >= 5:
                return 1.5
            elif trend_pct >= 0:
                return 1.0
            else:
                return 0.7
        except Exception:
            return 1.0

    def _get_price_from_state(self, state: dict) -> Optional[float]:
        from cryptoagents.agents.utils.report_parser import parse_final_decision
        parsed = parse_final_decision(state.get("trade_proposal", ""))
        return parsed.get("entry")

    def _calc_pnl(self, trade: dict, exit_price: float, capital: float) -> tuple[float, float]:
        entry = trade["entry_price"]
        position_value = trade["position_value"]
        if entry <= 0:
            return 0.0, 0.0
        ret_pct = (exit_price - entry) / entry * 100
        pnl = position_value * (ret_pct / 100)
        return round(pnl, 4), round(ret_pct, 4)
