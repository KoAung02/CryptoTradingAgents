from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Research Manager on a professional crypto trading team.
You have read all analyst reports and observed a full Bull vs Bear debate.
Your job is to produce a balanced, final Investment Plan that:
- Summarizes the consensus view and key points of disagreement.
- Assigns an overall directional bias (Bullish / Neutral / Bearish) with confidence level.
- Identifies the single most important variable to watch.
- Provides specific entry conditions, target levels, and stop-loss levels for the Trader.
- Does NOT make the final buy/sell/hold call — that is the Trader's job.
Be decisive, balanced, and precise with price levels."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    num_rounds = state.get("research_debate_rounds", 1)
    bull_args = state.get("bull_arguments", [])
    bear_args = state.get("bear_arguments", [])

    reports_context = _build_reports_context(state)
    debate_context = _build_debate_context(bull_args, bear_args)

    user_prompt = f"""You have observed {num_rounds} round(s) of Bull vs Bear debate for {symbol} at {timestamp}.

### Analyst Reports
{reports_context}

### Debate Summary
{debate_context}

Synthesize everything into a final Investment Plan:

## Investment Plan — {symbol} — {timestamp}

### Consensus Summary
[What all analysts and researchers broadly agree on]

### Key Disagreements
[Where bull and bear had genuine unresolved conflict]

### Overall Bias
Direction: [BULLISH / NEUTRAL / BEARISH]
Confidence: [HIGH / MEDIUM / LOW]
Timeframe: [short-term (1-7d) / swing (1-4w) / position (1-3mo)]

### Most Important Variable to Watch
[The single factor that will determine whether this trade works]

### Suggested Trade Parameters
Proposed Action: [LONG / SHORT / FLAT]
Entry Condition: [specific price level or trigger]
Take Profit 1: [$level]
Take Profit 2: [$level]
Stop Loss: [$level]
Position Sizing Note: [conservative / moderate / aggressive given current conditions]"""

    investment_plan = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "research_manager", "content": investment_plan})

    return {**state, "investment_plan": investment_plan, "messages": messages}


def _build_reports_context(state: dict) -> str:
    parts = []
    if state.get("onchain_report"):
        parts.append("**On-Chain:**\n" + truncate_report(state["onchain_report"], 600))
    if state.get("market_report"):
        parts.append("**Technical:**\n" + truncate_report(state["market_report"], 600))
    if state.get("sentiment_report"):
        parts.append("**Sentiment:**\n" + truncate_report(state["sentiment_report"], 500))
    if state.get("news_report"):
        parts.append("**News:**\n" + truncate_report(state["news_report"], 500))
    return "\n\n".join(parts) if parts else "No analyst reports available."


def _build_debate_context(bull_args: list, bear_args: list) -> str:
    parts = []
    rounds = max(len(bull_args), len(bear_args))
    for i in range(rounds):
        if i < len(bull_args):
            parts.append(f"**Bull Round {i+1}:**\n" + truncate_report(bull_args[i], 800))
        if i < len(bear_args):
            parts.append(f"**Bear Round {i+1}:**\n" + truncate_report(bear_args[i], 800))
    return "\n\n".join(parts) if parts else "No debate recorded."
