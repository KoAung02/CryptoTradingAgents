from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Risk Manager on a professional crypto trading team.
After observing a full risk debate, your job is to produce a final Risk Assessment Report.
You must:
- State whether the Trade Proposal should be APPROVED, MODIFIED, or REJECTED.
- If MODIFIED: specify the exact adjusted parameters (size, stop, entry).
- Quantify the maximum acceptable loss for this trade.
- Flag any portfolio-level risks (concentration, correlation, leverage).
- Provide the Portfolio Manager with a clear verdict and one-paragraph justification.
- Be decisive — the Portfolio Manager depends on your clarity."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    num_rounds = state.get("risk_debate_rounds", 1)
    trade_proposal = truncate_report(state.get("trade_proposal", "No proposal."), 1200)
    debate_context = _build_debate_context(state)

    max_heat = config.get("max_portfolio_heat", 0.20) * 100
    max_size = config.get("max_single_position_size", 0.10) * 100

    user_prompt = f"""You have observed {num_rounds} round(s) of risk debate for {symbol} at {timestamp}.

### Original Trade Proposal
{trade_proposal}

### Risk Debate Summary
{debate_context}

### Hard Risk Limits
Max Portfolio Heat: {max_heat:.0f}%
Max Single Position Size: {max_size:.0f}%

Produce the final Risk Assessment Report:

## Risk Assessment Report — {symbol} — {timestamp}

### Trade Proposal Summary
[Brief restatement of the Trader's proposed action and parameters]

### Risk Metrics
Portfolio Heat (if trade taken): [X%]
Max Drawdown This Trade: [$X or X%]
Tail Risk Score: [1-10, where 10 is highest risk]
BTC Correlation: [HIGH / MEDIUM / LOW]

### Risk Debate Synthesis
[2-3 sentences summarising the aggressive vs conservative debate and the neutral resolution]

### Recommendation
Verdict: [APPROVE / MODIFY / REJECT]
If MODIFY — adjusted parameters:
  Position Size: [X%]
  Stop Loss: [$X]
  Entry: [$X or MARKET]
Justification: [1 clear paragraph explaining the verdict]"""

    risk_assessment = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "risk_manager", "content": risk_assessment})

    return {**state, "risk_assessment": risk_assessment, "messages": messages}


def _build_debate_context(state: dict) -> str:
    parts = []
    agg = state.get("aggressive_risk_args", [])
    con = state.get("conservative_risk_args", [])
    neu = state.get("neutral_risk_args", [])

    rounds = max(len(agg), len(con), len(neu))
    for i in range(rounds):
        if i < len(agg):
            parts.append(f"**Aggressive R{i+1}:**\n" + truncate_report(agg[i], 500))
        if i < len(con):
            parts.append(f"**Conservative R{i+1}:**\n" + truncate_report(con[i], 500))
        if i < len(neu):
            parts.append(f"**Neutral R{i+1}:**\n" + truncate_report(neu[i], 500))

    return "\n\n".join(parts) if parts else "No debate recorded."
