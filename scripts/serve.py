"""统一的启动入口：有 fastapi 就用 fastapi，否则退回 flask。

这样"换框架"对使用者是透明的——前端、测试、接口契约都不用动。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = 8000


def main() -> int:
    try:
        import uvicorn  # noqa: F401

        print("[serve] 检测到 fastapi + uvicorn → 使用 FastAPI 适配器")
        import uvicorn

        uvicorn.run("api.app_fastapi:app", host="127.0.0.1", port=PORT, reload=False)
        return 0
    except ModuleNotFoundError:
        pass

    try:
        from api.app_flask import app

        print("[serve] 未装 fastapi → 使用 Flask 适配器（接口契约一致）")
        print(f"[serve] 打开 http://127.0.0.1:{PORT}/      落地页")
        print(f"[serve] 打开 http://127.0.0.1:{PORT}/vue/  Vue 3 前端")
        app.run(host="127.0.0.1", port=PORT, debug=False)
        return 0
    except ModuleNotFoundError as exc:
        print(f"[serve] 缺少依赖：{exc}. 请 pip install flask（或 fastapi uvicorn）")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
