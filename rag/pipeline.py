"""编排层：把 ①入库 ②检索 ③生成 串起来，暴露两个方法给测试和评估。

- search(question)：只做检索，供 L2 检索质量指标使用（不花钱、可进 CI）
- ask(question)：检索 + 生成 + 引用，供 L3 答案质量评估使用
"""
from __future__ import annotations

from pathlib import Path

from .chunking import chunk_text
from .embedding import HashingEmbedder
from .generator import ExtractiveLLM
from .retriever import Retriever
from .store import VectorStore


class RagPipeline:
    def __init__(
        self,
        corpus_dir: str | Path | None = None,
        chunk_size: int = 200,
        overlap: int = 40,
        top_k: int = 5,
        embedder: HashingEmbedder | None = None,
        llm=None,
    ) -> None:
        self.corpus_dir = Path(corpus_dir) if corpus_dir else Path(__file__).resolve().parent.parent / "corpus"
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.top_k = top_k
        self.embedder = embedder or HashingEmbedder()
        self.llm = llm or ExtractiveLLM()
        self.store = VectorStore()
        self.retriever = Retriever(self.store, self.embedder, top_k=top_k)
        self.doc_count = 0
        self.chunk_count = 0
        self.build()

    def _read_corpus(self) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        for path in sorted(self.corpus_dir.glob("*.md")):
            docs.append((path.stem, path.read_text(encoding="utf-8")))
        return docs

    def build(self) -> "RagPipeline":
        """入库：读文档 → 分块 → 向量化 → 写向量库。"""
        docs = self._read_corpus()
        self.doc_count = len(docs)
        for doc_id, text in docs:
            chunks = chunk_text(text, doc_id, chunk_size=self.chunk_size, overlap=self.overlap)
            vectors = [self.embedder.embed(c.text) for c in chunks]
            self.store.add(chunks, vectors)
        self.chunk_count = len(self.store)
        return self

    # ---- L2：只检索，不生成 ----
    def search(self, question: str, top_k: int | None = None) -> list[dict]:
        return self.retriever.search(question, top_k=top_k)

    # ---- L3：完整问答 ----
    def ask(self, question: str, top_k: int | None = None) -> dict:
        hits = self.search(question, top_k=top_k)
        result = self.llm.answer(question, hits)
        return {
            "question": question,
            "answer": result["answer"],
            "citations": result["citations"],
            "refused": result["refused"],
            "retrieved": [
                {"doc_id": h["doc_id"], "chunk_id": h["chunk_id"], "score": h["score"]}
                for h in hits
            ],
            "llm": getattr(self.llm, "name", "unknown"),
        }
