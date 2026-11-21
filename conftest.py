"""根级 conftest：把浏览器夹具放在这里，任何目录的测试都能用。

为什么必须放在根目录（真实踩过的坑）：
一开始 `browser` / `page` 夹具写在 `web/e2e/conftest.py` 里——pytest 的 conftest
**只对它所在目录及其子目录生效**。所以 Agent 把生成的用例落到 `evals/generated/` 后，
一跑就是 `fixture 'page' not found`，5 条全 ERROR。
夹具提到根目录后，`web/e2e/` 和 `evals/generated/` 都能用。

注意两个"不打扰"的设计：
- playwright 在夹具内部才导入（importorskip）：没装 playwright 时是 skip 而不是报错；
- 夹具是惰性的：只跑 `tests/` 里的单元测试时，完全不会碰浏览器。
"""
from __future__ import annotations

import os
import socket

import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")


def _port_open(host: str = "127.0.0.1", port: int = 8000, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def browser():
    playwright_api = pytest.importorskip(
        "playwright.sync_api", reason="未安装 playwright：pip install playwright"
    )
    if not _port_open():
        pytest.skip(f"服务未启动：请先在另一个终端运行 python scripts/serve.py（{BASE_URL}）")

    with playwright_api.sync_playwright() as p:
        # 优先复用系统自带 Edge，省掉 150MB 浏览器下载
        candidates = [
            ("msedge", lambda: p.chromium.launch(channel="msedge", headless=True)),
            ("chromium", lambda: p.chromium.launch(headless=True)),
        ]
        last_error: Exception | None = None
        for name, launch in candidates:
            try:
                br = launch()
                print(f"[e2e] 使用浏览器：{name}")
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                print(f"[e2e] {name} 不可用：{type(exc).__name__}")
        else:
            pytest.skip(f"没有可用浏览器，最后错误：{last_error}")
        yield br
        br.close()


@pytest.fixture()
def page(browser):
    """每个用例一个干净上下文；用例结束时若有 JS 错误则失败。

    白名单只放"浏览器自己产生的噪声"，绝不放"资源真的缺失"：
    - favicon.ico：浏览器自动请求（服务端已改成 204 兜底）
    - chrome-extension://：浏览器插件注入
    反面例子：app.js / app.css 的 404 **不能**进白名单 —— 那正是"黑屏"的真因。
    """
    ignore_keywords = ("favicon.ico", "chrome-extension://")

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    errors: list[str] = []

    def _record(text: str) -> None:
        if not any(k in text for k in ignore_keywords):
            errors.append(text)

    pg.on("console", lambda msg: _record(f"console.{msg.type}: {msg.text}") if msg.type == "error" else None)
    pg.on("pageerror", lambda exc: _record(f"pageerror: {exc}"))

    yield pg

    context.close()
    assert not errors, "页面出现 JS 错误（这类问题接口测试查不出来）：\n" + "\n".join(errors)
