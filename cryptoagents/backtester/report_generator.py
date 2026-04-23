"""Generate a JSON + Markdown report from backtest results."""

import json
import os
from datetime import datetime


def generate_report(results: dict, symbol: str, start: str, end: str) -> str:
    os.makedirs("reports", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = f"reports/{symbol}_{start}_{end}_{ts}"

    # JSON dump
    json_path = base + ".json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Markdown report
    md_path = base + ".md"
    m = results.get("metrics", {})
    trades = results.get("trades", [])

    lines = [
        f"# Backtest Report — {symbol}",
        f"**Period:** {start} → {end}  ",
        f"**Interval:** {results.get('interval', '1d')}  ",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Initial Capital | ${m.get('initial_capital', 0):,.2f} |",
        f"| Final Capital | ${m.get('final_capital', 0):,.2f} |",
        f"| Total Return | {m.get('total_return_pct', 0):+.2f}% |",
        f"| Sharpe Ratio | {m.get('sharpe_ratio', '—')} |",
        f"| Max Drawdown | {m.get('max_drawdown_pct', 0):.2f}% |",
        f"| Win Rate | {m.get('win_rate_pct', 0):.1f}% |",
        f"| Total Trades | {m.get('total_trades', 0)} |",
        f"| Profit Factor | {m.get('profit_factor', '—')} |",
        "",
        "## Trade Log",
        "| Date | Action | Entry | Exit | Return | P&L |",
        "|------|--------|-------|------|--------|-----|",
    ]

    for t in trades:
        lines.append(
            f"| {str(t.get('timestamp',''))[:10]} "
            f"| {t.get('action','—')} "
            f"| ${t.get('entry_price', 0):,.2f} "
            f"| ${t.get('exit_price', 0):,.2f} "
            f"| {t.get('return_pct', 0):+.2f}% "
            f"| ${t.get('pnl', 0):+,.2f} |"
        )

    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    return md_path
