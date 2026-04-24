import json
import os

DECISIONS_FILE = "./paper_decisions.json"


def load_decisions(path: str = DECISIONS_FILE) -> list:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_decisions(decisions: list, path: str = DECISIONS_FILE) -> None:
    with open(path, "w") as f:
        json.dump(decisions, f, indent=2, default=str)


def log_decision(
    date: str,
    symbol: str,
    action: str,
    price: float,
    decision: dict,
    outcome: str,
    path: str = DECISIONS_FILE,
) -> None:
    """Append one symbol's daily decision to the log."""
    decisions = load_decisions(path)
    decisions.append({
        "date": date,
        "symbol": symbol,
        "action": action,
        "price": price,
        "confidence": decision.get("confidence"),
        "stop_loss": decision.get("stop_loss"),
        "take_profit": decision.get("take_profit_1"),
        "position_size_pct": decision.get("position_size_pct"),
        "rationale": decision.get("rationale") or decision.get("reasoning"),
        "outcome": outcome,  # "opened", "closed_sell", "held", "already_open"
    })
    save_decisions(decisions, path)
