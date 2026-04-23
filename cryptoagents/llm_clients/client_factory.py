import os
from langchain_ollama import ChatOllama


def get_llm(config: dict, mode: str = "quick"):
    """
    Returns a LangChain chat model.
    mode: 'quick' for analysts/trader, 'deep' for researchers/risk/portfolio manager.
    """
    provider = config.get("llm_provider", "ollama")
    base_url = config.get("ollama_base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    num_ctx = config.get("ollama_num_ctx", 8192)

    if mode == "deep":
        model = config.get("deep_think_llm", "qwen3.5:4b")
        temperature = config.get("temperature_deep", 0.3)
    else:
        model = config.get("quick_think_llm", "qwen3.5:4b")
        temperature = config.get("temperature_quick", 0.1)

    if provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY", "")
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=config.get("groq_max_tokens", 2048),
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        return ChatOpenAI(model=model, api_key=api_key, temperature=temperature,
                          base_url="https://api.deepseek.com",
                          timeout=60, max_retries=2)

    if provider == "together":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("TOGETHER_API_KEY", "")
        return ChatOpenAI(model=model, api_key=api_key, temperature=temperature,
                          base_url="https://api.together.xyz/v1",
                          timeout=60, max_retries=2)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY", "")
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=temperature)

    raise ValueError(f"Unsupported LLM provider: {provider}")
