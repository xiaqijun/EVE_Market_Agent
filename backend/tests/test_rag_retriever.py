import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.retriever import _rrf_fusion, hybrid_search, format_rag_context, conversation_search


# --- RRF Fusion Tests ---


def test_rrf_fusion_basic():
    semantic = [
        {"id": "doc1", "title": "A", "content": "..."},
        {"id": "doc2", "title": "B", "content": "..."},
    ]
    keyword = [
        {"id": "doc2", "title": "B", "content": "..."},
        {"id": "doc3", "title": "C", "content": "..."},
    ]
    result = _rrf_fusion(semantic, keyword, k=10)
    ids = [d["id"] for d in result]
    assert "doc2" in ids
    assert "doc1" in ids
    assert "doc3" in ids


def test_rrf_fusion_ranks_by_combined_score():
    semantic = [
        {"id": "doc1", "title": "A"},
        {"id": "doc2", "title": "B"},
    ]
    keyword = [
        {"id": "doc1", "title": "A"},
        {"id": "doc2", "title": "B"},
    ]
    result = _rrf_fusion(semantic, keyword, k=2)
    assert result[0]["id"] == "doc1"


def test_rrf_fusion_limits_results():
    semantic = [{"id": f"doc{i}", "title": f"D{i}"} for i in range(100)]
    keyword = []
    result = _rrf_fusion(semantic, keyword, k=5)
    assert len(result) == 5


def test_rrf_fusion_empty():
    result = _rrf_fusion([], [], k=5)
    assert result == []


def test_rrf_fusion_handles_duplicate_ids():
    semantic = [{"id": "doc1", "title": "A"}]
    keyword = [{"id": "doc1", "title": "A"}]
    result = _rrf_fusion(semantic, keyword, k=10)
    assert len(result) == 1


def test_rrf_fusion_respects_rrf_k():
    semantic = [{"id": "doc1", "title": "A"}]
    keyword = [{"id": "doc2", "title": "B"}]
    result = _rrf_fusion(semantic, keyword, k=10, rrf_k=60)
    assert len(result) == 2


def test_rrf_fusion_no_overlap():
    semantic = [{"id": "doc1", "title": "A"}, {"id": "doc2", "title": "B"}]
    keyword = [{"id": "doc3", "title": "C"}, {"id": "doc4", "title": "D"}]
    result = _rrf_fusion(semantic, keyword, k=4)
    ids = {d["id"] for d in result}
    assert ids == {"doc1", "doc2", "doc3", "doc4"}


def test_rrf_fusion_preserves_order():
    semantic = [
        {"id": "doc1", "title": "A"},
        {"id": "doc2", "title": "B"},
        {"id": "doc3", "title": "C"},
    ]
    keyword = [
        {"id": "doc3", "title": "C"},
        {"id": "doc1", "title": "A"},
        {"id": "doc2", "title": "B"},
    ]
    result = _rrf_fusion(semantic, keyword, k=3)
    ids = [d["id"] for d in result]
    assert ids[0] == "doc1"


# --- format_rag_context Tests ---


def test_format_rag_context_normal():
    results = [
        {"title": "交易基础", "content": "EVE市场交易的基本原理包括买入和卖出订单..."},
        {"title": "套利策略", "content": "跨区域套利是利用不同区域之间的价格差异..."},
    ]
    ctx = format_rag_context(results)
    assert "交易基础" in ctx
    assert "套利策略" in ctx
    assert "EVE市场交易" in ctx


def test_format_rag_context_empty():
    assert format_rag_context([]) == "无相关知识库参考"


def test_format_rag_context_truncates():
    long_content = "x" * 5000
    results = [{"title": "T", "content": long_content}]
    ctx = format_rag_context(results, max_chars=500)
    assert len(ctx) <= 500


def test_format_rag_context_missing_fields():
    results = [{"title": "Only Title"}]
    ctx = format_rag_context(results)
    assert "Only Title" in ctx


# --- Hybrid Search Integration Tests (mocked DB + embedding) ---


