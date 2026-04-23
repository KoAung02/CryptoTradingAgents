from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Conservative Risk Advisor on a professional crypto trading team.
Your job is to protect the portfolio from catastrophic loss.
You must:
- Argue for reduced position sizing if volatility, correlation, or drawdown risk is elevated.
- Identify tail risks (exchange hack, regulatory action, liquidity gap, cascade liquidation) the Trader may have underweighted.
- Recommend tighter stop-losses where appropriate.
- Quantify maximum acceptable drawdown from this trade given portfolio size.
- Challenge the Aggressive Advisor's arguments with evidence.
- Do NOT be paralysed by fear — only raise genuine, quantifiable risks."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    round_num = len(state.get("conservative_risk_args", [])) + 1
    aggressive_args = state.get("aggressive_risk_args", [])
    neutral_args = state.get("neutral_risk_args", [])

    trade_proposal = truncate_report(state.get("trade_proposal", "No trade proposal."), 1500)

    counter_section = ""
    if aggressive_args:
        counter_section += f"\n\n### Aggressive Advisor's Last Argument\n{truncate_report(aggressive_args[-1], 800)}"
    if neutral_args:
        counter_section += f"\n\n### Neutral Advisor's Last Argument\n{truncate_report(neutral_args[-1], 600)}"

    max_size = config.get("max_single_position_size", 0.10)
    default_sl = config.get("default_stop_loss_pct", 0.05)

    user_prompt = f"""You are arguing the CONSERVATIVE RISK case for the following Trade Proposal on {symbol} at {timestamp}.

### Trade Proposal
{trade_proposal}

### Risk Parameters
Max Single Position Size: {max_size * 100:.0f}%
Default Stop Loss: {default_sl * 100:.0f}%
{counter_section}

Write your Conservative Risk argument for Round {round_num}:

## Conservative Risk Argument — Round {round_num} — {symbol}

### Tail Risk Assessment
[Identify 2-3 specific tail risks that could invalidate this trade]

### Position Sizing Concern
[Why the proposed size should be reduced — cite volatility or portfolio heat]

### Stop-Loss Recommendation
[Is the stop tight enough? Suggest adjustment with reasoning]

### Max Acceptable Drawdown
[Dollar/% amount this trade should not exceed given portfolio size]

### Counter to Aggressive/Neutral Arguments
[Directly address their points — skip if Round 1]

### Recommended Parameters
Position Size: [X% — reduced from proposal]
Stop Loss: [$X — tighter]
Justification: [1-2 sentences]"""

    argument = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    conservative_risk_args = state.get("conservative_risk_args", []) + [argument]
    messages = state.get("messages", [])
    messages.append({"role": f"conservative_risk_r{round_num}", "content": argument})

    return {**state, "conservative_risk_args": conservative_risk_args, "messages": messages}
