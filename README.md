# CryptoAgents

A multi-agent LLM framework for cryptocurrency analysis, backtesting, and paper trading, inspired by [TradingAgents](https://tradingagents-ai.github.io).

Uses **Together AI** for LLM inference (free tier available) and **Binance public API** for market data.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Phase 1 — Analysis                   │
│   On-Chain  →  Market  →  Sentiment  →  News Analyst        │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2 — Research Debate                │
│         Bull Researcher  ⇄  Bear Researcher                 │
│                    Research Manager                         │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                       Phase 3 — Trader                      │
│              Generates Trade Proposal (BUY/SELL/HOLD)       │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Phase 4 — Risk Debate                    │
│    Aggressive  ⇄  Conservative  ⇄  Neutral Risk Advisor    │
│                      Risk Manager                           │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  Phase 5 — Portfolio Manager                │
│          Final Decision: BUY / HOLD / SELL + parameters     │
└─────────────────────────────────────────────────────────────┘
```

13 agents total, orchestrated by [LangGraph](https://github.com/langchain-ai/langgraph).

## Models

| Role | Model | Used for | Cost |
|------|-------|----------|------|
| Quick | `openai/gpt-oss-20b` (Together AI) | Analysts, Trader, Researchers | $0.05/$0.20 per MTok |
| Deep | `deepseek-ai/DeepSeek-V3.1` (Together AI) | Risk Manager, Portfolio Manager | $0.60/$1.70 per MTok |

Typical cost: ~$0.05 per 1-week backtest, ~$0.60 per 90-day backtest.

## Requirements

- Python 3.11+
- Together AI API key (get one free at [api.together.ai](https://api.together.ai))

## Installation

```bash
git clone <repo>
cd CryptoAgents
pip install -r requirements.txt
cp .env.example .env
# Add your TOGETHER_API_KEY to .env
```

## Usage

### Single analysis (live market)

```bash
python -m cli.main analyze BTCUSDT
python -m cli.main analyze ETHUSDT --timestamp "2024-06-15 00:00:00"
python -m cli.main analyze SOLUSDT --show-reports
```

### Backtest

```bash
# Basic
python -m cli.main backtest BTCUSDT --start 2024-01-01 --end 2024-03-31 --save

# With caffeinate (keeps Mac awake when lid is closed)
caffeinate -i python -m cli.main backtest BTCUSDT --start 2024-01-01 --end 2024-03-31 --save
```

### Paper Trading

Run once a day to get new signals and open/close positions:

```bash
python -m cli.main paper-trade --symbols BTCUSDT ETHUSDT BNBUSDT SOLUSDT
```

Check portfolio status anytime:

```bash
python -m cli.main paper-status
```

Run the 24/7 price monitor in the background (free — no LLM calls):

```bash
caffeinate -i python -m cryptoagents.paper_trader.price_monitor
```

Reset portfolio to start fresh:

```bash
python -m cli.main paper-reset
```

### Python API

```python
from main import CryptoAgents

ca = CryptoAgents(debug=True)
state, decision = ca.analyze("BTCUSDT", "2024-06-15 00:00:00")
print(decision)
# {'action': 'BUY', 'entry': 65000, 'stop_loss': 60450, 'take_profit_1': 79300, ...}

# After trade resolves, store outcome in memory
ca.record_outcome(state, {
    "entry_price": 65000,
    "exit_price": 68000,
    "lessons_learned": "Momentum held through resistance",
})
```

## Q1 2024 Backtest Results (Jan–Mar 2024)

Backtested across 4 symbols with $10,000 initial capital each.

| Symbol | Return | Sharpe | Win Rate | Max Drawdown |
|--------|--------|--------|----------|--------------|
| BTC | +6.39% | 11.39 | 71.4% | 0.49% |
| ETH | +4.06% | 5.25 | 44.4% | 2.99% |
| BNB | +4.51% | 4.65 | 42.9% | 1.60% |
| SOL | +6.69% | 2.47 | 30.0% | 2.33% |
| **Combined** | **+5.41%** | **5.95** | **47.2%** | **1.60%** |

Combined portfolio: $40,000 → $42,165 (+$2,165) with under 3% max drawdown during one of crypto's strongest bull quarters.

## Position Sizing Logic

| Confidence | Base Size | Trend Multiplier | Max Size |
|-----------|-----------|-----------------|----------|
| 8–10 | 20–25% | 0.7× – 2.0× (based on 20-day trend) | 25% cap |
| 6–7 | 10–15% | 0.7× – 2.0× | 25% cap |
| < 6 | 5% | 0.7× – 2.0× | 25% cap |

- **Strong bull trend** (20-day return ≥ 15%): 2× multiplier
- **Mild bull** (5–15%): 1.5×
- **Neutral**: 1.0×
- **Bearish**: 0.7×

## Risk Management

- **Minimum stop loss**: 7% below entry for BTC, 8% for altcoins
- **Minimum take profit**: 2× the stop distance (enforces 2:1 R:R minimum)
- **Trailing stop**: trails 10% below highest close (BTC), 12% for altcoins
- **Entry-day protection**: stop loss not checked on same candle as entry

## Data Sources (all free)

| Data | Source |
|------|--------|
| Price / OHLCV / derivatives | Binance public API |
| Market cap / fundamentals | CoinGecko free tier |
| Fear & Greed Index | Alternative.me |
| News | CryptoPanic free endpoint |
| DeFi TVL / revenue | DeFiLlama |

## Configuration

Edit `cryptoagents/default_config.py`:

```python
"llm_provider": "together",
"deep_think_llm": "deepseek-ai/DeepSeek-V3.1",
"quick_think_llm": "openai/gpt-oss-20b",
"max_portfolio_heat": 0.40,
"max_single_position_size": 0.25,
"default_stop_loss_pct": 0.07,
"kelly_fraction": 0.25,
```

## Project Structure

```
CryptoAgents/
├── main.py                        # Python API entrypoint
├── cli/main.py                    # Rich interactive CLI
├── cryptoagents/
│   ├── default_config.py
│   ├── graph/
│   │   ├── crypto_graph.py        # LangGraph orchestration
│   │   └── state.py               # AgentState TypedDict
│   ├── agents/
│   │   ├── analysts/              # on-chain, market, sentiment, news
│   │   ├── researchers/           # bull, bear, research manager
│   │   ├── trader/
│   │   ├── risk_mgmt/             # aggressive, conservative, neutral, risk manager
│   │   └── managers/              # portfolio manager
│   ├── dataflows/                 # Binance + other API clients, cache
│   ├── llm_clients/               # Together AI / DeepSeek / OpenAI factory
│   ├── memory/                    # ChromaDB situation memory
│   ├── backtester/
│   │   ├── backtest_runner.py
│   │   ├── metrics.py
│   │   └── report_generator.py
│   └── paper_trader/
│       ├── paper_trader.py        # Daily paper trading runner
│       ├── portfolio.py           # Portfolio state management
│       └── price_monitor.py      # 24/7 background price checker
└── reports/                       # Saved backtest reports (JSON + Markdown)
```

## Backtesting Methodology

1. Download historical OHLCV data for the target symbol
2. Run the 13-agent pipeline for each day in the period
3. Apply confidence-based + trend-based position sizing
4. Simulate entries, trailing stops, and take profits
5. Generate JSON + Markdown report with full trade log and metrics
