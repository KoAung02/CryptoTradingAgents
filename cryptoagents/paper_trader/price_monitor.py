"""
Background price monitor — checks open positions every 15 minutes.
No LLM calls, no API keys needed. Uses free Binance public API only.

Run once and leave it in the background:
    python -m cryptoagents.paper_trader.price_monitor
"""

import time
import logging
from datetime import datetime

from cryptoagents.dataflows.binance_client import get_current_price
from cryptoagents.paper_trader.portfolio import (
    load_portfolio, save_portfolio, PORTFOLIO_FILE,
)

CHECK_INTERVAL_SECONDS = 900  # 15 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Monitor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def check_positions() -> list[dict]:
    """Check all open positions against live prices. Close any that hit stop/TP."""
    portfolio = load_portfolio(PORTFOLIO_FILE)
    closed = []

    if not portfolio["open_positions"]:
        return closed

    for pos in list(portfolio["open_positions"]):
        symbol = pos["symbol"]
        try:
            price = get_current_price(symbol)
        except Exception as e:
            log.warning(f"{symbol}: could not fetch price — {e}")
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
            ret_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            pnl = pos["position_value"] * (ret_pct / 100)

            portfolio["cash"] += pos["position_value"] + pnl
            portfolio["open_positions"] = [
                p for p in portfolio["open_positions"] if p["symbol"] != symbol
            ]

            trade = {
                **pos,
                "exit_price": round(exit_price, 4),
                "exit_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "exit_reason": reason,
                "return_pct": round(ret_pct, 4),
                "pnl": round(pnl, 4),
            }
            portfolio["closed_trades"].append(trade)
            closed.append(trade)

            log.info(
                f"CLOSED {symbol} via {reason} | "
                f"Entry ${pos['entry_price']:,.2f} → Exit ${exit_price:,.2f} | "
                f"{ret_pct:+.2f}% | P&L ${pnl:+,.2f}"
            )
        else:
            sl_str = f"${sl:,.2f}" if sl else "—"
            tp_str = f"${tp:,.2f}" if tp else "—"
            log.info(
                f"{symbol} @ ${price:,.2f} | "
                f"SL {sl_str} | TP {tp_str} | "
                f"Trail high ${pos.get('highest_price', pos['entry_price']):,.2f}"
            )

    save_portfolio(portfolio)
    return closed


def run_monitor():
    log.info("Price monitor started — checking every 15 minutes. Press Ctrl+C to stop.")

    while True:
        try:
            portfolio = load_portfolio(PORTFOLIO_FILE)
            n = len(portfolio["open_positions"])

            if n == 0:
                log.info("No open positions — sleeping.")
            else:
                log.info(f"Checking {n} open position(s)...")
                closed = check_positions()
                if closed:
                    log.info(f"{len(closed)} position(s) closed this check.")

        except Exception as e:
            log.error(f"Unexpected error during check: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_monitor()
