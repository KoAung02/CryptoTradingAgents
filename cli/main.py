"""
CryptoAgents CLI — interactive Rich interface.

Usage:
    python -m cli.main
    python -m cli.main analyze BTCUSDT
    python -m cli.main backtest BTCUSDT --start 2024-01-01 --end 2024-03-31
"""

import argparse
import sys
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box

console = Console()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _action_color(action: str) -> str:
    return {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(action.upper(), "white")


def _print_decision(decision: dict, symbol: str) -> None:
    action = decision.get("action", "HOLD").upper()
    color = _action_color(action)

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Symbol", symbol)
    table.add_row("Action", f"[{color}]{action}[/{color}]")
    if action != "HOLD":
        if decision.get("entry"):
            table.add_row("Entry", f"${decision['entry']:,.2f}")
        if decision.get("stop_loss"):
            table.add_row("Stop Loss", f"[red]${decision['stop_loss']:,.2f}[/red]")
        if decision.get("take_profit_1"):
            table.add_row("Take Profit 1", f"[green]${decision['take_profit_1']:,.2f}[/green]")
        if decision.get("take_profit_2"):
            table.add_row("Take Profit 2", f"[green]${decision['take_profit_2']:,.2f}[/green]")
        if decision.get("position_size_pct"):
            table.add_row("Position Size", f"{decision['position_size_pct']:.1f}%")
    if decision.get("confidence"):
        table.add_row("Confidence", f"{decision['confidence']}/10")

    console.print(Panel(table, title=f"[bold]Final Decision — {symbol}[/bold]", border_style=color))


def _print_pipeline_summary(state: dict) -> None:
    table = Table(title="Pipeline Summary", box=box.SIMPLE_HEAVY, padding=(0, 1))
    table.add_column("Agent", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Signal / Output", style="white")

    from cryptoagents.agents.utils.report_parser import extract_signal_rating

    agents = [
        ("On-Chain Analyst",    extract_signal_rating(state.get("onchain_report", ""))),
        ("Market Analyst",      extract_signal_rating(state.get("market_report", ""))),
        ("Sentiment Analyst",   extract_signal_rating(state.get("sentiment_report", ""))),
        ("News Analyst",        extract_signal_rating(state.get("news_report", ""))),
        ("Bull Researcher",     f"{len(state.get('bull_arguments', []))} round(s)"),
        ("Bear Researcher",     f"{len(state.get('bear_arguments', []))} round(s)"),
        ("Research Manager",    "Done" if state.get("investment_plan") else "—"),
        ("Trader",              "Done" if state.get("trade_proposal") else "—"),
        ("Aggressive Risk",     f"{len(state.get('aggressive_risk_args', []))} round(s)"),
        ("Conservative Risk",   f"{len(state.get('conservative_risk_args', []))} round(s)"),
        ("Neutral Risk",        f"{len(state.get('neutral_risk_args', []))} round(s)"),
        ("Risk Manager",        "Done" if state.get("risk_assessment") else "—"),
        ("Portfolio Manager",   "Done" if state.get("portfolio_manager_report") else "—"),
    ]

    for name, output in agents:
        status = "[green]✓[/green]" if output and output != "—" else "[dim]—[/dim]"
        table.add_row(name, status, str(output))

    console.print(table)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_analyze(args) -> None:
    symbol = args.symbol.upper()
    timestamp = args.timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    console.print(Panel(
        f"[bold cyan]Symbol:[/bold cyan] {symbol}\n"
        f"[bold cyan]Timestamp:[/bold cyan] {timestamp}",
        title="[bold]CryptoAgents — Analysis[/bold]",
        border_style="blue",
    ))

    from main import CryptoAgents
    ca = CryptoAgents(debug=args.debug)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running 13-agent pipeline...", total=None)
        state, decision = ca.analyze(symbol, timestamp)
        progress.update(task, completed=True)

    _print_pipeline_summary(state)
    _print_decision(decision, symbol)

    if args.show_reports:
        _show_full_reports(state)


def cmd_backtest(args) -> None:
    symbol = args.symbol.upper()
    start = args.start
    end = args.end
    interval = args.interval

    console.print(Panel(
        f"[bold cyan]Symbol:[/bold cyan]   {symbol}\n"
        f"[bold cyan]Period:[/bold cyan]   {start} → {end}\n"
        f"[bold cyan]Interval:[/bold cyan] {interval}",
        title="[bold]CryptoAgents — Backtest[/bold]",
        border_style="magenta",
    ))

    from cryptoagents.backtester.backtest_runner import BacktestRunner

    runner = BacktestRunner(
        symbol=symbol,
        start_date=start,
        end_date=end,
        interval=interval,
        initial_capital=args.capital,
        debug=args.debug,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Running backtest for {symbol}...", total=None)
        results = runner.run()
        progress.update(task, completed=True)

    _print_backtest_results(results, symbol)

    if args.save:
        from cryptoagents.backtester.report_generator import generate_report
        path = generate_report(results, symbol, start, end)
        console.print(f"\n[green]Report saved:[/green] {path}")


def _show_full_reports(state: dict) -> None:
    reports = [
        ("On-Chain Report",        state.get("onchain_report")),
        ("Market Report",          state.get("market_report")),
        ("Sentiment Report",       state.get("sentiment_report")),
        ("News Report",            state.get("news_report")),
        ("Investment Plan",        state.get("investment_plan")),
        ("Trade Proposal",         state.get("trade_proposal")),
        ("Risk Assessment",        state.get("risk_assessment")),
        ("Portfolio Manager",      state.get("portfolio_manager_report")),
    ]
    for title, content in reports:
        if content:
            console.print(Panel(content[:2000], title=f"[bold]{title}[/bold]", border_style="dim"))


def _print_backtest_results(results: dict, symbol: str) -> None:
    m = results.get("metrics", {})

    table = Table(title=f"Backtest Results — {symbol}", box=box.ROUNDED, padding=(0, 1))
    table.add_column("Metric", style="cyan", width=28)
    table.add_column("Value", justify="right")

    def fmt(val, fmt_str=".2f", suffix=""):
        return f"{val:{fmt_str}}{suffix}" if val is not None else "—"

    table.add_row("Total Return",       f"[{'green' if m.get('total_return_pct', 0) >= 0 else 'red'}]{fmt(m.get('total_return_pct'), '.2f', '%')}[/]")
    table.add_row("Sharpe Ratio",       fmt(m.get("sharpe_ratio")))
    table.add_row("Max Drawdown",       f"[red]{fmt(m.get('max_drawdown_pct'), '.2f', '%')}[/red]")
    table.add_row("Win Rate",           fmt(m.get("win_rate_pct"), ".1f", "%"))
    table.add_row("Total Trades",       str(m.get("total_trades", 0)))
    table.add_row("Winning Trades",     str(m.get("winning_trades", 0)))
    table.add_row("Losing Trades",      str(m.get("losing_trades", 0)))
    table.add_row("Avg Win",            fmt(m.get("avg_win_pct"), ".2f", "%"))
    table.add_row("Avg Loss",           fmt(m.get("avg_loss_pct"), ".2f", "%"))
    table.add_row("Profit Factor",      fmt(m.get("profit_factor")))
    table.add_row("Final Capital",      f"${m.get('final_capital', 0):,.2f}")

    console.print(table)

    trades = results.get("trades", [])
    if trades:
        trade_table = Table(title="Trade Log", box=box.SIMPLE, padding=(0, 1))
        trade_table.add_column("Date", style="dim")
        trade_table.add_column("Action", justify="center")
        trade_table.add_column("Entry", justify="right")
        trade_table.add_column("Exit", justify="right")
        trade_table.add_column("Return", justify="right")
        trade_table.add_column("P&L", justify="right")

        for t in trades[-20:]:
            action = t.get("action", "—")
            ret = t.get("return_pct", 0)
            color = "green" if ret >= 0 else "red"
            trade_table.add_row(
                t.get("timestamp", "—")[:10],
                f"[{_action_color(action)}]{action}[/]",
                f"${t.get('entry_price', 0):,.2f}",
                f"${t.get('exit_price', 0):,.2f}" if t.get("exit_price") else "—",
                f"[{color}]{ret:+.2f}%[/]",
                f"[{color}]${t.get('pnl', 0):+,.2f}[/]",
            )

        console.print(trade_table)


# ── Interactive mode ──────────────────────────────────────────────────────────

def interactive_mode() -> None:
    console.print(Panel(
        "[bold cyan]CryptoAgents[/bold cyan] — Multi-Agent Crypto Analysis\n"
        "[dim]Powered by qwen3.5:4b via Ollama[/dim]",
        border_style="cyan",
    ))

    while True:
        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("  [cyan]1[/cyan]  Analyze a coin")
        console.print("  [cyan]2[/cyan]  Run a backtest")
        console.print("  [cyan]3[/cyan]  Exit\n")

        choice = Prompt.ask("Choice", choices=["1", "2", "3"])

        if choice == "1":
            symbol = Prompt.ask("Symbol (e.g. BTCUSDT)").upper()
            use_now = Confirm.ask("Use current time?", default=True)
            if use_now:
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp = Prompt.ask("Timestamp (YYYY-MM-DD HH:MM:SS)")

            from main import CryptoAgents
            ca = CryptoAgents()
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as p:
                p.add_task("Running pipeline...", total=None)
                state, decision = ca.analyze(symbol, timestamp)

            _print_pipeline_summary(state)
            _print_decision(decision, symbol)

            if Confirm.ask("Show full reports?", default=False):
                _show_full_reports(state)

        elif choice == "2":
            symbol = Prompt.ask("Symbol (e.g. BTCUSDT)").upper()
            start = Prompt.ask("Start date (YYYY-MM-DD)", default="2024-01-01")
            end = Prompt.ask("End date (YYYY-MM-DD)", default="2024-03-31")
            interval = Prompt.ask("Interval", default="1d", choices=["1h", "4h", "1d"])
            capital = float(Prompt.ask("Initial capital (USD)", default="10000"))

            from cryptoagents.backtester.backtest_runner import BacktestRunner
            runner = BacktestRunner(symbol=symbol, start_date=start, end_date=end,
                                    interval=interval, initial_capital=capital)
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                p.add_task(f"Backtesting {symbol}...", total=None)
                results = runner.run()

            _print_backtest_results(results, symbol)

            if Confirm.ask("Save report?", default=True):
                from cryptoagents.backtester.report_generator import generate_report
                path = generate_report(results, symbol, start, end)
                console.print(f"[green]Saved:[/green] {path}")

        elif choice == "3":
            console.print("[dim]Goodbye.[/dim]")
            break


# ── Entry point ───────────────────────────────────────────────────────────────

def cmd_paper_trade(args) -> None:
    symbols = [s.upper() for s in args.symbols]

    console.print(Panel(
        f"[bold cyan]Symbols:[/bold cyan]  {', '.join(symbols)}\n"
        f"[bold cyan]Capital:[/bold cyan]  ${args.capital:,.2f}\n"
        f"[bold cyan]Mode:[/bold cyan]     Paper Trading (no real money)",
        title="[bold]CryptoAgents — Paper Trade[/bold]",
        border_style="green",
    ))

    from cryptoagents.paper_trader.paper_trader import PaperTrader

    trader = PaperTrader(symbols=symbols, initial_capital=args.capital, debug=args.debug)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Running 13-agent pipeline for each symbol...", total=None)
        results = trader.run()
        progress.update(task, completed=True)

    _print_paper_results(results)


def cmd_paper_status(args) -> None:
    from cryptoagents.paper_trader.portfolio import load_portfolio, compute_summary
    from cryptoagents.dataflows.binance_client import get_current_price

    portfolio = load_portfolio()
    if not portfolio.get("last_run"):
        console.print("[yellow]No paper trading session found. Run paper-trade first.[/yellow]")
        return

    live_prices = {}
    for pos in portfolio["open_positions"]:
        try:
            live_prices[pos["symbol"]] = get_current_price(pos["symbol"])
        except Exception:
            live_prices[pos["symbol"]] = pos["entry_price"]

    summary = compute_summary(portfolio, live_prices)

    table = Table(title="Paper Portfolio — Status", box=box.ROUNDED, padding=(0, 1))
    table.add_column("Metric", style="cyan", width=24)
    table.add_column("Value", justify="right")

    color = "green" if summary["total_return_pct"] >= 0 else "red"
    table.add_row("Initial Capital", f"${summary['initial_capital']:,.2f}")
    table.add_row("Current Equity", f"[{color}]${summary['current_equity']:,.2f}[/{color}]")
    table.add_row("Cash Available", f"${summary['cash']:,.2f}")
    table.add_row("Total Return", f"[{color}]{summary['total_return_pct']:+.2f}%[/{color}]")
    table.add_row("Total P&L", f"[{color}]${summary['total_pnl']:+,.2f}[/{color}]")
    table.add_row("Closed Trades", str(summary["total_trades"]))
    table.add_row("Win Rate", f"{summary['win_rate_pct']:.1f}%")
    table.add_row("Open Positions", str(summary["open_positions"]))
    table.add_row("Last Run", str(summary["last_run"] or "—"))
    console.print(table)

    if portfolio["open_positions"]:
        pos_table = Table(title="Open Positions", box=box.SIMPLE, padding=(0, 1))
        pos_table.add_column("Symbol", style="cyan")
        pos_table.add_column("Entry", justify="right")
        pos_table.add_column("Current", justify="right")
        pos_table.add_column("Stop Loss", justify="right")
        pos_table.add_column("Take Profit", justify="right")
        pos_table.add_column("Size", justify="right")
        pos_table.add_column("Unrealized P&L", justify="right")

        for pos in portfolio["open_positions"]:
            price = live_prices.get(pos["symbol"], pos["entry_price"])
            ret = (price - pos["entry_price"]) / pos["entry_price"] * 100
            pnl = pos["position_value"] * (ret / 100)
            color = "green" if pnl >= 0 else "red"
            pos_table.add_row(
                pos["symbol"],
                f"${pos['entry_price']:,.2f}",
                f"${price:,.2f}",
                f"[red]${pos.get('stop_loss', 0):,.2f}[/red]",
                f"[green]${pos.get('take_profit', 0):,.2f}[/green]",
                f"{pos['size_pct'] * 100:.1f}%",
                f"[{color}]${pnl:+,.2f} ({ret:+.2f}%)[/{color}]",
            )
        console.print(pos_table)


def cmd_paper_reset(args) -> None:
    import os
    path = "./paper_portfolio.json"
    if os.path.exists(path):
        os.remove(path)
        console.print("[green]Paper portfolio reset. Starting fresh next run.[/green]")
    else:
        console.print("[yellow]No portfolio file found — nothing to reset.[/yellow]")


def _print_paper_results(results: dict) -> None:
    console.print(f"\n[bold]Paper Trade Update — {results['date']}[/bold]")

    if results.get("errors"):
        for err in results["errors"]:
            console.print(f"[red]Error:[/red] {err}")

    if results["closed_today"]:
        t = Table(title="Closed Today", box=box.SIMPLE, padding=(0, 1))
        t.add_column("Symbol", style="cyan")
        t.add_column("Entry", justify="right")
        t.add_column("Exit", justify="right")
        t.add_column("Return", justify="right")
        t.add_column("P&L", justify="right")
        t.add_column("Reason")
        for trade in results["closed_today"]:
            ret = trade.get("return_pct", 0)
            color = "green" if ret >= 0 else "red"
            t.add_row(
                trade["symbol"],
                f"${trade['entry_price']:,.2f}",
                f"${trade['exit_price']:,.2f}",
                f"[{color}]{ret:+.2f}%[/{color}]",
                f"[{color}]${trade['pnl']:+,.2f}[/{color}]",
                trade.get("exit_reason", "—"),
            )
        console.print(t)

    if results["opened_today"]:
        t = Table(title="Opened Today", box=box.SIMPLE, padding=(0, 1))
        t.add_column("Symbol", style="cyan")
        t.add_column("Entry", justify="right")
        t.add_column("Stop Loss", justify="right")
        t.add_column("Take Profit", justify="right")
        t.add_column("Size", justify="right")
        t.add_column("Value", justify="right")
        for pos in results["opened_today"]:
            t.add_row(
                pos["symbol"],
                f"${pos['entry_price']:,.2f}",
                f"[red]${pos.get('stop_loss', 0):,.2f}[/red]",
                f"[green]${pos.get('take_profit', 0):,.2f}[/green]",
                f"{pos['size_pct'] * 100:.1f}%",
                f"${pos['position_value']:,.2f}",
            )
        console.print(t)

    if results["held"]:
        console.print(f"[dim]Holding positions:[/dim] {', '.join(results['held'])}")

    eq = results.get("total_equity", 0)
    cash = results.get("cash", 0)
    console.print(f"\n[bold]Total Equity:[/bold] [cyan]${eq:,.2f}[/cyan]  |  [bold]Cash:[/bold] ${cash:,.2f}")


def main():
    parser = argparse.ArgumentParser(prog="cryptoagents", description="CryptoAgents CLI")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run single analysis")
    p_analyze.add_argument("symbol", help="e.g. BTCUSDT")
    p_analyze.add_argument("--timestamp", default=None, help="YYYY-MM-DD HH:MM:SS (default: now)")
    p_analyze.add_argument("--show-reports", action="store_true")

    # backtest
    p_back = sub.add_parser("backtest", help="Run backtest")
    p_back.add_argument("symbol", help="e.g. BTCUSDT")
    p_back.add_argument("--start", default="2024-01-01")
    p_back.add_argument("--end", default="2024-03-31")
    p_back.add_argument("--interval", default="1d", choices=["1h", "4h", "1d"])
    p_back.add_argument("--capital", type=float, default=10000.0)
    p_back.add_argument("--save", action="store_true")

    # paper-trade
    p_paper = sub.add_parser("paper-trade", help="Run daily paper trading update")
    p_paper.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
    p_paper.add_argument("--capital", type=float, default=10000.0)

    # paper-status
    sub.add_parser("paper-status", help="View current paper portfolio")

    # paper-reset
    sub.add_parser("paper-reset", help="Reset paper portfolio to start fresh")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "paper-trade":
        cmd_paper_trade(args)
    elif args.command == "paper-status":
        cmd_paper_status(args)
    elif args.command == "paper-reset":
        cmd_paper_reset(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
