"""
CryptoSituationMemory — stores past trading situations and outcomes.
Uses ChromaDB for vector similarity search so the Trader can retrieve
comparable historical scenarios during decision-making.
"""
import json
import uuid
from datetime import datetime, timezone

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class CryptoSituationMemory:
    def __init__(self, db_path: str = "./crypto_memory", top_k: int = 3):
        self.top_k = top_k
        self.enabled = CHROMADB_AVAILABLE

        if not self.enabled:
            print("[Memory] ChromaDB not installed. Memory disabled. Run: pip install chromadb sentence-transformers")
            self._store = []
            return

        self._client = chromadb.PersistentClient(path=db_path)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._client.get_or_create_collection(
            name="crypto_situations",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    def add_situation(self, situation: dict) -> None:
        """Store a completed trading situation with its outcome."""
        if not self.enabled:
            self._store.append(situation)
            return

        doc_id = str(uuid.uuid4())
        summary = _build_summary(situation)
        metadata = {
            "symbol": situation.get("symbol", ""),
            "timestamp": situation.get("timestamp", ""),
            "on_chain_signal": situation.get("on_chain_signal", ""),
            "technical_signal": situation.get("technical_signal", ""),
            "sentiment_signal": situation.get("sentiment_signal", ""),
            "news_signal": situation.get("news_signal", ""),
            "action_taken": situation.get("action_taken", ""),
            "entry_price": float(situation.get("entry_price", 0)),
            "exit_price": float(situation.get("exit_price", 0)),
            "return_pct": float(situation.get("return_pct", 0)),
            "outcome": situation.get("outcome", "NEUTRAL"),
            "lessons_learned": situation.get("lessons_learned", ""),
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

        self._collection.add(
            ids=[doc_id],
            documents=[summary],
            metadatas=[metadata],
        )

    def query_similar(self, description: str, n_results: int = None) -> list[dict]:
        """Retrieve the most similar historical situations by description."""
        if not self.enabled:
            return self._store[-(n_results or self.top_k):]

        k = n_results or self.top_k
        count = self._collection.count()
        if count == 0:
            return []

        k = min(k, count)
        results = self._collection.query(
            query_texts=[description],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        situations = []
        for i, meta in enumerate(results["metadatas"][0]):
            situations.append({
                **meta,
                "situation_summary": results["documents"][0][i],
                "similarity": round(1 - results["distances"][0][i], 3),
            })

        return situations

    def count(self) -> int:
        if not self.enabled:
            return len(self._store)
        return self._collection.count()

    def format_for_trader(self, situations: list[dict]) -> str:
        """Format retrieved memories into a readable context block for the Trader LLM."""
        if not situations:
            return "No similar historical situations found in memory."

        lines = ["### Historical Memory — Similar Past Situations\n"]
        for i, s in enumerate(situations, 1):
            outcome_emoji = "WIN" if s.get("outcome") == "WIN" else "LOSS" if s.get("outcome") == "LOSS" else "NEUTRAL"
            lines.append(
                f"**Memory {i}** (similarity: {s.get('similarity', 'N/A')})\n"
                f"- Symbol: {s.get('symbol')} | Date: {s.get('timestamp', '')[:10]}\n"
                f"- Signals: On-Chain={s.get('on_chain_signal')} | "
                f"Technical={s.get('technical_signal')} | "
                f"Sentiment={s.get('sentiment_signal')} | "
                f"News={s.get('news_signal')}\n"
                f"- Action Taken: {s.get('action_taken')} @ ${s.get('entry_price', 0):,.2f}\n"
                f"- Outcome: {outcome_emoji} | Return: {s.get('return_pct', 0):+.2f}%\n"
                f"- Lesson: {s.get('lessons_learned', 'None recorded')}\n"
            )
        return "\n".join(lines)


def _build_summary(situation: dict) -> str:
    """Build a natural language summary of a situation for embedding."""
    return (
        f"{situation.get('symbol', 'UNKNOWN')} at {situation.get('timestamp', 'unknown time')}. "
        f"On-chain signal was {situation.get('on_chain_signal', 'NEUTRAL')}, "
        f"technical signal was {situation.get('technical_signal', 'NEUTRAL')}, "
        f"sentiment was {situation.get('sentiment_signal', 'NEUTRAL')}, "
        f"news signal was {situation.get('news_signal', 'NEUTRAL')}. "
        f"Action taken: {situation.get('action_taken', 'HOLD')} "
        f"at entry price {situation.get('entry_price', 0)}. "
        f"Outcome: {situation.get('outcome', 'NEUTRAL')} with "
        f"{situation.get('return_pct', 0):+.2f}% return. "
        f"Lessons: {situation.get('lessons_learned', 'none')}."
    )
