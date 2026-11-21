"""qa_agent 的离线测试：知识库、契约检查、生成结果校验。

这些测试**不联网、不启动浏览器**，所以能进 CI。
真正的浏览器执行在 web/e2e 里，需要单独跑。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent import contract, generator
from qa_agent.kb import RequirementKB

ROOT = Path(__file__).resolve().parent.parent


# ---------- ① 需求知识库 ----------
def test_kb_hierarchical_split():
    """需求必须按 H2/H3 切成模块，而不是按固定长度硬切。"""
    kb = RequirementKB()
    assert kb.doc_count == 3
    assert kb.chunk_count > kb.doc_count
    titles = [s.title for s in kb.sections]
    assert any(t.startswith("FR-2") for t in titles), "没切出 FR-2 小节"
    assert any("NFR" in t for t in titles)


def test_kb_tree_is_readable():
    """模块结构树要能给人核对（这是"切得对不对"的唯一人工把关点）。"""
    tree = RequirementKB().tree()
    assert "REQ-001" in tree and "FR-1" in tree
    assert tree.count("📄") == 3


def test_kb_search_returns_scored_chunks():
    hits = RequirementKB().search("提问与出处", top_k=3)
    assert len(hits) == 3
    assert hits[0]["score"] >= hits[-1]["score"]
    assert all(h["chunk_id"].startswith("REQ-") for h in hits)


# ---------- ③ 接口契约检查 ----------
def test_contract_knows_properties_vs_methods():
    members = contract.load_members()
    assert members["answer_block"].kind == "property"
    assert members["fill_question"].kind == "method"
    assert members["fill_question"].args == ["text"]


def test_contract_catches_property_called_as_method():
    """这就是第一版真实翻车的地方：属性被加了括号。"""
    bad = "from pages.qa_page import QaPage\ndef test_x(page):\n    qa = QaPage(page)\n    qa.health_badge()\n"
    violations = contract.check_code(bad)
    assert violations and "属性" in violations[0]


def test_contract_catches_unknown_member():
    bad = "def test_x(page):\n    qa = QaPage(page)\n    qa.click_submit()\n"
    violations = contract.check_code(bad)
    assert violations and "不存在" in violations[0]


def test_contract_catches_wrong_arg_count():
    bad = "def test_x(page):\n    qa = QaPage(page)\n    qa.fill_question()\n"
    violations = contract.check_code(bad)
    assert violations and "参数个数" in violations[0]


def test_contract_passes_on_real_handwritten_tests():
    """反向验证：我们手写的 E2E 用例必须通过契约检查（否则说明检查器太严）。"""
    code = (ROOT / "web" / "e2e" / "test_qa_ui.py").read_text(encoding="utf-8")
    assert contract.check_code(code) == []


# ---------- ② 生成结果校验 ----------
def test_extract_code_handles_fences():
    raw = "说明文字\n```python\nprint(1)\n```\n结束"
    assert generator.extract_code(raw) == "print(1)"


def test_validate_rejects_empty():
    ok, count, err = generator.validate_code("")
    assert not ok and count == 0 and "没有返回" in err


def test_validate_rejects_no_test_function():
    ok, count, err = generator.validate_code("x = 1\n")
    assert not ok and "test_" in err


def test_validate_rejects_syntax_error():
    ok, count, err = generator.validate_code("def test_x(page):\n  return (\n")
    assert not ok and "语法" in err


def test_validate_accepts_contract_clean_code():
    good = (
        "from pages.qa_page import QaPage, expect_healthy\n"
        "def test_x(page):\n"
        "    qa = QaPage(page)\n"
        "    qa.open()\n"
        "    expect_healthy(qa)\n"
        "    qa.fill_question('hello')\n"
        "    assert qa.answer_block.is_visible()\n"
    )
    ok, count, err = generator.validate_code(good)
    assert ok, err
    assert count == 1


# ---------- 落盘位置与夹具作用域 ----------
def test_root_conftest_provides_browser_fixtures():
    """回归防线：Agent 生成的用例落在 evals/generated/，pytest 的 conftest
    只对自身目录及子目录生效，所以 browser/page 夹具必须在**根目录** conftest 里。

    第一次跑生成用例时 5 条全是 `fixture 'page' not found`，就是因为夹具还在
    web/e2e/conftest.py 里。这条测试防止有人再把它们挪回去。
    """
    text = (ROOT / "conftest.py").read_text(encoding="utf-8")
    assert "def browser(" in text, "根 conftest 缺少 browser 夹具"
    assert "def page(" in text, "根 conftest 缺少 page 夹具"
