"""环境自检：一条命令告诉你"现在能做什么、缺什么"。

用法：python scripts/check_env.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.env import load_env, mask, proxy_url, urllib_opener  # noqa: E402

OK = "✅"
NO = "❌"
WARN = "⚠️"


def reachable(url: str, opener: urllib.request.OpenerDirector, timeout: int = 12) -> tuple[bool, str]:
    try:
        with opener.open(url, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        # 401/403 也说明"网络通了、服务在"
        return True, f"HTTP {exc.code}（能连上，只是没带凭证）"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:60]}"


def npm_registry() -> str:
    for candidate in (Path(os.environ.get("USERPROFILE", "")) / ".npmrc", ROOT / ".npmrc"):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("registry="):
                    return line.split("=", 1)[1].strip()
    return "https://registry.npmjs.org/（默认）"


def main() -> int:
    print("=" * 62)
    print(" RAG 项目环境自检")
    print("=" * 62)

    loaded = load_env(verbose=True)
    proxy = proxy_url()
    opener = urllib_opener()

    # ---- 1) 真实模型 ----
    print("\n【1】真实模型（DeepSeek）")
    key = os.getenv("DEEPSEEK_API_KEY")
    print(f"  DEEPSEEK_API_KEY : {mask(key)}")
    print(f"  DEEPSEEK_BASE_URL: {os.getenv('DEEPSEEK_BASE_URL', '(默认 https://api.deepseek.com/v1)')}")
    print(f"  DEEPSEEK_MODEL   : {os.getenv('DEEPSEEK_MODEL', '(默认 deepseek-chat)')}")
    print(f"  RAG_LLM          : {os.getenv('RAG_LLM') or '(空 = 离线假模型)'}")
    if loaded:
        print(f"  本次注入         : {', '.join(sorted(loaded))}")

    # ---- 2) 网络 ----
    print("\n【2】网络出口")
    print(f"  代理             : {proxy or '(未显式配置，将走系统代理)'}")
    targets = {
        "DeepSeek API": "https://api.deepseek.com/",
        "npm registry": "https://registry.npmjs.org/react",
        "PyPI": "https://pypi.org/simple/fastapi/",
    }
    net_ok = {}
    for name, url in targets.items():
        good, detail = reachable(url, opener)
        net_ok[name] = good
        print(f"  {name:<15}: {OK if good else NO} {detail}")

    # ---- 3) 真实鉴权（只有 key 和网络都通才测）----
    print("\n【3】DeepSeek 鉴权")
    if not key:
        print(f"  {WARN} 没有 key → 跳过。填 .env 里的 DEEPSEEK_API_KEY")
    elif not net_ok.get("DeepSeek API"):
        print(f"  {NO} 网络不通 → 连不上 api.deepseek.com")
    else:
        try:
            req = urllib.request.Request(
                (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            with opener.open(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in body.get("data", [])]
            print(f"  {OK} key 有效，可用模型：{', '.join(models) or '(未返回列表)'}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:120]
            print(f"  {NO} HTTP {exc.code}：{detail}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {NO} {type(exc).__name__}: {exc}")

    # ---- 4) 前端 ----
    print("\n【4】前端依赖")
    node_modules = ROOT / "web" / "react" / "node_modules"
    print(f"  npm registry     : {npm_registry()}")
    print(f"  react node_modules: {OK + ' 已安装' if node_modules.exists() else NO + ' 未安装（cd web/react && npm install）'}")
    print(f"  Vue 本地库        : {OK + ' web/vendor/vue.global.prod.js' if (ROOT / 'web' / 'vendor' / 'vue.global.prod.js').exists() else NO + ' 缺失'}")

    # ---- 5) 后端 ----
    print("\n【5】后端依赖")
    for name in ("flask", "fastapi", "uvicorn", "pytest"):
        try:
            mod = __import__(name)
            print(f"  {name:<8}: {OK} 已安装")
        except ModuleNotFoundError:
            print(f"  {name:<8}: {NO} 未安装")

    # ---- 6) 下一步 ----
    print("\n" + "=" * 62)
    print(" 建议下一步")
    print("=" * 62)
    if key and net_ok.get("DeepSeek API"):
        print("  · 真实模型已就绪：python evals/run_eval.py --llm deepseek --md")
    else:
        print("  · 先在 .env 里填 DEEPSEEK_API_KEY，并确认代理已开")
    if node_modules.exists():
        print("  · React 已就绪：cd web/react && npm run dev")
    else:
        print("  · React：cd web/react && npm install（需要网络/代理）")
    print("  · Vue 随时可用：python scripts/serve.py 然后打开 http://127.0.0.1:8000/vue/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
