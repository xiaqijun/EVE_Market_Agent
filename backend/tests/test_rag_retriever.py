import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.retriever import _rrf_fusion, hybrid_search


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
    semantic = [{"id": "doc1", "title": "A"}, {"id": "doc2", "title": "B"}, {"id": "doc3", "title": "C"}]
    keyword = [{"id": "doc3", "title": "C"}, {"id": "doc1", "title": "A"}, {"id": "doc2", "title": "B"}]
    result = _rrf_fusion(semantic, keyword, k=3)
    ids = [d["id"] for d in result]
    assert ids[0] == "doc1"
