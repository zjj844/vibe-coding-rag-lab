"""FastAPI 适配器：接口契约与 Flask 版完全一致，方便你项目里直接替换。

⚠️ 本机装不上 fastapi（无外网），这个文件**未在本机运行验证**。
   在有网环境执行 pip install fastapi uvicorn 后：
       uvicorn api.app_fastapi:app --reload --port 8000
   预期行为与 Flask 版一致（同样的 URL、同样的 JSON 字段）。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import service

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = FastAPI(title="RAG Eval Starter API", version=service.API_VERSION)

# 开发期放开跨域：Vite 跑在 5173，后端跑在 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = 5


class SearchRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = 5


class EvalRequest(BaseModel):
    chunk_size: int = 200
    overlap: int = 40
    top_k: int = 5


@app.get("/api/health")
def health():
    return service.health()


@app.post("/api/ask")
def ask(req: AskRequest):
    try:
        return service.ask(req.question, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/search")
def search(req: SearchRequest):
    try:
        return service.search(req.question, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/gold")
def gold():
    return {"items": service.gold_set()}


@app.post("/api/eval")
def evaluate(req: EvalRequest):
    return service.evaluate(chunk_size=req.chunk_size, overlap=req.overlap, top_k=req.top_k)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/vue/")
def vue_index():
    return FileResponse(WEB / "vue" / "index.html")


if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