@pytest.mark.asyncio
async def test_hybrid_search_calls_rewrite_and_rerank():
    mock_db = AsyncMock()
    mock_semantic = [
        {
            "id": "d1",
            "title": "T1",
            "content": "C1",
            "source": "seed",
            "doc_type": "mechanic",
            "version": None,
            "similarity": 0.9,
        },
    ]
    mock_keyword = [
        {
            "id": "d1",
            "title": "T1",
            "content": "C1",
            "source": "seed",
            "doc_type": "mechanic",
            "version": None,
            "rank": 0.8,
        },
    ]

    with (
        patch(
            "app.rag.retriever._semantic_search", new_callable=AsyncMock, return_value=mock_semantic
        ) as mock_ss,
        patch(
            "app.rag.retriever._keyword_search", new_callable=AsyncMock, return_value=mock_keyword
        ) as mock_ks,
        patch(
            "app.rag.rewriter.rewrite_query", new_callable=AsyncMock, return_value="EVE 市场 交易"
        ) as mock_rw,
        patch(
            "app.rag.reranker.rerank",
            new_callable=AsyncMock,
            side_effect=lambda q, docs, k: docs[:k],
        ) as mock_rr,
        patch("app.rag.retriever.redis") as mock_redis_cls,
    ):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis_cls.from_url.return_value = mock_redis

        results = await hybrid_search(mock_db, "怎么交易", top_k=3, enable_rewrite=True)

        mock_rw.assert_called_once()
        mock_ss.assert_called_once()
        mock_ks.assert_called_once()
        mock_rr.assert_called_once()
        assert len(results) > 0
        assert results[0]["id"] == "d1"


@pytest.mark.asyncio
async def test_hybrid_search_rewrite_failure_falls_back():
    mock_db = AsyncMock()

    with (
        patch("app.rag.retriever._semantic_search", new_callable=AsyncMock, return_value=[]),
        patch("app.rag.retriever._keyword_search", new_callable=AsyncMock, return_value=[]),
        patch(
            "app.rag.rewriter.rewrite_query",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ),
        patch(
            "app.rag.reranker.rerank",
            new_callable=AsyncMock,
            side_effect=lambda q, docs, k: docs[:k],
        ),
        patch("app.rag.retriever.redis") as mock_redis_cls,
    ):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis_cls.from_url.return_value = mock_redis

        # Should not raise, falls back to original query
        results = await hybrid_search(mock_db, "test query", top_k=3, enable_rewrite=True)
        assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_uses_cache():
    mock_db = AsyncMock()
    cached_data = [{"id": "cached", "title": "Cached Doc"}]

    with patch("app.rag.retriever.redis") as mock_redis_cls:
        mock_redis = MagicMock()
        import json

        mock_redis.get.return_value = json.dumps(cached_data)
        mock_redis_cls.from_url.return_value = mock_redis

        results = await hybrid_search(mock_db, "cached query", enable_rewrite=False)
        assert results == cached_data


# --- Conversation Search Tests ---


@pytest.mark.asyncio
async def test_conversation_search_queries_correctly():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result._mapping = {
        "id": "conv1",
        "role": "user",
        "content": "怎么赚ISK",
        "created_at": None,
        "similarity": 0.85,
    }
    mock_db.execute = AsyncMock(return_value=[mock_result])

    with patch("app.rag.retriever._get_embedder") as mock_get:
        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = [0.1] * 384
        mock_get.return_value = mock_embedder

        results = await conversation_search(mock_db, "user-123", "赚ISK", top_k=3)
        mock_db.execute.assert_called_once()
        assert len(results) == 1
        assert results[0]["role"] == "user"


# --- Loader CRUD Tests ---


@pytest.mark.asyncio
async def test_add_document():
    from app.rag.loader import add_document

    with patch("app.rag.loader.async_session") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_doc = MagicMock()
        mock_doc.id = "test-id"
        mock_doc.title = "Test"
        mock_doc.content = "Content"
        mock_doc.source = "manual"
        mock_doc.doc_type = "wiki"
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch("app.rag.loader.RagDocument", return_value=mock_doc):
            with patch("app.rag.loader._embed_single", new_callable=AsyncMock):
                result = await add_document("Test", "Content", auto_embed=True)
                assert result["title"] == "Test"
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_document():
    from app.rag.loader import delete_document

    with patch("app.rag.loader.async_session") as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await delete_document("00000000-0000-0000-0000-000000000001")
        assert result is True
