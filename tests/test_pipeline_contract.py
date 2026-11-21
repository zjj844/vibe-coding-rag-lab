"""L0 契约测试：管道对外行为。不测"答得好不好"，只测"接口没坏"。"""
from __future__ import annotations

import pytest

from rag import ExtractiveLLM, RagPipeline


def test_pipeline_builds_from_corpus(pipeline):
    assert pipeline.doc_count >= 8
    assert pipeline.chunk_count >= pipeline.doc_count


def test_ask_returns_schema(pipeline):
    result = pipeline.ask("接口返回 401 应该先检查什么")
    for key in ("question", "answer", "citations", "refused", "retrieved", "llm"):
        assert key in result
    assert isinstance(result["answer"], str) and result["answer"]
    assert isinstance(result["citations"], list)
    assert isinstance(result["refused"], bool)


def test_top_k_is_respected(pipeline):
    assert len(pipeline.search("分块参数怎么定", top_k=3)) == 3
    assert len(pipeline.search("分块参数怎么定", top_k=1)) == 1


def test_empty_question_raises(pipeline):
    with pytest.raises(ValueError):
        pipeline.ask("")
    with pytest.raises(ValueError):
        pipeline.ask("   ")


def test_same_question_same_answer(pipeline):
    """确定性：同一问题两次结果必须一致，否则测试会时红时绿。"""
    a = pipeline.ask("NLTK 报 LookupError 时目录该怎么放")
    b = pipeline.ask("NLTK 报 LookupError 时目录该怎么放")
    assert a["answer"] == b["answer"]
    assert [c["chunk_id"] for c in a["citations"]] == [c["chunk_id"] for c in b["citations"]]


def test_offdomain_question_is_refused(pipeline):
    result = pipeline.ask("这本教材的作者和出版社是谁")
    assert result["refused"] is True


def test_chunk_size_change_takes_effect():
    """参数真的传下去了：块越小，块数越多。"""
    small = RagPipeline(chunk_size=80, overlap=10)
    big = RagPipeline(chunk_size=400, overlap=40)
    assert small.chunk_count > big.chunk_count


def test_retrieved_scores_are_sorted(pipeline):
    hits = pipeline.search("引用溯源怎么保证不编", top_k=5)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_llm_is_injectable():
    """可替换性：换一个 LLM 实现，管道不需要改一行。"""
    class AlwaysRefuse(ExtractiveLLM):
        name = "always-refuse"

        def answer(self, question, hits):
            return {"answer": "资料中未提及。", "citations": [], "refused": True}

    pipe = RagPipeline(llm=AlwaysRefuse())
    result = pipe.ask("接口返回 401 应该先检查什么")
    assert result["refused"] is True
    assert result["llm"] == "always-refuse"
