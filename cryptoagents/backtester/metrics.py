"""Compute standard trading metrics from a list of closed trades."""

import math
from typing import Optional


def compute_metrics(
    trades: list[dict],
    initial_capital: float,
    final_capital: float,
    equity_curve: list[dict],
) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "initial_capital": round(initial_capital, 2),
            "final_capital": round(final_capital, 2),
            "total_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

    returns = [t["return_pct"] for t in trades if "return_pct" in t]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    total_return_pct = (final_capital - initial_capital) / initial_capital * 100
    win_rate = len(wins) / len(returns) * 100 if returns else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")

    sharpe = _sharpe_ratio(returns)
    max_dd = _max_drawdown(equity_curve)

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "total_return_pct": round(total_return_pct, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else None,
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown_pct": round(max_dd, 2),
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(final_capital, 2),
    }


def _sharpe_ratio(returns: list[float], risk_free: float = 0.0) -> Optional[float]:
    if len(returns) < 2:
        return None
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (mean - risk_free) / std * math.sqrt(252)


def _max_drawdown(equity_curve: list[dict]) -> float:
    if not equity_curve:
        return 0.0
    equities = [e["equity"] for e in equity_curve]
    peak = equities[0]
    max_dd = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd
