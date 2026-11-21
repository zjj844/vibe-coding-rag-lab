"""L2 检索质量：统计指标 + 门槛。

这一层不需要真实大模型，纯嵌入即可，所以：
- 不花钱、不 flaky（哈希嵌入是确定性的）→ 可以放进 CI，每次 push 都算真实指标。
这就是"确定性测试"和"质量评估"能共存的原因。
"""
from __future__ import annotations

import pytest


def _recall_at_k(pipeline, gold_set, k=5):
    total = hit = 0
    rr = 0.0
    for item in gold_set:
        if item["type"] == "refuse":
            continue
        total += 1
        docs = [h["doc_id"] for h in pipeline.search(item["question"], top_k=k)]
        rank = next((i + 1 for i, d in enumerate(docs) if d in item["gold_doc_ids"]), None)
        if rank:
            hit += 1
            rr += 1.0 / rank
    return hit / total, rr / total


@pytest.mark.slow
def test_recall_at_5_above_floor(pipeline, gold_set):
    """门槛值来自 EVAL.md 的实测结果，故意留 5 个百分点波动空间。"""
    recall, mrr = _recall_at_k(pipeline, gold_set, k=5)
    assert recall >= 0.75, f"Recall@5={recall:.3f} 低于门槛 0.75"
    assert mrr >= 0.55, f"MRR={mrr:.3f} 低于门槛 0.55"


@pytest.mark.slow
def test_refusal_accuracy_above_floor(pipeline, gold_set):
    """拒答准确率：语料外问题必须被拒。"""
    items = [i for i in gold_set if i["type"] == "refuse" and "预期失败" not in i.get("notes", "")]
    ok = sum(1 for i in items if pipeline.ask(i["question"])["refused"])
    acc = ok / len(items)
    assert acc >= 0.99, f"拒答准确率 {acc:.2f} 低于门槛 1.0（已排除标注为预期失败的样例）"


@pytest.mark.slow
def test_more_overlap_does_not_hurt_recall(pipeline_factory, gold_set):
    """调参断言：加 overlap 不应让召回变差（这是换参数的前提）。"""
    r0, _ = _recall_at_k(pipeline_factory(200, 0), gold_set)
    r40, _ = _recall_at_k(pipeline_factory(200, 40), gold_set)
    assert r40 >= r0 - 1e-9, f"overlap=40 ({r40:.3f}) 反而比 overlap=0 ({r0:.3f}) 差"
