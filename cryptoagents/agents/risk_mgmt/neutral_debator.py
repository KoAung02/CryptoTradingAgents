import math
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report
from cryptoagents.agents.utils.report_parser import parse_final_decision

SYSTEM_PROMPT = """You are the Neutral Risk Advisor on a professional crypto trading team.
Your job is to provide the most objective, quantitative risk assessment.
You must:
- Use the Kelly Criterion (or a fraction thereof) to suggest optimal position size.
- Compute portfolio heat if this trade is taken.
- Assess whether this trade increases or decreases portfolio diversification.
- Identify the most likely failure mode and its estimated probability.
- Propose a concrete compromise between the Aggressive and Conservative positions.
- Be data-driven and quantitative — show your calculations."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    round_num = len(state.get("neutral_risk_args", [])) + 1
    aggressive_args = state.get("aggressive_risk_args", [])
    conservative_args = state.get("conservative_risk_args", [])

    trade_proposal = state.get("trade_proposal", "")
    parsed = parse_final_decision(trade_proposal)

    kelly_size = _compute_kelly(parsed, config)
    portfolio_heat = _compute_portfolio_heat(parsed, config)

    trade_proposal_text = truncate_report(trade_proposal, 1200)
    agg_context = truncate_report(aggressive_args[-1], 600) if aggressive_args else "None yet."
    con_context = truncate_report(conservative_args[-1], 600) if conservative_args else "None yet."

    user_prompt = f"""You are providing the NEUTRAL/QUANTITATIVE risk assessment for {symbol} at {timestamp}.

### Trade Proposal
{trade_proposal_text}

### Pre-computed Risk Metrics
Kelly Criterion Size (fractional): {kelly_size:.1f}% of portfolio
Estimated Portfolio Heat if Trade Taken: {portfolio_heat:.1f}%
Max Allowed Heat: {config.get('max_portfolio_heat', 0.20) * 100:.0f}%
Max Single Position: {config.get('max_single_position_size', 0.10) * 100:.0f}%

### Aggressive Advisor's Argument
{agg_context}

### Conservative Advisor's Argument
{con_context}

Write your Neutral Risk argument for Round {round_num}:

## Neutral Risk Argument — Round {round_num} — {symbol}

### Kelly Criterion Analysis
[Show the calculation: win_rate, avg_win, avg_loss → Kelly % → fractional Kelly]
Suggested Size: {kelly_size:.1f}% (Kelly fraction: {config.get('kelly_fraction', 0.25)})

### Portfolio Heat Assessment
Current Heat: [X%]
Heat if Trade Taken: {portfolio_heat:.1f}%
Assessment: [ACCEPTABLE / ELEVATED / CRITICAL]

### Correlation & Diversification
[Does this trade increase concentration risk? Correlation to BTC?]

### Most Likely Failure Mode
[The single most probable reason this trade fails, with estimated probability]

### Compromise Recommendation
Position Size: [between aggressive and conservative suggestion]
Stop Loss: [balanced recommendation]
Justification: [2-3 sentences citing both sides]"""

    argument = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    neutral_risk_args = state.get("neutral_risk_args", []) + [argument]
    messages = state.get("messages", [])
    messages.append({"role": f"neutral_risk_r{round_num}", "content": argument})

    return {**state, "neutral_risk_args": neutral_risk_args, "messages": messages}


def _compute_kelly(parsed: dict, config: dict) -> float:
    win_rate = 0.55
    avg_win = abs((parsed.get("take_profit_1") or 0) - (parsed.get("entry") or 0))
    avg_loss = abs((parsed.get("entry") or 0) - (parsed.get("stop_loss") or 0))

    if avg_loss > 0 and avg_win > 0:
        b = avg_win / avg_loss
        kelly = win_rate - ((1 - win_rate) / b)
    else:
        kelly = 0.05

    kelly = max(0.0, kelly)
    fractional = kelly * config.get("kelly_fraction", 0.25)
    max_size = config.get("max_single_position_size", 0.10)
    return round(min(fractional, max_size) * 100, 2)


def _compute_portfolio_heat(parsed: dict, config: dict) -> float:
    size_pct = (parsed.get("position_size_pct") or 5.0) / 100
    entry = parsed.get("entry") or 1
    stop = parsed.get("stop_loss") or (entry * 0.95)
    risk_per_unit = abs(entry - stop) / entry if entry else 0.05
    trade_risk = size_pct * risk_per_unit * 100
    current_heat = 0.0
    return round(current_heat + trade_risk, 2)
