DEFAULT_CONFIG = {
    # LLM Settings
    # providers: "ollama" | "groq" | "anthropic" | "openai" | "google"
    "llm_provider": "together",
    "deep_think_llm": "MiniMaxAI/MiniMax-M2.7",
    "quick_think_llm": "openai/gpt-oss-20b",
    "ollama_base_url": "http://localhost:11434",
    "temperature_deep": 0.3,
    "temperature_quick": 0.1,
    "ollama_num_ctx": 8192,

    # Debate Settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,

    # Data Settings
    "primary_exchange": "binance",
    "data_vendors": {
        "price_data": "binance",
        "onchain_data": "glassnode",
        "social_data": "lunarcrush",
        "news_data": "cryptopanic",
        "fundamentals": "messari",
        "fear_greed": "alternative_me",
        "defi_data": "defillama",
    },
    "cache_backend": "sqlite",
    "cache_ttl_seconds": 300,
    "cache_db_path": "./crypto_cache.db",

    # Risk Parameters
    "max_portfolio_heat": 0.40,
    "max_single_position_size": 0.25,
    "default_stop_loss_pct": 0.07,
    "use_kelly_criterion": True,
    "kelly_fraction": 0.25,

    # Memory
    "use_memory": True,
    "memory_db_path": "./crypto_memory",
    "memory_top_k": 3,

    # Operational
    "trading_mode": "paper",
    "base_currency": "USDT",
    "initial_capital": 10000.0,
    "debug": False,
}
