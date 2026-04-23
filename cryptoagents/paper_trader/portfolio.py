import json
import os
from typing import Optional

PORTFOLIO_FILE = "./paper_portfolio.json"


def load_portfolio(path: str = PORTFOLIO_FILE, initial_capital: float = 10000.0) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {
        "initial_capital": initial_capital,
        "cash": initial_capital,
        "open_positions": [],
        "closed_trades": [],
        "equity_curve": [],
        "last_run": None,
    }


def save_portfolio(portfolio: dict, path: str = PORTFOLIO_FILE) -> None:
    with open(path, "w") as f:
        json.dump(portfolio, f, indent=2, default=str)


def get_open_position(portfolio: dict, symbol: str) -> Optional[dict]:
    for pos in portfolio["open_positions"]:
        if pos["symbol"] == symbol:
            return pos
    return None


def total_equity(portfolio: dict, live_prices: dict) -> float:
    equity = portfolio["cash"]
    for pos in portfolio["open_positions"]:
        price = live_prices.get(pos["symbol"], pos["entry_price"])
        ret = (price - pos["entry_price"]) / pos["entry_price"]
        equity += pos["position_value"] * (1 + ret)
    return round(equity, 2)


def compute_summary(portfolio: dict, live_prices: dict) -> dict:
    eq = total_equity(portfolio, live_prices)
    initial = portfolio["initial_capital"]
    closed = portfolio["closed_trades"]
    wins = [t for t in closed if t.get("pnl", 0) > 0]
    losses = [t for t in closed if t.get("pnl", 0) <= 0]
    total_pnl = sum(t.get("pnl", 0) for t in closed)

    return {
        "initial_capital": initial,
        "current_equity": eq,
        "cash": round(portfolio["cash"], 2),
        "total_return_pct": round((eq - initial) / initial * 100, 2),
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(closed),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
        "open_positions": len(portfolio["open_positions"]),
        "last_run": portfolio.get("last_run"),
    }
