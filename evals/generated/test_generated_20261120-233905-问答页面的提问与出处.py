"""本文件由 qa_agent 自动生成，请勿手工修改（改了就失去"生成质量"的可比性）。

生成时间：2026-11-20 23:39:05
需求依据：REQ-001-问答页面#s02#c00, REQ-001-问答页面#s06#c00, REQ-001-问答页面#s07#c00
"""

import re
import time

import pytest
from playwright.sync_api import expect

from pages.qa_page import QaPage, expect_healthy


def test_submit_question_renders_non_empty_answer(page):
    qa = QaPage(page)
    qa.open()
    qa.fill_question("libGL.so.1 缺失该用什么命令安装")
    qa.submit()

    expect(qa.answer_block).to_be_visible(timeout=60000)
    answer = qa.answer_block.inner_text().strip()
    assert len(answer) > 0


def test_citation_card_contains_number_and_similarity(page):
    qa = QaPage(page)
    qa.open()
    qa.fill_question("libGL.so.1 缺失该用什么命令安装")
    qa.submit()

    expect(qa.citation_cards.first).to_be_visible(timeout=60000)
    assert qa.citation_cards.count() >= 1

    first_card = qa.citation_cards.first.inner_text()
    assert re.search(r"\[\d+\]", first_card) is not None
    assert "相似度" in first_card


def test_citation_numbers_in_answer_exist_in_citation_list(page):
    qa = QaPage(page)
    qa.open()
    qa.fill_question("libGL.so.1 缺失该用什么命令安装")
    qa.submit()

    expect(qa.answer_block).to_be_visible(timeout=60000)
    answer = qa.answer_block.inner_text()

    refusal_markers = ("无法回答", "拒答", "没有找到")
    if any(marker in answer for marker in refusal_markers):
        pytest.skip("模型返回拒答，NFR-2 不适用")

    answer_numbers = re.findall(r"\[(\d+)\]", answer)
    assert len(answer_numbers) >= 1

    cards_text = "\n".join(
        qa.citation_cards.nth(i).inner_text()
        for i in range(qa.citation_cards.count())
    )
    card_numbers = set(re.findall(r"\[(\d+)\]", cards_text))

    for number in answer_numbers:
        assert number in card_numbers


def test_answer_returned_within_60_seconds(page):
    qa = QaPage(page)
    qa.open()
    qa.fill_question("libGL.so.1 缺失该用什么命令安装")

    start = time.monotonic()
    qa.submit()
    expect(qa.answer_block).to_be_visible(timeout=60000)
    elapsed = time.monotonic() - start

    assert elapsed < 60


def test_long_question_still_returns_answer(page):
    qa = QaPage(page)
    qa.open()
    long_question = "libGL.so.1 缺失该用什么命令安装 " * 20
    qa.fill_question(long_question)
    qa.submit()

    expect(qa.answer_block).to_be_visible(timeout=60000)
    answer = qa.answer_block.inner_text().strip()
    assert len(answer) > 0
