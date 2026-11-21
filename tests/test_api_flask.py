"""HTTP 层测试：用 Flask 的 test_client，不需要真的起服务器、不需要网络。

这层保证"前端能拿到它期待的东西"：
状态码、JSON 字段、静态页面是否可访问、错误输入是否返回 400 而不是 500。
"""
from __future__ import annotations

import pytest

flask = pytest.importorskip("flask", reason="未安装 flask 时跳过 HTTP 层测试")

from api.app_flask import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["chunk_count"] > 0


def test_ask_endpoint(client):
    resp = client.post("/api/ask", json={"question": "libGL.so.1 缺失该用什么命令安装", "top_k": 3})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["answer"]
    assert body["citation_valid"] is True
    assert len(body["retrieved"]) == 3


def test_ask_empty_returns_400(client):
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_ask_without_body_returns_400(client):
    resp = client.post("/api/ask", json={})
    assert resp.status_code == 400


def test_search_endpoint(client):
    resp = client.post("/api/search", json={"question": "overlap 有什么用", "top_k": 2})
    assert resp.status_code == 200
    assert len(resp.get_json()["hits"]) == 2


def test_gold_endpoint(client):
    resp = client.get("/api/gold")
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) == 12


def test_eval_endpoint(client):
    resp = client.post("/api/eval", json={"chunk_size": 200, "overlap": 40, "top_k": 5})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["all_pass"] is True
    assert len(body["gates"]) == 4


def test_cors_header_present(client):
    """前端可能是 file:// 或 5173 端口，必须带 CORS 头，否则浏览器直接拦掉。"""
    resp = client.get("/api/health")
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


def test_landing_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "前端入口" in resp.get_data(as_text=True)


def test_vue_page_served(client):
    resp = client.get("/vue/")
    assert resp.status_code == 200
    assert "Vue 3" in resp.get_data(as_text=True)


def test_vendored_vue_is_served(client):
    """Vue 库必须能从本地拿到（不依赖 CDN），否则离线环境整页白屏。"""
    resp = client.get("/vendor/vue.global.prod.js")
    assert resp.status_code == 200
    assert len(resp.get_data()) > 100_000


def test_favicon_returns_no_content(client):
    """favicon 必须 204 而不是 404。

    否则浏览器控制台永远有一条 404，E2E 里"页面有 JS 错误就失败"的断言
    会变成永久噪声 —— 第一次跑 E2E 就是被它挡下来的。
    """
    resp = client.get("/favicon.ico")
    assert resp.status_code == 204
