"""L1 确定性测试：分块。不依赖模型、不依赖网络，必须在 CI 里永远绿。"""
from __future__ import annotations

import pytest

from rag import chunk_text, normalize, split_sentences

LONG_SENT = "这是一句没有任何句号的长句" * 30  # 390 字


def test_chunk_length_never_exceeds_chunk_size():
    """防止回归：某次改分块逻辑后，块变得过长，把上下文挤爆。"""
    text = "第一句话。第二句话比第一句长一些，用来测试打包。第三句。\n\n第四段开始。第五句结束。"
    for size in (30, 50, 80):
        chunks = chunk_text(text, "d", chunk_size=size, overlap=size // 4)
        assert chunks, "不应产出空列表"
        for c in chunks:
            assert len(c.text) <= size, f"chunk {c.chunk_id} 超长: {len(c.text)} > {size}"


def test_overlap_increases_total_text():
    """防止回归：overlap 参数失效（改了代码但参数没生效）。"""
    text = "句子一。句子二。句子三。句子四。句子五。句子六。句子七。句子八。句子九。句子十。" * 4
    no_ov = chunk_text(text, "d", chunk_size=40, overlap=0)
    with_ov = chunk_text(text, "d", chunk_size=40, overlap=20)
    total_no = sum(len(c.text) for c in no_ov)
    total_with = sum(len(c.text) for c in with_ov)
    assert total_with > total_no, "overlap>0 时总字符数应因重复而增加"


def test_overlap_actually_shared_between_neighbours():
    """相邻块必须真的共享内容，否则 overlap 是个摆设。

    ⚠️ 两次踩坑记录（这就是"测试也会假绿"的实例）：
    1. 第一版用重复字符串，overlap 失效时断言仍通过；
    2. 第二版每句都以相同后缀结尾，overlap 失效时仍然通过。
    结论：测试数据必须**互不重复且后缀唯一**，否则断言测的是巧合，不是行为。
    """
    text = "".join(f"句子编号{i}的唯一标记为M{i}Z。" for i in range(1, 25))
    chunks = chunk_text(text, "d", chunk_size=40, overlap=20)
    assert len(chunks) >= 3
    tail = chunks[0].text[-8:]
    assert tail in chunks[1].text, (
        f"相邻块没有共享内容，overlap 可能失效。块0尾部={tail!r} 块1开头={chunks[1].text[:20]!r}"
    )



def test_hard_split_long_sentence():
    """单句超过 chunk_size 时必须硬切，且仍不超限。"""
    chunks = chunk_text(LONG_SENT, "d", chunk_size=100, overlap=0)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.text) <= 100


def test_chunks_stay_on_sentence_boundaries():
    """按句切：大部分块应以句末标点结尾（硬切块除外）。"""
    text = "第一句在这里。第二句在这里。第三句在这里。第四句在这里。第五句在这里。"
    chunks = chunk_text(text, "d", chunk_size=20, overlap=0)
    ends = [c.text[-1] for c in chunks]
    assert sum(1 for e in ends if e in "。！？\n") >= len(chunks) - 1


def test_invalid_params_raise():
    """参数非法要在入库前就炸，而不是静默产生垃圾块。"""
    with pytest.raises(ValueError):
        chunk_text("abc", "d", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("abc", "d", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_text("abc", "d", chunk_size=10, overlap=-1)


def test_empty_input_returns_empty():
    assert chunk_text("", "d") == []
    assert chunk_text("   \n\n  ", "d") == []


def test_normalize_and_split():
    assert normalize("a\r\n\r\n\r\nb") == "a\n\nb"
    sents = split_sentences("第一句。第二句！第三句？")
    assert len(sents) == 3


def test_chunk_ids_are_stable_and_unique():
    """块 id 必须稳定唯一，否则引用对不上、评估无法复现。"""
    text = "句子甲。句子乙。句子丙。句子丁。"
    a = chunk_text(text, "doc1", chunk_size=20, overlap=0)
    b = chunk_text(text, "doc1", chunk_size=20, overlap=0)
    ids_a = [c.chunk_id for c in a]
    assert ids_a == [c.chunk_id for c in b]
    assert len(ids_a) == len(set(ids_a))
    assert all(i.startswith("doc1#c") for i in ids_a)
