from typing import TypedDict, Optional


class AgentState(TypedDict):
    # Input
    symbol: str
    timestamp: str

    # Phase 1 outputs
    onchain_report: Optional[str]
    market_report: Optional[str]
    sentiment_report: Optional[str]
    news_report: Optional[str]

    # Phase 2 outputs
    bull_arguments: list
    bear_arguments: list
    investment_plan: Optional[str]
    research_debate_rounds: int

    # Phase 3 output
    trade_proposal: Optional[str]

    # Phase 4 outputs
    aggressive_risk_args: list
    conservative_risk_args: list
    neutral_risk_args: list
    risk_assessment: Optional[str]
    risk_debate_rounds: int

    # Phase 5 output
    portfolio_manager_report: Optional[str]
    final_action: Optional[str]

    # Metadata
    messages: list
