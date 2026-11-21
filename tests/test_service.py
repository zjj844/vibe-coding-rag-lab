"""服务层测试：不起 HTTP，直接调 service —— 最快、最稳的一层。

这层测的是"接口契约"本身（返回哪些字段、异常怎么抛），
Web 框架换 Flask / FastAPI 都不影响这些断言。
"""
from __future__ import annotations

import pytest

from api import service


def test_health_schema():
    data = service.health()
    assert data["status"] == "ok"
    assert data["doc_count"] >= 8
    assert data["chunk_count"] >= data["doc_count"]
    assert isinstance(data["api_version"], str)
    assert "llm" in data


def test_ask_returns_contract_fields():
    data = service.ask("接口返回 401 应该先检查什么")
    for key in (
        "question", "answer", "citations", "refused",
        "retrieved", "citation_valid", "citation_problems", "latency_ms", "llm",
    ):
        assert key in data, f"缺少字段 {key}"
    assert data["refused"] is False
    assert data["citation_valid"] is True, data["citation_problems"]
    assert data["latency_ms"] >= 0


def test_ask_refuses_offdomain():
    data = service.ask("这本教材的作者和出版社是谁")
    assert data["refused"] is True
    assert data["citations"] == []
    assert data["citation_valid"] is True  # 拒答不需要引用，也算合法


def test_ask_rejects_empty_question():
    for bad in ("", "   ", None):
        with pytest.raises(ValueError):
            service.ask(bad)


def test_search_top_k():
    data = service.search("分块参数怎么定", top_k=3)
    assert len(data["hits"]) == 3
    scores = [h["score"] for h in data["hits"]]
    assert scores == sorted(scores, reverse=True)


def test_gold_set_shape():
    items = service.gold_set()
    assert len(items) == 12
    kinds = {i["type"] for i in items}
    assert kinds == {"hit", "boundary", "multi", "refuse"}
    for item in items:
        assert item["id"] and item["question"]


def test_evaluate_returns_gates():
    data = service.evaluate()
    assert "metrics" in data and "gates" in data
    assert data["all_pass"] is True, data["gates"]
    metric_names = {g["metric"] for g in data["gates"]}
    assert metric_names == {"recall_at_5", "mrr", "citation_valid", "refusal_acc"}
