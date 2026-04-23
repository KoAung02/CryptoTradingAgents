from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, truncate_report, get_data_interface
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, get_data_interface

SYSTEM_PROMPT = """You are a Market/Technical Analyst at a professional crypto trading firm.
Your job is to analyze price action, volume, derivatives data, and technical indicators
to identify trend direction, momentum, and key price levels.
Be precise with numbers, identify specific support/resistance levels, and give a clear signal rating."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    data = get_data_interface(config)
    llm = get_llm(config, mode="quick")

    indicators = data.get_technical_indicators(symbol)
    stats_24h = data.get_24h_stats(symbol)
    order_book = data.get_order_book_depth(symbol)
    funding = data.get_funding_rate(symbol)
    oi = data.get_open_interest(symbol)
    lsr = data.get_long_short_ratio(symbol)
    volume_profile = data.get_volume_profile(symbol)
    liq = data.get_liquidation_heatmap(symbol)
    current_price = data.get_current_price(symbol)

    context = f"Symbol: {symbol} | Timestamp: {timestamp} | Current Price: ${current_price:,.4f}"
    context += format_data_section("Technical Indicators", indicators)
    context += format_data_section("24h Market Stats", stats_24h)
    context += format_data_section("Order Book", order_book)
    context += format_data_section("Funding Rate", funding)
    context += format_data_section("Open Interest", oi)
    context += format_data_section("Long/Short Ratio", lsr)
    context += format_data_section("Volume Profile (30d)", volume_profile)
    context += format_data_section("Liquidation Zones", liq)

    user_prompt = f"""Based on this technical and derivatives data, write a concise Technical Analysis Report.

{context}

Format your report as:
## Technical Analysis Report — {symbol} — {timestamp}

### Trend Structure
[EMA alignment, market structure, higher highs/lows]

### Momentum Indicators
[RSI reading, MACD signal, volume confirmation]

### Derivatives Sentiment
[Funding rate, OI trend, long/short ratio]

### Key Levels
Support: [specific price levels]
Resistance: [specific price levels]
Invalidation: [the level that breaks the thesis]

### Technical Signal
Rating: [BULLISH / NEUTRAL / BEARISH]
Confidence: [HIGH / MEDIUM / LOW]
Suggested Timeframe: [short-term / swing / position]
Key Risks: [2-3 bullets]"""

    report = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "market_analyst", "content": report})

    return {**state, "market_report": report, "messages": messages}
