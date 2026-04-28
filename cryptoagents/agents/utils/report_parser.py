import re


def parse_final_decision(report: str) -> dict:
    """Extract structured data from the Portfolio Manager's final report."""
    result = {
        "action": "HOLD",
        "entry": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "position_size_pct": None,
        "confidence": None,
        "raw_report": report,
    }

    action_match = re.search(r"ACTION:\s*(BUY|SELL|HOLD)", report, re.IGNORECASE)
    if action_match:
        result["action"] = action_match.group(1).upper()

    entry_match = re.search(r"Entry[:\s]+\$?([\d,]+\.?\d*)", report, re.IGNORECASE)
    if entry_match:
        result["entry"] = float(entry_match.group(1).replace(",", ""))

    sl_match = re.search(r"Stop.?Loss[:\s]+\$?([\d,]+\.?\d*)", report, re.IGNORECASE)
    if sl_match:
        result["stop_loss"] = float(sl_match.group(1).replace(",", ""))

    tp1_match = re.search(r"Take.?Profit.?1[:\s]+\$?([\d,]+\.?\d*)", report, re.IGNORECASE)
    if tp1_match:
        result["take_profit_1"] = float(tp1_match.group(1).replace(",", ""))

    tp2_match = re.search(r"Take.?Profit.?2[:\s]+\$?([\d,]+\.?\d*)", report, re.IGNORECASE)
    if tp2_match:
        result["take_profit_2"] = float(tp2_match.group(1).replace(",", ""))

    size_match = re.search(r"Position.?Size[:\s]+([\d.]+)%", report, re.IGNORECASE)
    if size_match:
        result["position_size_pct"] = float(size_match.group(1))

    conf_match = re.search(r"Confidence.?Score[:\s]+(\d+)", report, re.IGNORECASE)
    if conf_match:
        result["confidence"] = int(conf_match.group(1))

    rationale_match = re.search(r"###\s*Rationale\s*\n(.*?)(?=\n###|\Z)", report, re.IGNORECASE | re.DOTALL)
    if rationale_match:
        result["rationale"] = rationale_match.group(1).strip()[:500]

    return result


def extract_signal_rating(report: str) -> str:
    """Extract BULLISH / NEUTRAL / BEARISH rating from an analyst report."""
    match = re.search(r"Rating[:\s]+(BULLISH|NEUTRAL|BEARISH)", report, re.IGNORECASE)
    return match.group(1).upper() if match else "NEUTRAL"


def extract_confidence(report: str) -> str:
    match = re.search(r"Confidence[:\s]+(HIGH|MEDIUM|LOW)", report, re.IGNORECASE)
    return match.group(1).upper() if match else "MEDIUM"
