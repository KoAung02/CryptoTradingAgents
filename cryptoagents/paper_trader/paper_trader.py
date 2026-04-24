from datetime import datetime

from cryptoagents.graph.crypto_graph import CryptoAgentsGraph
from cryptoagents.dataflows.binance_client import get_current_price, get_ohlcv
from cryptoagents.paper_trader.portfolio import (
    load_portfolio, save_portfolio, get_open_position, total_equity,
    PORTFOLIO_FILE,
)
from cryptoagents.paper_trader.decisions import log_decision


class PaperTrader:
    def __init__(self, symbols: list, initial_capital: float = 10000.0, debug: bool = False):
        self.symbols = [s.upper() for s in symbols]
        self.initial_capital = initial_capital
        self.debug = debug
        self.graph = CryptoAgentsGraph(debug=debug)

    def run(self) -> dict:
        portfolio = load_portfolio(PORTFOLIO_FILE, self.initial_capital)
        today = datetime.utcnow()
        today_str = today.strftime("%Y-%m-%d %H:%M:%S")
        date_str = today.strftime("%Y-%m-%d")

        results = {
            "date": date_str,
            "closed_today": [],
            "opened_today": [],
            "held": [],
            "errors": [],
            "states": {},
        }

        # ── Step 1: Fetch live prices ─────────────────────────────────────────
        live_prices = {}
        for symbol in self.symbols:
            try:
                live_prices[symbol] = get_current_price(symbol)
            except Exception as e:
                results["errors"].append(f"{symbol}: price fetch failed ({e})")

        # ── Step 2: Check open positions for stop/TP ──────────────────────────
        positions_to_close = []
        for pos in portfolio["open_positions"]:
            symbol = pos["symbol"]
            price = live_prices.get(symbol)
            if not price:
                continue

            # Update trailing stop
            trail_pct = 0.10 if "BTC" in symbol else 0.12
            if price > pos.get("highest_price", pos["entry_price"]):
                pos["highest_price"] = price
            trail_stop = round(pos["highest_price"] * (1 - trail_pct), 2)
            if trail_stop > (pos.get("stop_loss") or 0):
                pos["stop_loss"] = trail_stop

            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")
            hit_stop = bool(sl and price <= sl)
            hit_tp = bool(tp and price >= tp)

            if hit_stop or hit_tp:
                exit_price = sl if hit_stop else tp
                reason = "Stop Loss" if hit_stop else "Take Profit"
                positions_to_close.append((pos, exit_price, reason))

        for pos, exit_price, reason in positions_to_close:
            ret_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            pnl = pos["position_value"] * (ret_pct / 100)
            portfolio["cash"] += pos["position_value"] + pnl
            closed = {
                **pos,
                "exit_price": round(exit_price, 4),
                "exit_date": today_str,
                "exit_reason": reason,
                "return_pct": round(ret_pct, 4),
                "pnl": round(pnl, 4),
            }
            portfolio["closed_trades"].append(closed)
            portfolio["open_positions"] = [
                p for p in portfolio["open_positions"] if p["symbol"] != pos["symbol"]
            ]
            results["closed_today"].append(closed)
            self.graph.reflect_and_remember({}, {
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "lessons_learned": f"Paper trade closed via {reason}",
            })

        # ── Step 3: Run 13-agent pipeline for each symbol ─────────────────────
        for symbol in self.symbols:
            open_pos = get_open_position(portfolio, symbol)
            price = live_prices.get(symbol)

            try:
                state, decision = self.graph.propagate(symbol, today_str)
                results["states"][symbol] = state
            except Exception as e:
                results["errors"].append(f"{symbol}: pipeline failed ({e})")
                if open_pos:
                    results["held"].append(symbol)
                continue

            action = decision.get("action", "HOLD").upper()

            if open_pos:
                if action == "SELL" and price:
                    ret_pct = (price - open_pos["entry_price"]) / open_pos["entry_price"] * 100
                    pnl = open_pos["position_value"] * (ret_pct / 100)
                    portfolio["cash"] += open_pos["position_value"] + pnl
                    closed = {
                        **open_pos,
                        "exit_price": round(price, 4),
                        "exit_date": today_str,
                        "exit_reason": "Sell Signal",
                        "return_pct": round(ret_pct, 4),
                        "pnl": round(pnl, 4),
                    }
                    portfolio["closed_trades"].append(closed)
                    portfolio["open_positions"] = [
                        p for p in portfolio["open_positions"] if p["symbol"] != symbol
                    ]
                    results["closed_today"].append(closed)
                    log_decision(date_str, symbol, action, price, decision, "closed_sell")
                    self.graph.reflect_and_remember(state, {
                        "entry_price": open_pos["entry_price"],
                        "exit_price": price,
                        "lessons_learned": f"Closed on SELL signal at {today_str}",
                    })
                else:
                    results["held"].append(symbol)
                    log_decision(date_str, symbol, action, price or 0, decision, "already_open")

            elif action != "BUY" and not open_pos:
                log_decision(date_str, symbol, action, price or 0, decision, "held")

            elif action == "BUY" and price:
                entry_price = decision.get("entry") or price
                stop_loss = decision.get("stop_loss")
                take_profit = decision.get("take_profit_1")
                confidence = decision.get("confidence") or 5
                llm_size = decision.get("position_size_pct") or 5.0

                # Confidence-based sizing
                if confidence >= 8:
                    size_pct = max(llm_size, 20.0) / 100
                elif confidence >= 6:
                    size_pct = max(llm_size, 10.0) / 100
                else:
                    size_pct = min(llm_size, 5.0) / 100

                # Trend multiplier
                trend_mult = self._get_trend_multiplier(symbol)
                size_pct = min(size_pct * trend_mult, 0.25)

                # Enforce minimum stop distance
                if stop_loss and entry_price:
                    min_stop_pct = 0.07 if "BTC" in symbol else 0.08
                    floor_stop = entry_price * (1 - min_stop_pct)
                    if stop_loss > floor_stop:
                        stop_loss = round(floor_stop, 2)

                # Enforce minimum TP (2:1 R:R)
                if entry_price and stop_loss:
                    stop_dist = entry_price - stop_loss
                    min_tp = entry_price + 2 * stop_dist
                    if not take_profit or take_profit < min_tp:
                        take_profit = round(min_tp, 2)

                position_value = round(portfolio["cash"] * size_pct, 4)

                if position_value > 0 and portfolio["cash"] >= position_value:
                    portfolio["cash"] = round(portfolio["cash"] - position_value, 4)
                    new_pos = {
                        "symbol": symbol,
                        "action": "BUY",
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "position_value": position_value,
                        "size_pct": round(size_pct, 4),
                        "entry_date": today_str,
                        "highest_price": entry_price,
                    }
                    portfolio["open_positions"].append(new_pos)
                    results["opened_today"].append(new_pos)
                    log_decision(date_str, symbol, action, price, decision, "opened")

        # ── Step 4: Update equity curve and save ──────────────────────────────
        eq = total_equity(portfolio, live_prices)
        portfolio["equity_curve"].append({"date": date_str, "equity": eq})
        portfolio["last_run"] = today_str

        save_portfolio(portfolio)

        results["total_equity"] = eq
        results["cash"] = round(portfolio["cash"], 2)
        results["open_positions"] = portfolio["open_positions"]
        results["live_prices"] = live_prices

        return results

    def _get_trend_multiplier(self, symbol: str) -> float:
        try:
            df = get_ohlcv(symbol, interval="1d", limit=22)
            if len(df) < 5:
                return 1.0
            closes = df["close"].tolist()
            trend_pct = (closes[-1] - closes[0]) / closes[0] * 100
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
