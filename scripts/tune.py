"""调参实验：扫 chunk_size × overlap，输出对照表。

为什么要有这个脚本：
"我把参数从 A 调到 B，Recall@5 从 x 提到 y" —— 这句话必须有脚本产出，
不能靠记忆。这就是 CHANGELOG / 博客里"演进叙事"的数据来源。
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_eval import run  # noqa: E402

GRID = [
    (200, 0),
    (200, 40),
    (120, 0),
    (120, 40),
    (300, 50),
    (400, 60),
]


def main() -> None:
    print(f"{'chunk':>6}{'overlap':>9}{'块数':>7}{'Recall@5':>11}{'MRR':>8}{'证据命中':>10}{'引用合法':>10}{'拒答':>8}")
    print("-" * 70)
    best = None
    for cs, ov in GRID:
        m = run(cs, ov, 5)["metrics"]
        print(
            f"{cs:>6}{ov:>9}{m['chunk_count']:>7}{m['recall_at_5']:>11.3f}"
            f"{m['mrr']:>8.3f}{m['evidence_hit_rate']:>10.3f}{m['citation_valid']:>10.3f}{m['refusal_acc']:>8.3f}"
        )
        score = (m["recall_at_5"], m["mrr"])
        if best is None or score > best[0]:
            best = (score, cs, ov)
    print("-" * 70)
    print(f"最优组合：chunk_size={best[1]} overlap={best[2]}  (Recall@5={best[0][0]:.3f}, MRR={best[0][1]:.3f})")


if __name__ == "__main__":
    main()
