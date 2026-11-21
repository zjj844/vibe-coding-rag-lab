"""本文件由 qa_agent 自动生成，请勿手工修改（改了就失去"生成质量"的可比性）。

生成时间：2026-11-20 23:38:07
需求依据：REQ-001-问答页面#s02#c00, REQ-001-问答页面#s06#c00, REQ-001-问答页面#s07#c00
"""

import re
import time

import pytest
from playwright.sync_api import expect

from pages.qa_page import QaPage, expect_healthy


QUESTION = "libGL.so.1 缺失该用什么命令安装"


def _ask(page, question=QUESTION):
    qa = QaPage(page)
    qa.open()
    expect_healthy(qa.health_badge())
    qa.fill_question(question)
    qa.submit()
    return qa


def test_answer_and_at_least_one_citation_displayed(page):
    """FR-2：点击「提问（带出处）」后展示回答正文且至少一条出处卡片。"""
    qa = _ask(page)

    answer = qa.answer_block()
    expect(answer).to_be_visible(timeout=60000)
    assert answer.inner_text().strip() != "", "回答正文为空"

    cards = qa.citation_cards()
    expect(cards.first).to_be_visible(timeout=60000)
    assert cards.count() >= 1, "非拒答回答必须至少带一条出处卡片"


def test_citation_card_contains_number_similarity_and_snippet(page):
    """FR-2：每条出处卡片包含编号 [n]、相似度与原文片段。"""
    qa = _ask(page)

    cards = qa.citation_cards()
    expect(cards.first).to_be_visible(timeout=60000)
    count = cards.count()
    assert count >= 1, "未展示任何出处卡片"

    for i in range(count):
        text = cards.nth(i).inner_text()
        assert re.search(r"\[\d+\]", text), f"第 {i + 1} 条出处缺少编号 [n]：{text!r}"
        assert "相似度" in text, f"第 {i + 1} 条出处缺少相似度：{text!r}"
        assert len(text.strip()) > 10, f"第 {i + 1} 条出处缺少原文片段：{text!r}"


def test_answer_citation_numbers_all_exist_in_citation_list(page):
    """NFR-2：回答中出现的出处编号必须都能在出处列表中找到。"""
    qa = _ask(page)

    answer = qa.answer_block()
    expect(answer).to_be_visible(timeout=60000)
    answer_text = answer.inner_text()

    nums_in_answer = set(re.findall(r"\[(\d+)\]", answer_text))
    assert nums_in_answer, f"非拒答回答未标注任何出处编号：{answer_text!r}"

    cards = qa.citation_cards()
    expect(cards.first).to_be_visible(timeout=60000)
    card_nums = set()
    for i in range(cards.count()):
        card_nums.update(re.findall(r"\[(\d+)\]", cards.nth(i).inner_text()))

    assert card_nums, "出处列表中没有解析到任何编号"
    missing = nums_in_answer - card_nums
    assert not missing, f"回答引用了出处列表中不存在的编号：{sorted(missing)}"


def test_answer_returned_within_60_seconds(page):
    """NFR-1：单次问答必须在 60 秒内返回，且返回内容非空。"""
    qa = QaPage(page)
    qa.open()
    expect_healthy(qa.health_badge())
    qa.fill_question(QUESTION)

    start = time.monotonic()
    qa.submit()
    expect(qa.answer_block()).to_be_visible(timeout=60000)
    elapsed = time.monotonic() - start

    assert elapsed < 60.0, f"单次问答耗时 {elapsed:.1f}s，超过 60s 失败阈值"
    assert qa.answer_block().inner_text().strip() != "", "超时返回但回答正文为空"


def test_empty_question_is_rejected_with_error_text(page):
    """边界：空问题提交后给出错误提示，且不产生回答与出处。"""
    qa = QaPage(page)
    qa.open()
    expect_healthy(qa.health_badge())

    qa.fill_question("")
    qa.submit()

    error = qa.error_text()
    expect(error).to_be_visible(timeout=10000)
    assert error.inner_text().strip() != "", "空问题未给出任何错误提示文案"
    assert qa.citation_cards().count() == 0, "空问题不应产生出处卡片"
