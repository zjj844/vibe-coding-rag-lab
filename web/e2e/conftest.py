"""web/e2e 目录的占位 conftest。

`browser` / `page` 夹具已经上移到项目根目录的 `conftest.py`——因为 conftest 只对
自身目录及子目录生效，而 Agent 生成的用例会落到 `evals/generated/`，那里拿不到这里定义的夹具
（第一次跑生成用例就是 5 条全 `fixture 'page' not found`）。

这个文件保留是有意的：以后如果你要写**只给 E2E 用的夹具**（比如"先登录"），放这里最合适。
"""
