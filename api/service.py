"""服务核心：不依赖任何 Web 框架，可被 pytest / Flask / FastAPI / CLI 直接调用。

设计理由：接口契约（返回什么字段）只在这里定义一次，
两个 Web 框架适配器、前端、测试全都对着它写——这就是"一套逻辑多个入口"。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag import DeepSeekLLM, RagPipeline  # noqa: E402
from rag.generator import validate_citations  # noqa: E402

API_VERSION = "1.0.0"

_PIPELINES: dict[tuple[int, int, int, str], RagPipeline] = {}


def _llm_choice() -> str:
    """由环境变量 RAG_LLM 决定用哪个生成器：空/stub = 离线假模型，deepseek = 真实模型。"""
    return (os.getenv("RAG_LLM") or "stub").strip().lower()


def _build_llm():
    """返回 None 表示用默认的离线抽取式模型。"""
    choice = _llm_choice()
    if choice in ("deepseek", "real"):
        llm = DeepSeekLLM()
        if not llm.available():
            raise RuntimeError("RAG_LLM=deepseek 但 DEEPSEEK_API_KEY 未设置（写进 .env）")
        return llm
    return None


def get_pipeline(chunk_size: int = 200, overlap: int = 40, top_k: int = 5) -> RagPipeline:
    """按参数缓存管道实例，避免每次请求都重建索引。

    缓存 key 里带上 LLM 选择：否则你切换模型后会拿到旧实例，指标对不上。
    """
    key = (chunk_size, overlap, top_k, _llm_choice())
    if key not in _PIPELINES:
        _PIPELINES[key] = RagPipeline(
            chunk_size=chunk_size, overlap=overlap, top_k=top_k, llm=_build_llm()
        )
    return _PIPELINES[key]


def health() -> dict:
    pipe = get_pipeline()
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "doc_count": pipe.doc_count,
        "chunk_count": pipe.chunk_count,
        "llm": getattr(pipe.llm, "name", "unknown"),
    }


def ask(question: str, top_k: int | None = None) -> dict:
    """完整问答：检索 + 生成 + 引用校验。返回结构即 API 契约。"""
    if not question or not question.strip():
        raise ValueError("question 不能为空")
    pipe = get_pipeline()
    started = time.perf_counter()
    result = pipe.ask(question, top_k=top_k)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    ok, problems = validate_citations(result["answer"], result["citations"])
    return {
        "question": result["question"],
        "answer": result["answer"],
        "citations": result["citations"],
        "refused": result["refused"],
        "retrieved": result["retrieved"],
        "citation_valid": ok,
        "citation_problems": problems,
        "latency_ms": latency_ms,
        "llm": result["llm"],
    }


def search(question: str, top_k: int = 5) -> dict:
    """只要检索结果，不生成——前端用它做"检索调试"面板。"""
    if not question or not question.strip():
        raise ValueError("question 不能为空")
    pipe = get_pipeline()
    started = time.perf_counter()
    hits = pipe.search(question, top_k=top_k)
    return {
        "question": question,
        "hits": hits,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def gold_set() -> list[dict]:
    import json

    path = ROOT / "gold_set.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(chunk_size: int = 200, overlap: int = 40, top_k: int = 5) -> dict:
    """跑一遍 gold set，返回指标 + 门禁判定（供前端"跑评估"按钮使用）。"""
    from evals.run_eval import GATES, run

    result = run(chunk_size, overlap, top_k)
    metrics = result["metrics"]
    gates = [
        {"metric": key, "value": metrics[key], "floor": floor, "pass": metrics[key] >= floor}
        for key, floor in GATES.items()
    ]
    return {
        "metrics": metrics,
        "gates": gates,
        "all_pass": all(g["pass"] for g in gates),
        "failures": result["failures"],
        "known_issues": result["known_issues"],
        "rows": result["rows"],
    }
