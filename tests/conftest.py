"""pytest 共享夹具。

设计要点：
- pipeline 夹具默认 chunk_size=200 / overlap=40；需要不同参数时用 pipeline_factory，
  避免测试之间互相污染；
- gold set 只加载一次，供不同测试文件复用（这就是"一组数据两处用"的一半）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ⚠️ 关键：测试永远用离线假模型。
# 因为 .env 里一旦打开 RAG_LLM=deepseek，测试就会真的去调 API——
# 花钱、变慢、受网络影响，还会让"确定性测试"名不副实。
# 真模型的验证请走 `python evals/run_eval.py --llm deepseek`，不要混进 pytest。
os.environ["RAG_LLM"] = "stub"


@pytest.fixture()
def ws_tmp():
    """工作区内的临时目录（替代 pytest 的 tmp_path）。

    为什么不用 tmp_path：它写在系统临时目录（C:\\Users\\...\\Temp），
    在受限环境（沙箱、权限异常的 Windows、某些 CI 容器）会直接 PermissionError。
    换成工作区内目录，测试在任何环境都能跑。
    """
    import shutil

    path = Path(__file__).resolve().parent / "_tmp_ws"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)

from rag import RagPipeline  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "gold_set.jsonl"


@pytest.fixture(scope="session")
def gold_set() -> list[dict]:
    items = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


@pytest.fixture(scope="session")
def pipeline_factory():
    cache: dict[tuple[int, int], RagPipeline] = {}

    def _make(chunk_size: int = 200, overlap: int = 40) -> RagPipeline:
        key = (chunk_size, overlap)
        if key not in cache:
            cache[key] = RagPipeline(chunk_size=chunk_size, overlap=overlap)
        return cache[key]

    return _make


@pytest.fixture(scope="session")
def pipeline(pipeline_factory) -> RagPipeline:
    return pipeline_factory()
