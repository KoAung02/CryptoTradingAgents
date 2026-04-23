from langchain_core.messages import HumanMessage, SystemMessage


def call_llm(llm, system_prompt: str, user_prompt: str) -> str:
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    return response.content


def format_data_section(title: str, data: dict | list) -> str:
    if isinstance(data, dict):
        lines = [f"  {k}: {v}" for k, v in data.items() if v is not None and k != "source"]
        return f"\n### {title}\n" + "\n".join(lines)
    elif isinstance(data, list):
        lines = []
        for item in data[:5]:
            if isinstance(item, dict):
                lines.append("  - " + ", ".join(f"{k}: {v}" for k, v in item.items() if k != "source"))
            else:
                lines.append(f"  - {item}")
        return f"\n### {title}\n" + "\n".join(lines)
    return f"\n### {title}\n  {data}"


def truncate_report(report: str, max_chars: int = 3000) -> str:
    if len(report) <= max_chars:
        return report
    return report[:max_chars] + "\n\n[Report truncated for context length]"


def get_data_interface(config: dict):
    """Returns historical interface if available, otherwise live DataInterface."""
    if config.get("_historical_interface") is not None:
        return config["_historical_interface"]
    from cryptoagents.dataflows.interface import DataInterface
    return DataInterface(config)
