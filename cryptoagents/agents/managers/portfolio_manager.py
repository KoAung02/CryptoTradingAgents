from cryptoagents.llm_clients.client_factory import get_llm
from cryptoagents.agents.utils.agent_utils import call_llm, truncate_report
from cryptoagents.agents.utils.report_parser import parse_final_decision, extract_signal_rating

SYSTEM_PROMPT = """You are the Portfolio Manager and the final decision-maker on a professional crypto trading team.
You have received all analyst reports, the Investment Plan, the Trade Proposal, and the Risk Assessment.
Your job is to make the FINAL trading decision. You must:
- Issue a final action: BUY, HOLD, or SELL.
- If the Risk Manager said MODIFY, use the modified parameters exactly.
- If the Risk Manager said REJECT, issue HOLD unless you have strong independent reason to override.
- Provide a clear rationale referencing all key inputs.
- Output a structured Final Decision that can be parsed by the execution layer.
- Be decisive. You are responsible for portfolio performance."""


def run(state: dict, config: dict) -> dict:
    symbol = state["symbol"]
    timestamp = state["timestamp"]
    llm = get_llm(config, mode="deep")

    onchain_signal = extract_signal_rating(state.get("onchain_report", ""))
    technical_signal = extract_signal_rating(state.get("market_report", ""))
    sentiment_signal = extract_signal_rating(state.get("sentiment_report", ""))
    news_signal = extract_signal_rating(state.get("news_report", ""))

    investment_plan = truncate_report(state.get("investment_plan", "Not available."), 1000)
    trade_proposal = truncate_report(state.get("trade_proposal", "Not available."), 1000)
    risk_assessment = truncate_report(state.get("risk_assessment", "Not available."), 1200)

    parsed_proposal = parse_final_decision(state.get("trade_proposal", ""))
    parsed_risk = _extract_risk_verdict(state.get("risk_assessment", ""))

    user_prompt = f"""You are making the FINAL DECISION for {symbol} at {timestamp}.

### Analyst Signal Summary
On-Chain: {onchain_signal} | Technical: {technical_signal} | Sentiment: {sentiment_signal} | News: {news_signal}

### Investment Plan (Research Manager)
{investment_plan}

### Trade Proposal (Trader)
{trade_proposal}

### Risk Assessment (Risk Manager)
Verdict: {parsed_risk}
{risk_assessment}

### Guidelines
- If Risk Manager said APPROVE: follow the Trader's proposal.
- If Risk Manager said MODIFY: use the modified parameters from the Risk Assessment.
- If Risk Manager said REJECT: issue HOLD unless all 4 analyst signals are strongly aligned.
- Max position size: {config.get('max_single_position_size', 0.25) * 100:.0f}%
- High confidence (8-10): target 20-25% position. Medium (6-7): 10-15%. Low (<6): 5% or HOLD.

Produce the final structured decision:

## FINAL DECISION — {symbol} — {timestamp}

### ACTION: [BUY / HOLD / SELL]

### Parameters (if BUY or SELL)
Entry: [$X or MARKET]
Stop Loss: [$X]
Take Profit 1: [$X]
Take Profit 2: [$X]
Position Size: [X% of portfolio]

### Rationale
[2-3 paragraphs referencing analyst consensus, investment plan, and risk assessment]

### Risk Acknowledgment
[What would invalidate this decision and require immediate position exit]

### Confidence Score: [1-10]"""

    report = call_llm(llm, SYSTEM_PROMPT, user_prompt)
    parsed = parse_final_decision(report)

    messages = state.get("messages", [])
    messages.append({"role": "portfolio_manager", "content": report})

    return {
        **state,
        "portfolio_manager_report": report,
        "final_action": parsed.get("action", "HOLD"),
        "messages": messages,
    }


def _extract_risk_verdict(risk_assessment: str) -> str:
    import re
    match = re.search(r"Verdict[:\s]+(APPROVE|MODIFY|REJECT)", risk_assessment, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"
