from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, truncate_report, get_data_interface
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, get_data_interface

SYSTEM_PROMPT = """You are a News & Macro Analyst at a professional crypto trading firm.
Your job is to monitor crypto-native news, macro environment, and regulatory developments.
Assess the directional impact of each news item (POSITIVE/NEGATIVE/NEUTRAL) and identify catalysts or risks."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    data = get_data_interface(config)
    llm = get_llm(config, mode="quick")

    news_items = data.get_crypto_news(symbol, limit=8)
    macro_events = data.get_macro_events()
    regulatory = data.get_regulatory_news()
    protocol_events = data.get_protocol_events(symbol)
    narratives = data.get_narrative_trends()
    global_market = data.get_global_market()
    asset_metrics = data.get_asset_metrics(symbol)
    github = data.get_github_activity(symbol)

    context = f"Symbol: {symbol} | Timestamp: {timestamp}"

    news_formatted = "\n".join(
        f"  - [{i+1}] {n.get('title', '')} ({n.get('source', '')})"
        for i, n in enumerate(news_items[:6])
    )
    context += f"\n### Recent News\n{news_formatted}"
    context += format_data_section("Macro Events", macro_events)
    context += format_data_section("Regulatory Landscape", regulatory)
    context += format_data_section("Narrative Trends", narratives)
    context += format_data_section("Global Market", global_market)
    context += format_data_section("Asset Fundamentals", asset_metrics)
    context += format_data_section("Developer Activity", github)

    user_prompt = f"""Based on this news and macro data, write a concise News & Macro Analysis Report.

{context}

Format your report as:
## News & Macro Analysis Report — {symbol} — {timestamp}

### Breaking & Recent News
[Top 3-5 news items with POSITIVE/NEGATIVE/NEUTRAL impact]

### Macro Environment
[BTC dominance, total market direction, upcoming macro events]

### Regulatory Landscape
[Key regulatory developments and their impact]

### Protocol Catalyst or Risk
[Upcoming events, developer activity, governance]

### Narrative Context
[Which crypto narratives is this asset exposed to?]

### News Signal
Rating: [BULLISH / NEUTRAL / BEARISH]
Confidence: [HIGH / MEDIUM / LOW]
Catalyst Timeline: [immediate / 1-7 days / 7-30 days]
Key Risks: [2-3 bullets]"""

    report = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "news_analyst", "content": report})

    return {**state, "news_report": report, "messages": messages}
