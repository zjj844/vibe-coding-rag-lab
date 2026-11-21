"""模型体检：账号能用哪些模型、哪个是"推理模型"、max_tokens 该给多少。

为什么要这个工具：
`deepseek-v4-pro` 是**推理模型**，会先输出 `reasoning_content`（思考）再输出 `content`（正文）。
如果 max_tokens 给小了，token 全花在思考上，正文返回空 —— 表现为"模型没有返回任何代码"，
极难从报错里看出原因（第一次跑生成用例时踩了这个坑）。

用法：
    python scripts/check_models.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.env import load_env, mask, urllib_opener  # noqa: E402

BASE = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")


def _post(path: str, payload: dict, timeout: int = 180) -> dict:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib_opener().open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, timeout: int = 30) -> dict:
    key = os.getenv("DEEPSEEK_API_KEY")
    req = urllib.request.Request(
        f"{BASE}{path}", headers={"Authorization": f"Bearer {key}"}, method="GET"
    )
    with urllib_opener().open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe(model: str, max_tokens: int = 300) -> dict:
    started = time.time()
    data = _post(
        "/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "用一句话说明 pytest 是什么。"}],
            "temperature": 0,
            "max_tokens": max_tokens,
        },
    )
    choice = data["choices"][0]
    msg = choice["message"]
    usage = data.get("usage", {})
    details = usage.get("completion_tokens_details", {}) or {}
    return {
        "model": model,
        "finish_reason": choice.get("finish_reason"),
        "content_len": len(msg.get("content") or ""),
        "reasoning_tokens": details.get("reasoning_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "seconds": round(time.time() - started, 1),
    }


def main() -> int:
    load_env()
    print("=" * 66)
    print(" DeepSeek 模型体检")
    print("=" * 66)
    print(f"key      : {mask(os.getenv('DEEPSEEK_API_KEY'))}")
    print(f"base_url : {BASE}")
    print(f"默认模型 : {os.getenv('DEEPSEEK_MODEL') or '(未设置)'}")

    try:
        models = [m.get("id") for m in _get("/models").get("data", [])]
        print(f"\n账号可用模型：{', '.join(models) or '(接口未返回列表)'}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n获取模型列表失败：{type(exc).__name__}: {exc}")
        models = [os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"]

    print("\n逐个体检（max_tokens=300，只看是不是推理模型、正文有没有出来）")
    print(f"{'模型':<22}{'finish':<12}{'正文长度':>8}{'思考token':>10}{'耗时s':>7}")
    print("-" * 66)
    reasoning_models: list[str] = []
    for name in models:
        try:
            r = probe(name)
        except urllib.error.HTTPError as exc:
            print(f"{name:<22}HTTP {exc.code}")
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<22}{type(exc).__name__}")
            continue
        if r["reasoning_tokens"] > 0:
            reasoning_models.append(name)
        print(
            f"{r['model']:<22}{str(r['finish_reason']):<12}{r['content_len']:>8}"
            f"{r['reasoning_tokens']:>10}{r['seconds']:>7}"
        )

    print("\n结论")
    if reasoning_models:
        print(f"  ⚠️ 推理模型（会先思考，max_tokens 要给足）：{', '.join(reasoning_models)}")
        print("     → 生成代码类任务建议 max_tokens >= 4000；自评类 600~1000 够用")
        print("     → 如果正文为空且 finish_reason=length，就是 token 被思考吃光了")
    else:
        print("  ✅ 都是普通模型，正文直接返回")
    print("  建议：生成用例优先用 flash 这类快模型（便宜、无思考开销）；")
    print("        复杂评审再用推理模型，但要给足 max_tokens。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
