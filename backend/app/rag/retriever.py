import hashlib
import json
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

VERSION_WEIGHTS = {"current": 1.0, "recent": 0.5, "old": 0.1, "unmarked": 0.8}


async def hybrid_search(
    db: AsyncSession, query: str, top_k: int = 5,
    version_filter: str | None = None, item_group_ids: list[int] | None = None,
    source_filter: list[str] | None = None,
) -> list[dict]:
    cache_key = f"rag:cache:{hashlib.md5(query.encode()).hexdigest()[:16]}"
    r = redis.from_url(settings.redis_url)
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    semantic_results = await _semantic_search(
        db, query, top_k * 3, version_filter, item_group_ids, source_filter
    )
    keyword_results = await _keyword_search(
        db, query, top_k * 2, version_filter, item_group_ids, source_filter
    )
    merged = _rrf_fusion(semantic_results, keyword_results, top_k * 2)
    results = merged[:top_k]

    ttl = 86400 if results and results[0].get("doc_type") in ("mechanic", "wiki") else 3600
    r.setex(cache_key, ttl, json.dumps(results, default=str))
    return results


async def _semantic_search(db, query, top_k, version_filter, item_group_ids, source_filter):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedding_resp = await client.embeddings.create(
        model="text-embedding-3-small", input=query
    )
    query_embedding = embedding_resp.data[0].embedding

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
    conditions = ["rd.content ILIKE :q"]
    if version_filter:
        conditions.append(f"rd.version = '{version_filter}'")
    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT rd.id, rd.title, rd.content, rd.source, rd.doc_type, rd.version,
               0.5 AS rank
        FROM rag_documents rd
        WHERE {where}
        LIMIT :limit
    """)
    result = await db.execute(sql, {"q": f"%{query}%", "limit": top_k})
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
