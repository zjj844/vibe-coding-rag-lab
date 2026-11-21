"""Page Object：把"页面长什么样、怎么操作"与"断言什么"分开。

为什么要有 Page Object（PO 模式）：
- 页面改版时，只需要改这个文件里的选择器，测试用例一行都不用动；
- 用例读起来像自然语言（page.ask(...) / page.answer_text()），不是一堆 CSS 选择器。

选择器的取舍（实战教训）：
- 优先用**可见文案**（如按钮上的"提问（带出处）"）和可访问性属性，而不是 nth-child / 长 CSS 链；
- 退而求其次用 data-testid，但本项目没加，所以用 role + 文案；
- 反面教材：`.wrap > div:nth-child(3) > button` 这种，页面挪一格就全红。
"""
from __future__ import annotations

from playwright.sync_api import Page, expect


class QaPage:
    """Vue 版问答页面（/vue/）。"""

    def __init__(self, page: Page, base_url: str = "http://127.0.0.1:8000") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.url = f"{self.base_url}/vue/"

    # ---- 操作（动作）----
    def open(self) -> "QaPage":
        self.page.goto(self.url, wait_until="networkidle")
        return self

    def fill_question(self, text: str) -> "QaPage":
        self.page.get_by_placeholder("输入问题，例如：libGL.so.1 缺失该用什么命令安装").fill(text)
        return self

    def submit(self) -> "QaPage":
        # 真模型每次 3-6 秒，所以这里给足超时
        self.page.get_by_role("button", name="提问（带出处）").click()
        return self

    def open_tab(self, name: str) -> "QaPage":
        self.page.get_by_role("button", name=name, exact=True).click()
        return self

    def run_eval(self) -> "QaPage":
        self.open_tab("评估面板")
        self.page.get_by_role("button", name="跑一遍 gold set").click()
        return self

    # ---- 断言用到的读取器 ----
    @property
    def health_badge(self):
        return self.page.locator(".pill").first

    @property
    def answer_block(self):
        return self.page.locator(".answer")

    @property
    def citation_cards(self):
        return self.page.locator(".cite")

    @property
    def error_text(self):
        return self.page.locator(".err")


def expect_healthy(page: QaPage):
    """健康徽章必须出现 'API 正常'，且 3 秒内稳定（等接口返回）。"""
    expect(page.health_badge).to_contain_text("API 正常", timeout=5_000)
