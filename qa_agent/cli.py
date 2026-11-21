"""命令行入口：一条命令走完 ①知识库 → ②生成 → ③自评。

用法：
    python -m qa_agent.cli tree                        # 只看需求被切成了什么样
    python -m qa_agent.cli generate                    # 生成 5 条用例（默认查询）
    python -m qa_agent.cli generate --n 6 --query "评估面板" --no-critic
    python -m qa_agent.cli generate --save             # 生成并落盘到 evals/generated/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qa_agent import critic, generator  # noqa: E402
from qa_agent.kb import RequirementKB  # noqa: E402


def cmd_tree(_args) -> int:
    kb = RequirementKB()
    print(f"需求知识库：{kb.doc_count} 篇文档 / {kb.chunk_count} 个块\n")
    print(kb.tree())
    return 0


def cmd_generate(args) -> int:
    kb = RequirementKB()
    print(f"[①] 需求知识库：{kb.doc_count} 篇 / {kb.chunk_count} 块")
    print(kb.tree())
    print()

    result = generator.generate(args.query, kb, n_cases=args.n, top_k=args.top_k)

    print(f"[②] 检索依据（top_{args.top_k}）：")
    for c in result.evidence or []:
        print(f"     - {c['chunk_id']}  score={c['score']}  {c['text'][:40].replace(chr(10), ' ')}")
    print()
    print(f"[②] {result.summary()}")
    if not result.ok:
        print(f"     {result.error}")
        return 1

    if args.save:
        path = generator.save(result, tag=args.query)
        print(f"     已保存：{path.relative_to(ROOT)}")

    if not args.no_critic:
        print(f"\n[③] 用例自评（{args.samples} 次采样取中位）…")
        scored = critic.score(result.code, samples=args.samples)
        print("    " + scored.summary().replace("\n", "\n    "))
    else:
        print("\n[③] 已跳过自评（--no-critic）")

    print("\n---- 生成的代码预览 ----")
    head = "\n".join(result.code.splitlines()[: args.preview])
    print(head)
    if len(result.code.splitlines()) > args.preview:
        print(f"... （共 {len(result.code.splitlines())} 行，完整内容见落盘文件）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qa_agent", description="Agent 辅助的测试用例生成与自评（MVP）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tree", help="打印需求文档的模块结构树").set_defaults(func=cmd_tree)

    g = sub.add_parser("generate", help="生成测试用例并可选择自评")
    g.add_argument("--query", default="问答页面的提问与出处", help="需求检索查询")
    g.add_argument("--n", type=int, default=5, help="生成用例数量")
    g.add_argument("--top-k", type=int, default=3, help="检索需求片段数")
    g.add_argument("--samples", type=int, default=2, help="自评采样次数")
    g.add_argument("--save", action="store_true", help="落盘到 evals/generated/")
    g.add_argument("--no-critic", action="store_true", help="跳过自评（省 token）")
    g.add_argument("--preview", type=int, default=25, help="预览行数")
    g.set_defaults(func=cmd_generate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
