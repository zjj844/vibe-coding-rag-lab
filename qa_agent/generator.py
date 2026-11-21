"""② 用例生成：需求片段 + 页面对象接口 → 让模型产出 pytest 用例源码。

三条硬约束（这是"能跑通"和"生成一堆废码"的分界线）：

1. **只准用已有的 Page Object**：把 `QaPage` 的方法签名写进提示词，
   模型就不会凭空发明 `page.click("#submit")` 这种不存在的调用。
2. **输出必须是单个 python 代码块**：便于程序化解析，不用猜哪里是代码。
3. **落盘前先 `ast.parse` 语法检查**：语法都不对的直接判失败，
   不写进仓库、不浪费后面评测的时间。

注意：语法通过 ≠ 能跑。真正能不能跑由 pytest 执行决定（见 ARCHITECTURE.md 的分层）。
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass
from pathlib import Path

from rag import llm_client

from . import contract

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "evals" / "generated"

SYSTEM_PROMPT = """你是一名资深测试开发工程师，正在为「RAG 问答网页」编写 Playwright 端到端测试。

严格规则：
1. 只能使用下面给定的 Page Object 接口，禁止发明新的方法或选择器。
2. 输出必须是一个 ```python 代码块，不要输出任何解释文字。
3. 用 pytest 风格：每个用例是一个 def test_xxx(page) 函数，参数名必须是 page。
4. 开头必须有：
   from pages.qa_page import QaPage, expect_healthy
5. 每个用例只验证一个需求点，断言要具体（断言文本内容或元素数量，不要只断言"没报错"）。
6. 涉及真实模型回答的断言，单个用例等待时间不超过 60 秒。

可用的 Page Object 接口（唯一允许的调用方式）：
{page_object_api}
"""


@dataclass
class GenerationResult:
    ok: bool
    code: str
    case_count: int
    error: str = ""
    evidence: list[dict] | None = None
    prompt: str = ""

    def summary(self) -> str:
        if not self.ok:
            return f"❌ 生成失败：{self.error}"
        return f"✅ 生成成功，共 {self.case_count} 个用例（语法检查通过）"


def _page_object_api() -> str:
    """从真实代码里抽接口清单（区分属性/方法），避免提示词和代码脱节。

    ⚠️ 第一版只抽了方法，模型就把 @property 也写成 `qa.xxx()` 调用，
    语法通过、自评 4.0，一跑就 TypeError —— 现在改成从 AST 里读 decorator。
    """
    try:
        members = contract.load_members()
    except (OSError, SyntaxError):
        return "（未能读取页面对象，请谨慎使用）"
    return contract.describe_for_prompt(members)


def build_messages(requirement_context: list[dict], n_cases: int = 5) -> list[dict]:
    context = "\n\n".join(
        f"【{c['doc_id']} / {c['chunk_id']}】\n{c['text']}" for c in requirement_context
    )
    user = (
        f"以下是需求文档的相关片段：\n\n{context}\n\n"
        f"请据此生成 {n_cases} 个端到端测试用例，覆盖面尽量不同（正常流程、边界、异常）。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(page_object_api=_page_object_api())},
        {"role": "user", "content": user},
    ]


def extract_code(text: str) -> str:
    """从模型回复里抠出 python 代码块。"""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def validate_code(code: str) -> tuple[bool, int, str]:
    """返回值：(是否通过, 用例数, 错误信息)。三道关：语法 → 形式 → 接口契约。"""
    if not code.strip():
        return False, 0, "模型没有返回任何代码"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, 0, f"语法错误：{exc.msg}（第 {exc.lineno} 行）"
    cases = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if not cases:
        return False, 0, "没有找到 def test_* 用例函数"
    if "QaPage" not in code:
        return False, len(cases), "没有使用给定的 Page Object（可能自己在发明选择器）"

    # 第三关：接口契约。语法对、形式对，但可能调用了不存在的方法/给属性加了括号
    violations = contract.check_code(code)
    if violations:
        return False, len(cases), "接口契约违规：" + "；".join(violations[:3])
    return True, len(cases), ""


def generate(
    query: str,
    kb,
    n_cases: int = 5,
    top_k: int = 3,
    max_repair: int = 1,
) -> GenerationResult:
    """检索需求 → 生成 → 三道校验 →（违规时）有界自愈一次。

    `max_repair=1` 是刻意的限制，不是妥协：
    - 真实平台的"自愈"风险在于反复改脚本会把断言改弱、把真 Bug 掩盖掉；
    - MVP 只在"接口契约违规"（可以机器判定、不存在判断分歧）时重试一次，
      不碰断言强度，所以不会掩盖缺陷。
    """
    evidence = kb.search(query, top_k=top_k)
    messages = build_messages(evidence, n_cases)

    raw = ""
    code = ""
    ok, count, err = False, 0, ""
    for attempt in range(0, max_repair + 1):
        raw = llm_client.chat_for("gen", messages, max_tokens=8000)
        code = extract_code(raw)
        ok, count, err = validate_code(code)
        if ok or attempt >= max_repair:
            break
        # 只在"契约违规"时回喂重写；语法错误也值得再试一次
        if "契约违规" in err or "语法错误" in err:
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"上面的代码有问题：{err}\n请只修正这些问题，重新输出完整代码块。"},
            ]
        else:
            break

    return GenerationResult(
        ok=ok, code=code, case_count=count, error=err, evidence=evidence,
        prompt=messages[-1]["content"],
    )


def save(result: GenerationResult, out_dir: Path | str = DEFAULT_OUT_DIR, tag: str = "") -> Path:
    """落盘成合法的 pytest 文件。文件名带时间戳，永不覆盖旧结果（历史可比）。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_tag = re.sub(r"\W+", "-", tag)[:20].strip("-")
    name = f"test_generated_{stamp}{('-' + safe_tag) if safe_tag else ''}.py"
    path = out / name
    header = (
        '"""本文件由 qa_agent 自动生成，请勿手工修改（改了就失去"生成质量"的可比性）。\n\n'
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"需求依据：{', '.join(sorted({c['chunk_id'] for c in (result.evidence or [])}))}\n"
        '"""\n\n'
    )
    path.write_text(header + result.code + "\n", encoding="utf-8")
    return path
