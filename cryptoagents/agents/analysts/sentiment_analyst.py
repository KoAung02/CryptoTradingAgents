from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, truncate_report, get_data_interface
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, get_data_interface

SYSTEM_PROMPT = """You are a Sentiment & Social Analyst at a professional crypto trading firm.
Your job is to gauge market psychology through social media, fear/greed indices, and community signals.
Identify both confirming signals and contrarian setups. Be specific about data points."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    data = get_data_interface(config)
    llm = get_llm(config, mode="quick")

    fng = data.get_fear_greed_index()
    social_vol = data.get_social_volume(symbol)
    twitter = data.get_twitter_sentiment(symbol)
    reddit = data.get_reddit_sentiment(symbol)
    influencer = data.get_influencer_sentiment(symbol)
    galaxy = data.get_galaxy_score(symbol)
    google = data.get_google_trends(symbol)
    market_global = data.get_global_market()

    context = f"Symbol: {symbol} | Timestamp: {timestamp}"
    context += format_data_section("Fear & Greed Index", fng)
    context += format_data_section("Social Volume", social_vol)
    context += format_data_section("Twitter Sentiment", twitter)
    context += format_data_section("Reddit Sentiment", reddit)
    context += format_data_section("Influencer Sentiment", influencer)
    context += format_data_section("Galaxy Score", galaxy)
    context += format_data_section("Google Trends", google)
    context += format_data_section("Global Market Context", market_global)

    user_prompt = f"""Based on this sentiment and social data, write a concise Sentiment Analysis Report.

{context}

Format your report as:
## Sentiment & Social Analysis Report — {symbol} — {timestamp}

### Market Psychology
[Fear & Greed reading, interpretation in current price context]

### Social Momentum
[Social volume trend, Reddit/community activity]

### Community Sentiment
[Twitter/Reddit bullish/bearish ratio, notable narratives]

### Contrarian Flags
[Is sentiment too extreme? Is this a crowded trade?]

### Sentiment Signal
Rating: [BULLISH / NEUTRAL / BEARISH]
Confidence: [HIGH / MEDIUM / LOW]
Contrarian Risk: [HIGH / MEDIUM / LOW]
Key Observations: [2-3 bullets]"""

    report = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "sentiment_analyst", "content": report})

    return {**state, "sentiment_report": report, "messages": messages}
