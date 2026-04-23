"""
Social + on-chain metrics using free public sources.
GitHub activity via GitHub API (free, no auth for public repos).
Social volume derived from Reddit + CryptoPanic.
"""
import requests
from .cache import get_cache
from .lunarcrush_client import get_social_metrics

TTL = 3600

SYMBOL_TO_GITHUB = {
    "BTCUSDT": "bitcoin/bitcoin",
    "ETHUSDT": "ethereum/go-ethereum",
    "SOLUSDT": "solana-labs/solana",
    "BNBUSDT": "bnb-chain/bsc",
    "ADAUSDT": "input-output-hk/cardano-node",
    "DOTUSDT": "paritytech/polkadot",
    "LINKUSDT": "smartcontractkit/chainlink",
    "UNIUSDT": "Uniswap/v3-core",
    "ARBUSDT": "OffchainLabs/arbitrum",
}


def get_social_volume(symbol: str, window: str = "7d") -> dict:
    metrics = get_social_metrics(symbol)
    return {
        "reddit_hot_posts": metrics.get("reddit_hot_count", 0),
        "social_sentiment": metrics.get("reddit_sentiment", "NEUTRAL"),
        "fear_greed": metrics.get("fear_greed_value", 50),
        "source": "reddit + alternative.me (free)",
    }


def get_sentiment_balance(symbol: str) -> dict:
    metrics = get_social_metrics(symbol)
    score = metrics.get("overall_sentiment_score", 50)
    balance = round((score - 50) / 50, 3)
    return {
        "sentiment_balance": balance,
        "interpretation": "POSITIVE" if balance > 0.1 else "NEGATIVE" if balance < -0.1 else "NEUTRAL",
        "source": "composite free sources",
    }


def get_github_activity(symbol: str, window: str = "30d") -> dict:
    cache = get_cache()
    cached = cache.get("github_activity", symbol=symbol)
    if cached:
        return cached

    repo = SYMBOL_TO_GITHUB.get(symbol.upper())
    if not repo:
        result = {"note": "No GitHub repo mapped for this asset", "source": "N/A"}
        cache.set(result, TTL, "github_activity", symbol=symbol)
        return result

    try:
        headers = {"User-Agent": "CryptoAgents/1.0", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(f"https://api.github.com/repos/{repo}/stats/commit_activity", headers=headers, timeout=10)
        data = r.json()
        if isinstance(data, list) and data:
            recent_weeks = data[-4:]
            total_commits = sum(w.get("total", 0) for w in recent_weeks)
            result = {
                "commit_count_30d": total_commits,
                "weekly_avg": round(total_commits / 4, 1),
                "trend": "ACTIVE" if total_commits > 50 else "QUIET",
                "source": "github.com (free)",
            }
        else:
            result = {"commit_count_30d": 0, "trend": "UNKNOWN", "source": "github.com"}
    except Exception as e:
        result = {"commit_count_30d": 0, "error": str(e), "source": "github.com"}

    cache.set(result, TTL, "github_activity", symbol=symbol)
    return result


def get_whale_alerts(symbol: str) -> list:
    from .glassnode_client import get_whale_transactions
    tx_data = get_whale_transactions(symbol)
    count = tx_data.get("tx_count_24h", 0) or tx_data.get("count_24h", 0)
    return [{"type": "on_chain_activity", "tx_count_24h": count, "source": tx_data.get("source", "estimated")}]
