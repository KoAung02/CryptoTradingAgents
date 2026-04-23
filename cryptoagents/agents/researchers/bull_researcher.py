from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Bull Researcher on a professional crypto trading team.
Your job is to argue the strongest possible BULLISH case based on the analyst reports provided.
You must:
- Highlight the most compelling on-chain, technical, sentiment, and news signals that support a long position.
- Directly counter the Bear Researcher's arguments with evidence and logic (in rounds > 1).
- Quantify potential upside targets with reasoning.
- Acknowledge genuine risks but explain why the upside outweighs them.
- Do NOT be blindly bullish. Your credibility depends on intellectual honesty.
- Be concise and structured."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    round_num = len(state.get("bull_arguments", [])) + 1
    bear_args = state.get("bear_arguments", [])

    reports_context = _build_reports_context(state)

    bear_counter_section = ""
    if bear_args:
        last_bear = truncate_report(bear_args[-1], max_chars=1500)
        bear_counter_section = f"\n\n### Bear Researcher's Previous Argument (Round {round_num - 1})\n{last_bear}"

    user_prompt = f"""You are making the BULL CASE for {symbol} at {timestamp}.

### Analyst Reports Summary
{reports_context}
{bear_counter_section}

Write your Bull Case argument for Round {round_num}:

## Bull Case — Round {round_num} — {symbol}

### Core Thesis
[1-2 sentence summary of the bull case]

### Evidence from Analyst Reports
[Cite specific data points from each relevant analyst report]

### Counter to Bear Arguments
[Directly address the bear's points — skip this section if Round 1]

### Upside Scenario
Target Price / % Gain: [estimate with reasoning]
Timeframe: [days/weeks]
Trigger: [what event or condition confirms the bull move]

### Risk Acknowledgment
[1-2 genuine risks the bull must admit]"""

    argument = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    bull_arguments = state.get("bull_arguments", []) + [argument]
    messages = state.get("messages", [])
    messages.append({"role": f"bull_researcher_r{round_num}", "content": argument})

    return {**state, "bull_arguments": bull_arguments, "messages": messages}


def _build_reports_context(state: dict) -> str:
    parts = []
    if state.get("onchain_report"):
        parts.append("**On-Chain:**\n" + truncate_report(state["onchain_report"], 800))
    if state.get("market_report"):
        parts.append("**Technical:**\n" + truncate_report(state["market_report"], 800))
    if state.get("sentiment_report"):
        parts.append("**Sentiment:**\n" + truncate_report(state["sentiment_report"], 600))
    if state.get("news_report"):
        parts.append("**News:**\n" + truncate_report(state["news_report"], 600))
    return "\n\n".join(parts) if parts else "No analyst reports available yet."
