"""L1 确定性测试：引用与提示词。

这组是最值钱的一组——它把"回答可溯源"从口号变成机器检查。
"""
from __future__ import annotations

import pytest

from rag import build_prompt, validate_citations


def test_validate_rejects_out_of_range_citation():
    """防止回归：模型编了 [5]，但只给了 1 条出处。"""
    ok, problems = validate_citations("答案是 A。 [5]", [{"index": 1}])
    assert not ok
    assert any("越界" in p for p in problems)


def test_validate_rejects_answer_without_citation():
    """防止回归：有答案却没有任何出处（最隐蔽的幻觉形态）。"""
    ok, problems = validate_citations("答案是 A。", [{"index": 1}])
    assert not ok
    assert any("没有任何" in p for p in problems)


def test_validate_rejects_empty_citation_list():
    ok, problems = validate_citations("答案是 A。 [1]", [])
    assert not ok


def test_validate_accepts_good_answer():
    ok, problems = validate_citations("答案是 A。 [1]", [{"index": 1}])
    assert ok, problems


def test_validate_accepts_refusal():
    """拒答是合法的：不需要引用。"""
    ok, problems = validate_citations("资料中未提及。", [])
    assert ok, problems


def test_duplicate_citation_is_allowed():
    """重复引用同一份资料是合法的（真实模型常这么写）。

    ⚠️ 这条测试原本断言"重复=非法"，换真模型后发现那是**假规则**：
    同一份资料支撑两句话是正常写作，把它判非法会让 citation_valid 从 1.0 掉到 0.33。
    测试本身写错了假设——这类"测试编码了错误假设"比 bug 更隐蔽。
    """
    ok, problems = validate_citations("A。[1] B。[1]", [{"index": 1}])
    assert ok, problems


def test_build_prompt_numbers_every_hit():
    """编号必须从 1 开始且与 hits 一一对应，否则模型引用必然错位。"""
    hits = [
        {"doc_id": "d1", "chunk_id": "d1#c00", "text": "内容一", "score": 0.9},
        {"doc_id": "d2", "chunk_id": "d2#c01", "text": "内容二", "score": 0.8},
    ]
    prompt = build_prompt("问题？", hits)
    assert "[1]" in prompt and "[2]" in prompt
    assert "内容一" in prompt and "内容二" in prompt
    assert "资料中未提及" in prompt  # 拒答策略必须写进提示词


@pytest.mark.parametrize("question", [
    "清华镜像装 torch 失败是什么原因",
    "libGL.so.1 缺失该用什么命令安装",
    "分块的 overlap 设成 0 会有什么问题",
])
def test_pipeline_answers_always_have_valid_citations(pipeline, question):
    """端到端硬门禁：任何一条回答的引用都必须合法。"""
    result = pipeline.ask(question)
    ok, problems = validate_citations(result["answer"], result["citations"])
    assert ok, f"{question} -> {problems}"


@pytest.mark.parametrize("question", [
    "这本教材的作者和出版社是谁",
    "作者的邮箱地址是多少",
])
def test_refusal_has_no_citations(pipeline, question):
    result = pipeline.ask(question)
    assert result["refused"] is True
    assert result["citations"] == []
    assert "资料中未提及" in result["answer"]
