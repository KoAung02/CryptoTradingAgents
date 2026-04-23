
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report, get_data_interface
from cryptoagents.agents.utils.report_parser import extract_signal_rating
from cryptoagents.memory.crypto_memory import CryptoSituationMemory

SYSTEM_PROMPT = """You are the Trader on a professional crypto trading team.
You receive an Investment Plan from the Research team and must produce a specific, actionable Trade Proposal.
You must:
- Decide on a concrete action: BUY, SELL, or HOLD.
- Specify position size based on your confidence: confidence 8-10 → 20-25%, confidence 6-7 → 10-15%, confidence <6 → 5% or HOLD.
- Set precise entry price, stop-loss, and take-profit levels with clear rationale.
- Stop loss MUST be at least 7% below entry for BTC, at least 8% for other coins. Crypto is highly volatile — tight stops get wiped by normal intraday wicks. Do NOT set stops closer than these minimums.
- Avoid round-number stops ($42,500, $43,000) — place them just below key support levels instead.
- Reference the Investment Plan and any relevant historical memory.
- If the Investment Plan is low-confidence or contradictory, default to HOLD and explain why.
- Be precise — vague proposals will be rejected by the Risk Management team.
- Always compute the Risk/Reward ratio before submitting. Target minimum 2:1."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    data = get_data_interface(config)
    llm = get_llm(config, mode="quick")

    current_price = data.get_current_price(symbol)
    portfolio = data.get_portfolio_state()
    investment_plan = state.get("investment_plan", "No investment plan available.")

    memory = CryptoSituationMemory(
        db_path=config.get("memory_db_path", "./crypto_memory"),
        top_k=config.get("memory_top_k", 3),
    )

    situation_desc = _build_situation_description(state)
    similar_memories = memory.query_similar(situation_desc)
    memory_context = memory.format_for_trader(similar_memories)

    stop_loss_pct = config.get("default_stop_loss_pct", 0.05)
    max_size = config.get("max_single_position_size", 0.10)
    available_capital = portfolio.get("available_capital_usd", 10000)

    user_prompt = f"""You are making a Trade Proposal for {symbol} at {timestamp}.

### Current Market Data
Current Price: ${current_price:,.4f}
Available Capital: ${available_capital:,.2f}
Max Single Position Size: {max_size * 100:.0f}% of portfolio
Default Stop Loss: {stop_loss_pct * 100:.0f}%

### Portfolio State
{_format_portfolio(portfolio)}

### Investment Plan (from Research Team)
{truncate_report(investment_plan, max_chars=2000)}

### Historical Memory
{memory_context}

Based on all the above, produce a precise Trade Proposal:

## Trade Proposal — {symbol} — {timestamp}

### Decision
Action: [BUY / SELL / HOLD]
Symbol: {symbol}
Position Size: [X% of portfolio — max {max_size * 100:.0f}%]
Entry Price: [MARKET or limit at $X]
Stop Loss: [$X — represents Y% risk]
Take Profit 1: [$X]
Take Profit 2: [$X]
Risk/Reward Ratio: [X:1]

### Rationale
[2-3 paragraphs connecting the Investment Plan to this specific proposal]

### Historical Memory Reference
[If applicable: what similar past situation was retrieved and how it informs this trade]

### Confidence
Level: [HIGH / MEDIUM / LOW]
Main Uncertainty: [what could make this trade wrong]"""

    proposal = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "trader", "content": proposal})

    return {**state, "trade_proposal": proposal, "messages": messages}


def _build_situation_description(state: dict) -> str:
    onchain = extract_signal_rating(state.get("onchain_report", ""))
    technical = extract_signal_rating(state.get("market_report", ""))
    sentiment = extract_signal_rating(state.get("sentiment_report", ""))
    news = extract_signal_rating(state.get("news_report", ""))
    return (
        f"{state['symbol']} trading situation: "
        f"on-chain signal {onchain}, technical signal {technical}, "
        f"sentiment {sentiment}, news {news}."
    )


def _format_portfolio(portfolio: dict) -> str:
    lines = []
    lines.append(f"  Total Value: ${portfolio.get('total_portfolio_value_usd', 0):,.2f}")
    lines.append(f"  Available Capital: ${portfolio.get('available_capital_usd', 0):,.2f}")
    lines.append(f"  Portfolio Heat: {portfolio.get('portfolio_heat_pct', 0) * 100:.1f}%")
    positions = portfolio.get("open_positions", [])
    if positions:
        lines.append(f"  Open Positions: {len(positions)}")
        for p in positions[:3]:
            lines.append(f"    - {p.get('symbol')}: {p.get('side')} @ ${p.get('entry_price', 0):,.2f}")
    else:
        lines.append("  Open Positions: None")
    return "\n".join(lines)
