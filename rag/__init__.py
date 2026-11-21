"""rag —— 一个最小可测的 RAG 骨架。

设计原则（这三条决定了它"能被测试"）：
1. 每个模块都是纯函数或纯对象，不读环境变量、不发网络请求 → 测试可以离线跑；
2. 嵌入器做成可替换接口（默认零依赖的哈希嵌入），真实项目里换成 bge 即可；
3. LLM 也做成可替换（默认离线抽取式假模型，可选 DeepSeek），
   这样 CI 里跑的一定是确定性结果。
"""
from .env import load_env, mask, proxy_url, urllib_opener

# 导入时就把 .env / Windows 用户级变量补齐。
# 为什么放在这里：所有入口（脚本、Flask、FastAPI、pytest）都会 import rag，
# 一处加载 = 全链路生效，不用每个脚本各写一遍。
load_env()

from .chunking import Chunk, chunk_text, normalize, split_sentences
from .embedding import HashingEmbedder, grams
from .store import VectorStore
from .retriever import Retriever
from .generator import (
    ExtractiveLLM,
    DeepSeekLLM,
    build_prompt,
    validate_citations,
)
from .pipeline import RagPipeline

__all__ = [
    "Chunk", "chunk_text", "normalize", "split_sentences",
    "HashingEmbedder", "grams", "VectorStore", "Retriever",
    "ExtractiveLLM", "DeepSeekLLM", "build_prompt", "validate_citations",
    "RagPipeline", "load_env", "mask", "proxy_url", "urllib_opener",
]
