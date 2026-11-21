"""api —— 传输层无关的服务核心 + 两个框架适配器。

分层：
- service.py   纯逻辑：ask / search / evaluate / health，不依赖任何 Web 框架
- app_flask.py Flask 适配器（本机可用；用于今天就能跑起来）
- app_fastapi.py FastAPI 适配器（你项目里用；接口契约完全一致）

好处：前端、测试、CLI 都调 service，换 Web 框架不影响上层。
"""
