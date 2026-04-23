from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Aggressive Risk Advisor on a professional crypto trading team.
Your job is NOT to be reckless — it is to ensure the team doesn't leave money on the table through excessive caution.
You must:
- Argue for maximum allowable position size given current market conditions.
- Identify why the stop-loss is appropriately placed (or suggest widening if too tight).
- Quantify the opportunity cost of being too conservative.
- Challenge the Conservative Advisor's arguments with data and logic.
- Flag if the trade is too small to be meaningful given the risk/reward.
- Be concise and evidence-based."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    round_num = len(state.get("aggressive_risk_args", [])) + 1
    conservative_args = state.get("conservative_risk_args", [])
    neutral_args = state.get("neutral_risk_args", [])

    trade_proposal = truncate_report(state.get("trade_proposal", "No trade proposal."), 1500)

    counter_section = ""
    if conservative_args:
        counter_section += f"\n\n### Conservative Advisor's Last Argument\n{truncate_report(conservative_args[-1], 800)}"
    if neutral_args:
        counter_section += f"\n\n### Neutral Advisor's Last Argument\n{truncate_report(neutral_args[-1], 600)}"

    max_size = config.get("max_single_position_size", 0.10)
    max_heat = config.get("max_portfolio_heat", 0.20)

    user_prompt = f"""You are arguing the AGGRESSIVE RISK case for the following Trade Proposal on {symbol} at {timestamp}.

### Trade Proposal
{trade_proposal}

### Risk Parameters
Max Single Position Size: {max_size * 100:.0f}%
Max Portfolio Heat: {max_heat * 100:.0f}%
{counter_section}

Write your Aggressive Risk argument for Round {round_num}:

## Aggressive Risk Argument — Round {round_num} — {symbol}

### Position Sizing Case
[Why the proposed size is appropriate or should be larger — cite R/R ratio]

### Stop-Loss Assessment
[Why the stop is not too tight, or suggest widening with reasoning]

### Opportunity Cost of Caution
[Quantify what is left on the table if position is cut too small]

### Counter to Conservative/Neutral Arguments
[Directly address their points — skip if Round 1]

### Recommended Parameters
Position Size: [X% — within the {max_size * 100:.0f}% max]
Stop Loss: [$X]
Justification: [1-2 sentences]"""

    argument = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    aggressive_risk_args = state.get("aggressive_risk_args", []) + [argument]
    messages = state.get("messages", [])
    messages.append({"role": f"aggressive_risk_r{round_num}", "content": argument})

    return {**state, "aggressive_risk_args": aggressive_risk_args, "messages": messages}
