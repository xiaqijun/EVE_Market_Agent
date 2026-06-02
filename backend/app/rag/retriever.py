import hashlib
import json
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

VERSION_WEIGHTS = {"current": 1.0, "recent": 0.5, "old": 0.1, "unmarked": 0.8}


async def hybrid_search(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    version_filter: str | None = None,
    item_group_ids: list[int] | None = None,
    source_filter: list[str] | None = None,
    enable_rewrite: bool = True,
) -> list[dict]:
    """Hybrid search: semantic (pgvector) + keyword (tsvector) with RRF fusion.

    Integrates optional query rewriting and reranking.
    Results are cached in Redis.
    """
    top_k = top_k or settings.rag_top_k

    # Cache lookup
    cache_key = f"rag:cache:{hashlib.md5(query.encode()).hexdigest()[:16]}"
    r = redis.from_url(settings.redis_url)
    try:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # Query rewriting
    search_query = query
    if enable_rewrite:
        from app.rag.rewriter import rewrite_query

        try:
            search_query = await rewrite_query(query)
        except Exception:
            search_query = query

    # Parallel retrieval
    import asyncio

    semantic_task = _semantic_search(
        db, search_query, top_k * 3, version_filter, item_group_ids, source_filter
    )
    keyword_task = _keyword_search(
        db, search_query, top_k * 2, version_filter, item_group_ids, source_filter
    )
    semantic_results, keyword_results = await asyncio.gather(semantic_task, keyword_task)

    # RRF fusion
    merged = _rrf_fusion(semantic_results, keyword_results, top_k * 3)

    # Reranking
    from app.rag.reranker import rerank

    try:
        results = await rerank(search_query, merged, top_k)
    except Exception:
        results = merged[:top_k]

    # Cache
    ttl = 86400 if results and results[0].get("doc_type") in ("mechanic", "wiki") else 3600
    try:
        r.setex(cache_key, ttl, json.dumps(results, default=str))
    except Exception:
        pass

    return results


async def conversation_search(
    db: AsyncSession, user_id: str, query: str, top_k: int = 5
) -> list[dict]:
    """Search conversation memory for relevant past exchanges."""
    import asyncio

    embedder = _get_embedder()
    query_embedding = await asyncio.to_thread(embedder.encode, query)

    sql = text("""
        SELECT cm.id, cm.role, cm.content, cm.created_at,
               1 - (cm.embedding <=> :embedding) AS similarity
        FROM conversation_memory cm
        WHERE cm.user_id = :user_id
          AND cm.embedding IS NOT NULL
        ORDER BY cm.embedding <=> :embedding
        LIMIT :limit
    """)
    result = await db.execute(
        sql,
        {
            "user_id": user_id,
            "embedding": str(query_embedding),
            "limit": top_k,
        },
    )
    return [dict(row._mapping) for row in result]


def format_rag_context(results: list[dict], max_chars: int = 2000) -> str:
    """Format RAG search results into a context string for LLM prompts."""
    if not results:
        return "无相关知识库参考"
    lines = []
    for r in results:
        title = r.get("title", "")
        content = r.get("content", "")[:200]
        lines.append(f"- {title}: {content}")
    context = "\n".join(lines)
    return context[:max_chars]


def _get_embedder():
    """Get or create a cached local embedding model."""
    if not hasattr(_get_embedder, "_model"):
        model_name = settings.rag_embedding_model.replace("local:", "")
        from sentence_transformers import SentenceTransformer

        _get_embedder._model = SentenceTransformer(model_name)
    return _get_embedder._model


async def _semantic_search(db, query, top_k, version_filter, item_group_ids, source_filter):
    import asyncio

    embedder = _get_embedder()
    query_embedding = await asyncio.to_thread(embedder.encode, query)

    conditions = ["rd.embedding IS NOT NULL"]
    if version_filter:
        conditions.append(f"rd.version = '{version_filter}'")
    if item_group_ids:
        ids = ",".join(map(str, item_group_ids[:100]))
        conditions.append(f"rd.related_item_groups && ARRAY[{ids}]")
    if source_filter:
        sources = ",".join(f"'{s}'" for s in source_filter)
        conditions.append(f"rd.source IN ({sources})")

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT rd.id, rd.title, rd.content, rd.source, rd.doc_type, rd.version,
               1 - (rd.embedding <=> :embedding) AS similarity
        FROM rag_documents rd
        WHERE {where}
        ORDER BY rd.embedding <=> :embedding
        LIMIT :limit
    """)
    result = await db.execute(sql, {"embedding": str(query_embedding), "limit": top_k})
    return [dict(row._mapping) for row in result]


async def _keyword_search(db, query, top_k, version_filter, item_group_ids, source_filter):
    """Full-text search using PostgreSQL tsvector (simple config, no external deps)."""
    conditions = [
        "to_tsvector('simple', coalesce(rd.title, '') || ' ' || coalesce(rd.content, '')) "
        "@@ plainto_tsquery('simple', :q)"
    ]
    if version_filter:
        conditions.append(f"rd.version = '{version_filter}'")
    if item_group_ids:
        ids = ",".join(map(str, item_group_ids[:100]))
        conditions.append(f"rd.related_item_groups && ARRAY[{ids}]")
    if source_filter:
        sources = ",".join(f"'{s}'" for s in source_filter)
        conditions.append(f"rd.source IN ({sources})")

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT rd.id, rd.title, rd.content, rd.source, rd.doc_type, rd.version,
               ts_rank(to_tsvector('simple', coalesce(rd.title, '') || ' ' || coalesce(rd.content, '')),
                       plainto_tsquery('simple', :q)) AS rank
        FROM rag_documents rd
        WHERE {where}
        ORDER BY rank DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"q": query, "limit": top_k})
    return [dict(row._mapping) for row in result]


def _rrf_fusion(semantic: list[dict], keyword: list[dict], k: int, rrf_k: int = 60) -> list[dict]:
    scores = {}
    docs = {}
    for rank, doc in enumerate(semantic):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (rrf_k + rank + 1)
        docs[doc_id] = doc
    for rank, doc in enumerate(keyword):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (rrf_k + rank + 1)
        docs[doc_id] = doc
    sorted_ids = sorted(scores, key=scores.get, reverse=True)[:k]
    return [docs[doc_id] for doc_id in sorted_ids]
