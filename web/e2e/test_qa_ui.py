"""Vue 问答页面的端到端（E2E）测试。

运行方式（需要服务已启动）：
    # 终端 A
    python scripts/serve.py
    # 终端 B
    pip install playwright                     # 只需一次；走代理时加 --proxy http://127.0.0.1:7877
    python -m pytest web/e2e -v

为什么这层必须存在（接口测试覆盖不到的部分）：
- 接口返回 200 但页面渲染失败（今天真实发生过：React 黑屏，56 个测试全绿）
- 按钮点击没绑定、文案错位、前端报错
- 出处卡片渲染空数据
"""
from __future__ import annotations

import pytest

from pages.qa_page import QaPage, expect_healthy

pytestmark = pytest.mark.e2e


def test_health_badge_shows_api_ok(page):
    """页面打开后，健康徽章必须从"连接中…"变成"API 正常"。"""
    qa = QaPage(page).open()
    expect_healthy(qa)


def test_ask_shows_answer_with_citation(page):
    """核心功能：问一句，必须出现答案 + 至少一条出处。"""
    qa = QaPage(page).open()
    expect_healthy(qa)

    qa.fill_question("libGL.so.1 缺失该用什么命令安装").submit()

    # 答案块出现且非空
    qa.answer_block.wait_for(state="visible", timeout=60_000)  # 真模型 3-6 秒，给足余量
    answer = qa.answer_block.inner_text().strip()
    assert answer, "答案区是空的"
    assert "资料中未提及" not in answer, f"语料内问题被拒答了：{answer}"

    # 出处卡片必须存在，且含 [编号]
    assert qa.citation_cards.count() >= 1, "没有任何出处卡片（可溯源这条验收失败）"
    first_cite = qa.citation_cards.first.inner_text()
    assert "[" in first_cite and "]" in first_cite, f"出处卡片没有编号：{first_cite}"


def test_offdomain_question_is_refused(page):
    """语料外的问题：页面必须显示拒答，而不是编一个答案。"""
    qa = QaPage(page).open()
    expect_healthy(qa)

    qa.fill_question("这本教材的作者和出版社是谁").submit()
    qa.answer_block.wait_for(state="visible", timeout=60_000)
    assert "资料中未提及" in qa.answer_block.inner_text()


def test_eval_panel_runs_gates(page):
    """评估面板能跑出指标表，并且门禁全部通过。"""
    qa = QaPage(page).open()
    expect_healthy(qa)

    qa.run_eval()
    # 12 条用例 × 真模型，给 3 分钟
    page.get_by_text("全部门禁通过", exact=False).wait_for(timeout=180_000)
    rows = page.locator("table tbody tr")
    assert rows.count() >= 4, f"指标行数异常：{rows.count()}"
