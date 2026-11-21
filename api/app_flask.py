"""Flask 适配器：本机现在就能跑（Flask 3.1.2 已安装）。

启动：python scripts/serve.py        或        python -m api.app_flask
打开：http://127.0.0.1:8000/          （落地页）
      http://127.0.0.1:8000/vue/      （Vue 3 前端，离线可用）
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from . import service

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = Flask(__name__, static_folder=None)


@app.after_request
def add_cors(response):
    """开发期允许任意来源：这样 file:// 打开 HTML 或 Vite 的 5173 端口也能调接口。"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@app.get("/api/health")
def api_health():
    return jsonify(service.health())


@app.get("/favicon.ico")
def favicon():
    """浏览器会自动请求 /favicon.ico；不返回 204 就永远有一条 404 控制台错误，
    会把 E2E 里"页面有 JS 错误就失败"的断言变成噪声（第一次跑 E2E 就撞上了）。"""
    return "", 204


@app.post("/api/ask")
def api_ask():
    data = _payload()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question 不能为空"}), 400
    try:
        return jsonify(service.ask(question, top_k=data.get("top_k")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/search")
def api_search():
    data = _payload()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question 不能为空"}), 400
    return jsonify(service.search(question, top_k=int(data.get("top_k") or 5)))


@app.get("/api/gold")
def api_gold():
    return jsonify({"items": service.gold_set()})


@app.post("/api/eval")
def api_eval():
    data = _payload()
    return jsonify(
        service.evaluate(
            chunk_size=int(data.get("chunk_size") or 200),
            overlap=int(data.get("overlap") or 40),
            top_k=int(data.get("top_k") or 5),
        )
    )


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/vue/")
@app.get("/vue")
def vue_index():
    return send_from_directory(WEB / "vue", "index.html")


@app.get("/react/")
@app.get("/react")
def react_index():
    """React 预构建版：由 esbuild 从 src/*.jsx 打包成 dist/app.js，可直接打开。"""
    return send_from_directory(WEB / "react" / "dist", "index.html")


@app.get("/<path:filename>")
def static_files(filename: str):
    return send_from_directory(WEB, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
