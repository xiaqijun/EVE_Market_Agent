from app.config import settings


async def rerank(query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
    if settings.rag_reranker_model == "none":
        return documents[:top_k]
    if settings.rag_reranker_model.startswith("local:"):
        return await _local_rerank(query, documents, top_k)
    return documents[:top_k]


async def _local_rerank(query: str, documents: list[dict], top_k: int) -> list[dict]:
    from sentence_transformers import CrossEncoder
    model = CrossEncoder("BAAI/bge-reranker-v2-m3")
    pairs = [(query, doc["content"]) for doc in documents]
    scores = model.predict(pairs)
    scored = list(zip(documents, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:top_k]]
