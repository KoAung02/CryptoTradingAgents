from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report

SYSTEM_PROMPT = """You are the Bear Researcher on a professional crypto trading team.
Your job is to argue the strongest possible BEARISH or CAUTIONARY case based on the analyst reports.
You must:
- Identify risks, red flags, and overextensions in the on-chain, technical, sentiment, and news data.
- Directly counter the Bull Researcher's arguments with evidence and logic.
- Quantify potential downside targets with reasoning.
- Flag any signs of manipulation, narrative exhaustion, or structural weakness.
- Do NOT be blindly bearish. Find real problems, not invented ones.
- Your job is to prevent the team from making losing trades, not just to be contrarian.
- Be concise and structured."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    round_num = len(state.get("bear_arguments", [])) + 1
    bull_args = state.get("bull_arguments", [])

    reports_context = _build_reports_context(state)

    bull_counter_section = ""
    if bull_args:
        last_bull = truncate_report(bull_args[-1], max_chars=1500)
        bull_counter_section = f"\n\n### Bull Researcher's Argument (Round {round_num})\n{last_bull}"

    user_prompt = f"""You are making the BEAR CASE for {symbol} at {timestamp}.

### Analyst Reports Summary
{reports_context}
{bull_counter_section}

Write your Bear Case argument for Round {round_num}:

## Bear Case — Round {round_num} — {symbol}

### Core Concern
[1-2 sentence summary of the bear case]

### Evidence from Analyst Reports
[Cite specific data points that support caution or a bearish thesis]

### Counter to Bull Arguments
[Directly address the bull's points with evidence — skip if Round 1 with no bull arg yet]

### Downside Scenario
Target Price / % Loss: [estimate with reasoning]
Timeframe: [days/weeks]
Trigger: [what event or condition confirms the bear move]

### What Would Change My Mind
[Conditions under which the bear would become neutral or bullish]"""

    argument = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    bear_arguments = state.get("bear_arguments", []) + [argument]
    messages = state.get("messages", [])
    messages.append({"role": f"bear_researcher_r{round_num}", "content": argument})

    return {**state, "bear_arguments": bear_arguments, "messages": messages}


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
