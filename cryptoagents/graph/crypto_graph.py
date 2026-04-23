from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from cryptoagents.graph.state import AgentState
from cryptoagents.default_config import DEFAULT_CONFIG
from cryptoagents.memory.crypto_memory import CryptoSituationMemory
from cryptoagents.agents.utils.report_parser import extract_signal_rating, parse_final_decision

import cryptoagents.agents.analysts.onchain_analyst as onchain_agent
import cryptoagents.agents.analysts.market_analyst as market_agent
import cryptoagents.agents.analysts.sentiment_analyst as sentiment_agent
import cryptoagents.agents.analysts.news_analyst as news_agent
import cryptoagents.agents.researchers.bull_researcher as bull_agent
import cryptoagents.agents.researchers.bear_researcher as bear_agent
import cryptoagents.agents.researchers.research_manager as research_mgr_agent
import cryptoagents.agents.trader.trader as trader_agent
import cryptoagents.agents.risk_mgmt.aggressive_debator as aggressive_agent
import cryptoagents.agents.risk_mgmt.conservative_debator as conservative_agent
import cryptoagents.agents.risk_mgmt.neutral_debator as neutral_agent
import cryptoagents.agents.risk_mgmt.risk_manager as risk_mgr_agent
import cryptoagents.agents.managers.portfolio_manager as portfolio_agent

load_dotenv()


class CryptoAgentsGraph:
    def __init__(self, config: dict = None, debug: bool = False):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.debug = debug
        self.graph = self._build_graph()
        self._memory = CryptoSituationMemory(
            db_path=self.config.get("memory_db_path", "./crypto_memory"),
            top_k=self.config.get("memory_top_k", 3),
        )

    def _build_graph(self) -> StateGraph:
        cfg = self.config

        def node(fn):
            return lambda state: fn(state, cfg)

        g = StateGraph(AgentState)

        # Phase 1 — Analysts (sequential for context-window safety on small models)
        g.add_node("onchain_analyst", node(onchain_agent.run))
        g.add_node("market_analyst", node(market_agent.run))
        g.add_node("sentiment_analyst", node(sentiment_agent.run))
        g.add_node("news_analyst", node(news_agent.run))

        # Phase 2 — Research debate
        g.add_node("bull_researcher", node(bull_agent.run))
        g.add_node("bear_researcher", node(bear_agent.run))
        g.add_node("research_manager", node(research_mgr_agent.run))

        # Phase 3 — Trader
        g.add_node("trader", node(trader_agent.run))

        # Phase 4 — Risk debate
        g.add_node("aggressive_risk", node(aggressive_agent.run))
        g.add_node("conservative_risk", node(conservative_agent.run))
        g.add_node("neutral_risk", node(neutral_agent.run))
        g.add_node("risk_manager", node(risk_mgr_agent.run))

        # Phase 5 — Portfolio Manager
        g.add_node("portfolio_manager", node(portfolio_agent.run))

        # ── Edges ────────────────────────────────────────────────────────────

        # Phase 1: sequential analyst chain
        g.set_entry_point("onchain_analyst")
        g.add_edge("onchain_analyst", "market_analyst")
        g.add_edge("market_analyst", "sentiment_analyst")
        g.add_edge("sentiment_analyst", "news_analyst")

        # Phase 2: debate loop
        g.add_edge("news_analyst", "bull_researcher")
        g.add_edge("bull_researcher", "bear_researcher")
        g.add_conditional_edges(
            "bear_researcher",
            self._should_continue_research,
            {"continue": "bull_researcher", "done": "research_manager"},
        )
        g.add_edge("research_manager", "trader")

        # Phase 4: risk debate loop
        g.add_edge("trader", "aggressive_risk")
        g.add_edge("aggressive_risk", "conservative_risk")
        g.add_edge("conservative_risk", "neutral_risk")
        g.add_conditional_edges(
            "neutral_risk",
            self._should_continue_risk,
            {"continue": "aggressive_risk", "done": "risk_manager"},
        )

        # Phase 5
        g.add_edge("risk_manager", "portfolio_manager")
        g.add_edge("portfolio_manager", END)

        return g.compile()

    def _should_continue_research(self, state: AgentState) -> str:
        max_rounds = self.config.get("max_debate_rounds", 1)
        completed = len(state.get("bear_arguments", []))
        if completed < max_rounds:
            updated = {**state, "research_debate_rounds": completed}
            return "continue"
        return "done"

    def _should_continue_risk(self, state: AgentState) -> str:
        max_rounds = self.config.get("max_risk_discuss_rounds", 1)
        completed = len(state.get("neutral_risk_args", []))
        if completed < max_rounds:
            updated = {**state, "risk_debate_rounds": completed}
            return "continue"
        return "done"

    def propagate(self, symbol: str, timestamp: str) -> tuple[dict, dict]:
        """Run the full pipeline. Returns (final_state, parsed_decision)."""
        initial_state: AgentState = {
            "symbol": symbol,
            "timestamp": timestamp,
            "onchain_report": None,
            "market_report": None,
            "sentiment_report": None,
            "news_report": None,
            "bull_arguments": [],
            "bear_arguments": [],
            "investment_plan": None,
            "research_debate_rounds": 0,
            "trade_proposal": None,
            "aggressive_risk_args": [],
            "conservative_risk_args": [],
            "neutral_risk_args": [],
            "risk_assessment": None,
            "risk_debate_rounds": 0,
            "portfolio_manager_report": None,
            "final_action": None,
            "messages": [],
        }

        if self.debug:
            print(f"\n[CryptoAgents] Starting pipeline: {symbol} @ {timestamp}")

        final_state = self.graph.invoke(initial_state)
        decision = parse_final_decision(final_state.get("portfolio_manager_report", ""))

        if self.debug:
            print(f"[CryptoAgents] Final action: {decision.get('action')}")

        return final_state, decision

    def reflect_and_remember(self, state: dict, outcome: dict) -> None:
        """Call after trade resolution to store the situation in memory."""
        entry_price = outcome.get("entry_price", 0)
        exit_price = outcome.get("exit_price", 0)
        return_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
        win = return_pct > 0

        parsed = parse_final_decision(state.get("portfolio_manager_report", ""))

        situation = {
            "symbol": state.get("symbol", ""),
            "timestamp": state.get("timestamp", ""),
            "on_chain_signal": extract_signal_rating(state.get("onchain_report", "")),
            "technical_signal": extract_signal_rating(state.get("market_report", "")),
            "sentiment_signal": extract_signal_rating(state.get("sentiment_report", "")),
            "news_signal": extract_signal_rating(state.get("news_report", "")),
            "action_taken": parsed.get("action", "HOLD"),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return_pct": round(return_pct, 2),
            "outcome": "WIN" if win else "LOSS",
            "lessons_learned": outcome.get("lessons_learned", ""),
        }

        self._memory.add_situation(situation)

        if self.debug:
            print(f"[Memory] Stored situation: {situation['symbol']} {situation['outcome']} {return_pct:+.2f}%")
