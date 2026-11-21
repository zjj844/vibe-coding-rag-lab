"""评估入口：跑 gold set → 打印指标 → 写 EVAL.md + artifacts JSON。

用法：
    python evals/run_eval.py                       # 默认参数
    python evals/run_eval.py --chunk-size 200 --overlap 0
    python evals/run_eval.py --md                  # 同时刷新 EVAL.md 里的表格

设计说明：
同一份 gold set 既驱动 pytest 断言（tests/），也驱动这里的指标表（evals/）——
这就是"一组数据两处用"，避免标注两遍。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台默认 GBK，打印中文和符号会炸，先切 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag import DeepSeekLLM, RagPipeline, validate_citations  # noqa: E402

GOLD_PATH = ROOT / "gold_set.jsonl"
EVAL_MD = ROOT / "EVAL.md"
ARTIFACT_DIR = ROOT / "evals" / "artifacts"

START = "<!-- EVAL_TABLE_START -->"
END = "<!-- EVAL_TABLE_END -->"

# 门槛：确定性指标设硬门禁，统计指标留下限（并留波动空间）
GATES = {"recall_at_5": 0.75, "mrr": 0.55, "citation_valid": 1.0, "refusal_acc": 1.0}


def load_gold() -> list[dict]:
    items = []
    for line in GOLD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def run(chunk_size: int, overlap: int, top_k: int, llm=None) -> dict:
    pipe = RagPipeline(chunk_size=chunk_size, overlap=overlap, top_k=top_k, llm=llm)
    rows, failures = [], []

    recall_total = recall_hit = 0
    rr_sum = 0.0
    evidence_total = evidence_hit = 0
    cite_total = cite_ok = 0
    answer_total = answer_ok = 0
    refuse_total = refuse_ok = 0          # 严格口径：排除已登记的已知缺陷
    refuse_all_total = refuse_all_ok = 0  # 全量口径：含已知缺陷
    known_issues = []

    for item in load_gold():
        q, kind = item["question"], item["type"]
        known_issue = "预期失败" in item.get("notes", "")
        hits = pipe.search(q, top_k=top_k)
        docs = [h["doc_id"] for h in hits]
        result = pipe.ask(q, top_k=top_k)

        if kind == "refuse":
            ok = result["refused"]
            refuse_all_total += 1
            refuse_all_ok += 1 if ok else 0
            if known_issue:
                known_issues.append(
                    f"{item['id']}（已登记缺陷）{item['notes']} → 实际回答：{result['answer'][:50]}"
                )
                refuse_mark = "⚠️已登记"
            else:
                refuse_total += 1
                refuse_ok += 1 if ok else 0
                refuse_mark = "✅" if ok else "❌"
                if not ok:
                    failures.append(
                        f"{item['id']} 应拒答却回答了：{result['answer'][:60]}"
                        f"（命中文档 {docs[0] if docs else '无'}）"
                    )
            rows.append((item["id"], kind, "-", "-", "-", refuse_mark))
            continue

        answer_total += 1
        if not result["refused"]:
            answer_ok += 1
        else:
            failures.append(f"{item['id']} 误拒答：语料内的问题被判成「资料中未提及」")

        recall_total += 1
        rank = next((i + 1 for i, d in enumerate(docs) if d in item["gold_doc_ids"]), None)
        if rank:
            recall_hit += 1
            rr_sum += 1.0 / rank
        else:
            failures.append(f"{item['id']} 前 {top_k} 条未命中金标文档 {item['gold_doc_ids']}，实际 {docs[:3]}")

        evidence_total += 1
        evidence_ok = any(item["must_contain"] in h["text"] for h in hits) if item["must_contain"] else True
        evidence_hit += 1 if evidence_ok else 0
        if not evidence_ok:
            failures.append(f"{item['id']} 命中文档但块内不含关键证据「{item['must_contain']}」")

        cite_total += 1
        cite_okd, problems = validate_citations(result["answer"], result["citations"])
        cite_ok += 1 if cite_okd else 0
        if not cite_okd:
            failures.append(f"{item['id']} 引用非法：{problems}")

        rows.append(
            (
                item["id"],
                kind,
                str(rank or "-"),
                "✅" if evidence_ok else "❌",
                "✅" if cite_okd else "❌",
                "❌误拒" if result["refused"] else "-",
            )
        )

    metrics = {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
        "doc_count": pipe.doc_count,
        "chunk_count": pipe.chunk_count,
        "recall_at_5": round(recall_hit / recall_total, 4) if recall_total else 0.0,
        "mrr": round(rr_sum / recall_total, 4) if recall_total else 0.0,
        "evidence_hit_rate": round(evidence_hit / evidence_total, 4) if evidence_total else 0.0,
        "citation_valid": round(cite_ok / cite_total, 4) if cite_total else 0.0,
        "answer_rate": round(answer_ok / answer_total, 4) if answer_total else 0.0,
        "refusal_acc": round(refuse_ok / refuse_total, 4) if refuse_total else 0.0,
        "refusal_acc_all": round(refuse_all_ok / refuse_all_total, 4) if refuse_all_total else 0.0,
        "known_issues": len(known_issues),
        "llm": getattr(pipe.llm, "name", "unknown"),
        "ran_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {"metrics": metrics, "rows": rows, "failures": failures, "known_issues": known_issues}



def gates(metrics: dict) -> list[tuple[str, float, float, bool]]:
    out = []
    for key, floor in GATES.items():
        value = metrics[key]
        out.append((key, value, floor, value >= floor))
    return out


def render_table(res: dict) -> str:
    m = res["metrics"]
    lines = [
        START,
        "",
        f"参数：`chunk_size={m['chunk_size']}` / `overlap={m['overlap']}` / `top_k={m['top_k']}`"
        f" · 语料 {m['doc_count']} 篇 / {m['chunk_count']} 块 · 生成器 `{m['llm']}` · 跑于 {m['ran_at']}",
        "",
        "| 指标 | 实测 | 门槛 | 判定 |",
        "|---|---|---|---|",
    ]
    for key, value, floor, ok in gates(m):
        lines.append(f"| {key} | {value:.4f} | ≥ {floor} | {'✅ PASS' if ok else '❌ FAIL'} |")
    lines += [
        "",
        "| 参考指标 | 实测 | 说明 |",
        "|---|---|---|",
        f"| 证据命中率 | {m['evidence_hit_rate']:.4f} | 命中文档的块里是否真的含关键证据 |",
        f"| 答题率 | {m['answer_rate']:.4f} | 语料内问题未被误拒的比例 |",
        f"| 拒答准确率（全量口径） | {m['refusal_acc_all']:.4f} | 含已登记缺陷 |",
        "",
    ]

    lines += ["| 用例 | 类型 | 命中排名 | 证据命中 | 引用合法 | 拒答 |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")

    lines += ["", "### 失败案例", ""]
    if res["failures"]:
        lines += [f"- {f}" for f in res["failures"]]
    else:
        lines.append("- 无")

    lines += ["", "### 已登记缺陷（known issues）", ""]
    if res.get("known_issues"):
        lines += [f"- {k}" for k in res["known_issues"]]
    else:
        lines.append("- 无")
    lines += ["", END]
    return "\n".join(lines)


def write_md(res: dict) -> None:
    table = render_table(res)
    if EVAL_MD.exists():
        text = EVAL_MD.read_text(encoding="utf-8")
        if START in text and END in text:
            text = re.sub(re.escape(START) + r".*?" + re.escape(END), table, text, flags=re.S)
        else:
            text = text.rstrip() + "\n\n" + table + "\n"
    else:
        text = "# EVAL\n\n" + table + "\n"
    EVAL_MD.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-size", type=int, default=200)
    ap.add_argument("--overlap", type=int, default=40)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--llm", choices=["stub", "deepseek"], default="stub",
                    help="stub=离线抽取式假模型（默认，确定性）；deepseek=真实模型（花钱、有波动）")
    ap.add_argument("--md", action="store_true", help="同时刷新 EVAL.md")
    args = ap.parse_args()

    llm = None
    if args.llm == "deepseek":
        llm = DeepSeekLLM()
        if not llm.available():
            print("❌ --llm deepseek 需要 DEEPSEEK_API_KEY（写进 .env 或环境变量）")
            return 2

    res = run(args.chunk_size, args.overlap, args.top_k, llm=llm)
    m = res["metrics"]

    print(f"\n=== 参数 chunk_size={m['chunk_size']} overlap={m['overlap']} top_k={m['top_k']} ===")
    print(f"语料 {m['doc_count']} 篇 -> {m['chunk_count']} 块；生成器 {m['llm']}\n")
    print(f"{'用例':<6}{'类型':<10}{'排名':<6}{'证据':<6}{'引用':<6}{'拒答':<6}")
    for r in res["rows"]:
        print(f"{r[0]:<6}{r[1]:<10}{r[2]:<6}{r[3]:<6}{r[4]:<6}{r[5]:<6}")

    print("\n--- 指标 ---")
    all_ok = True
    for key, value, floor, ok in gates(m):
        all_ok &= ok
        print(f"{key:<18}{value:>8.4f}   门槛 >= {floor:<5} {'PASS' if ok else 'FAIL'}")
    print(f"{'evidence_hit_rate':<18}{m['evidence_hit_rate']:>8.4f}   （参考项）")
    print(f"{'answer_rate':<18}{m['answer_rate']:>8.4f}   （参考项）")
    print(f"{'refusal_acc_all':<18}{m['refusal_acc_all']:>8.4f}   （含已登记缺陷）")

    print("\n--- 失败案例 ---")
    for f in res["failures"] or ["无"]:
        print("-", f)

    print("\n--- 已登记缺陷 ---")
    for k in res.get("known_issues") or ["无"]:
        print("-", k)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已存档：{out.relative_to(ROOT)}")

    if args.md:
        write_md(res)
        print(f"EVAL.md 已刷新：{EVAL_MD.relative_to(ROOT)}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
