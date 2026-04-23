from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, truncate_report, get_data_interface
from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, format_data_section, get_data_interface

SYSTEM_PROMPT = """You are an On-Chain Analyst at a professional crypto trading firm.
Your job is to evaluate blockchain-level data to assess network health, demand pressure,
and capital flows. Be precise, cite specific numbers, and give a clear BULLISH/NEUTRAL/BEARISH rating.
Keep your report concise and structured. Focus on the most actionable insights."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    data = get_data_interface(config)
    llm = get_llm(config, mode="quick")

    active_addr = data.get_active_addresses(symbol)
    netflow = data.get_exchange_netflow(symbol)
    whale_tx = data.get_whale_transactions(symbol)
    miner = data.get_miner_outflow(symbol)
    nvt = data.get_nvt_ratio(symbol)
    sopr = data.get_sopr(symbol)
    ssr = data.get_stablecoin_supply_ratio(symbol)
    unlocks = data.get_token_unlocks(symbol, days_ahead=30)
    tvl = data.get_tvl(symbol)
    revenue = data.get_protocol_revenue(symbol)

    context = f"Symbol: {symbol} | Timestamp: {timestamp}"
    context += format_data_section("Active Addresses", active_addr)
    context += format_data_section("Exchange Netflow", netflow)
    context += format_data_section("Whale Transactions", whale_tx)
    context += format_data_section("Miner Outflow", miner)
    context += format_data_section("NVT Ratio", nvt)
    context += format_data_section("SOPR", sopr)
    context += format_data_section("Stablecoin Supply Ratio", ssr)
    context += format_data_section("Token Unlocks (30d)", unlocks)
    context += format_data_section("TVL", tvl)
    context += format_data_section("Protocol Revenue", revenue)

    user_prompt = f"""Based on this on-chain data, write a concise On-Chain Analysis Report.

{context}

Format your report as:
## On-Chain Analysis Report — {symbol} — {timestamp}

### Network Health
[Active addresses trend, NVT assessment]

### Capital Flows
[Exchange netflow, stablecoin ratio, whale activity]

### Supply Pressure
[Token unlocks, miner outflow, SOPR]

### DeFi Metrics (if applicable)
[TVL, protocol revenue]

### On-Chain Signal
Rating: [BULLISH / NEUTRAL / BEARISH]
Confidence: [HIGH / MEDIUM / LOW]
Key Risks: [2-3 bullets]
Key Opportunities: [2-3 bullets]"""

    report = call_llm(llm, SYSTEM_PROMPT, user_prompt)

    messages = state.get("messages", [])
    messages.append({"role": "onchain_analyst", "content": report})

    return {**state, "onchain_report": report, "messages": messages}
