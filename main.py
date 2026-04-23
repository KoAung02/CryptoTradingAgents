"""
CryptoAgents — Python API entrypoint.

Usage:
    from main import CryptoAgents
    ca = CryptoAgents(debug=True)
    state, decision = ca.analyze("BTCUSDT", "2024-06-15")
"""

from cryptoagents.graph.crypto_graph import CryptoAgentsGraph


class CryptoAgents:
    def __init__(self, config: dict = None, debug: bool = False):
        self.graph = CryptoAgentsGraph(config=config, debug=debug)

    def analyze(self, symbol: str, timestamp: str) -> tuple[dict, dict]:
        """Run the full 13-agent pipeline. Returns (final_state, parsed_decision)."""
        return self.graph.propagate(symbol, timestamp)

    def record_outcome(self, state: dict, outcome: dict) -> None:
        """Store a resolved trade in memory for future reference.

        outcome = {
            "entry_price": 65000,
            "exit_price": 68000,
            "lessons_learned": "Momentum held through resistance",
        }
        """
        self.graph.reflect_and_remember(state, outcome)
