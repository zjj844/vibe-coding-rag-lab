"""Web 冒烟检查：一条命令验证所有页面和接口都能正常返回。

用法：
    python scripts/serve.py        # 先起服务（另一个终端）
    python scripts/verify_web.py   # 再跑这个

为什么要有它：页面"黑屏"这类问题，一半是资源 404 / 路径写错 / 类型不对导致的。
先确认"该拿到的字节都拿到了"，再去查浏览器，能省很多时间。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

CHECKS = [
    # (路径, 期望最小字节数, 说明)
    ("/", 2_000, "落地页"),
    ("/vue/", 8_000, "Vue 3 前端"),
    ("/react/", 400, "React 前端 HTML"),
    ("/react/dist/app.js", 100_000, "React 打包产物"),
    ("/react/dist/app.css", 1_000, "React 样式"),
    ("/vendor/vue.global.prod.js", 100_000, "本地化 Vue 库"),
    ("/api/health", 20, "健康检查"),
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ok = True
    print(f"{'路径':<30}{'状态':>6}{'字节':>9}  Content-Type / 说明")
    print("-" * 78)
    bodies: dict[str, bytes] = {}
    for path, min_bytes, label in CHECKS:
        try:
            with urllib.request.urlopen(BASE + path, timeout=30) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                status = resp.status
        except urllib.error.HTTPError as exc:
            print(f"{path:<30}{exc.code:>6}{'-':>9}  {label} ❌")
            ok = False
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"{path:<30}{'ERR':>6}{'-':>9}  {label} ❌ {exc}")
            ok = False
            continue

        bodies[path] = body
        good = status == 200 and len(body) >= min_bytes
        ok &= good
        print(f"{path:<30}{status:>6}{len(body):>9}  {ctype.split(';')[0]}  {label} {'✅' if good else '❌ 体积偏小'}")

    # 内容层面的校验：光有 200 不够，还要看关键片段在不在
    print("\n内容校验")
    checks = []

    react_html = bodies.get("/react/", b"").decode("utf-8", "ignore")
    checks.append(("React 页面含挂载点 #root", 'id="root"' in react_html))
    checks.append(("React 页面引入 app.js", "/react/dist/app.js" in react_html))
    checks.append(("React 页面含错误浮层", "boot-error" in react_html))

    app_js = bodies.get("/react/dist/app.js", b"").decode("utf-8", "ignore")
    checks.append(("app.js 已打成经典脚本（IIFE，可直接 <script> 加载）", app_js.lstrip().startswith("(()=>") or app_js.lstrip().startswith("(function")))
    checks.append(("app.js 未残留 NODE_ENV（避免 process 未定义）", "NODE_ENV" not in app_js))

    vue_html = bodies.get("/vue/", b"").decode("utf-8", "ignore")
    checks.append(("Vue 页面引用本地 vue 库", "/vendor/vue.global.prod.js" in vue_html))

    health = bodies.get("/api/health", b"{}")
    try:
        data = json.loads(health)
        checks.append((f"接口返回合法 JSON（llm={data.get('llm')}）", data.get("status") == "ok"))
    except json.JSONDecodeError:
        checks.append(("接口返回合法 JSON", False))

    for label, passed in checks:
        ok &= passed
        print(f"  {'✅' if passed else '❌'} {label}")

    print("\n" + ("全部通过 ✅" if ok else "存在问题 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
