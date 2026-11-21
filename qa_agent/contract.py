"""契约检查：静态核对"生成的代码只在调用真正存在的接口"。

为什么需要它（这是本项目最实用的一环）：
实测第一版生成结果语法完全正确、自评 4.0/5，但代码里写的是
    qa.health_badge()      ← Page Object 里它是 @property，不是方法
一跑就是 TypeError。而这类错误**不需要开浏览器就能查出来**：
把 Page Object 的成员表抽出来，和生成代码里的 `qa.xxx` 使用方式对一遍即可。

原则：能用静态检查发现的问题，不要拖到跑测试时才发现——
跑一次 E2E 要 10 秒以上，静态检查是毫秒级。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

PAGE_OBJECT = Path(__file__).resolve().parent.parent / "web" / "e2e" / "pages" / "qa_page.py"


@dataclass
class Member:
    name: str
    kind: str  # "property" | "method"
    args: list[str] = field(default_factory=list)

    def signature(self) -> str:
        if self.kind == "property":
            return f"QaPage.{self.name}  # 属性，直接取值，不要加括号"
        return f"QaPage.{self.name}({', '.join(self.args)})"


def load_members(path: Path | str = PAGE_OBJECT, class_name: str = "QaPage") -> dict[str, Member]:
    """从真实源码里抽取成员表——绝不手写，否则提示词会和代码脱节。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    members: dict[str, Member] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if not isinstance(item, ast.FunctionDef) or item.name.startswith("_"):
                    continue
                is_property = any(
                    isinstance(d, ast.Name) and d.id == "property" for d in item.decorator_list
                )
                args = [a.arg for a in item.args.args if a.arg != "self"]
                members[item.name] = Member(
                    name=item.name, kind="property" if is_property else "method", args=args
                )
    return members


def describe_for_prompt(members: dict[str, Member]) -> str:
    """给模型看的接口清单：明确标出"属性"和"方法"，避免它瞎加括号。"""
    props = [m.signature() for m in members.values() if m.kind == "property"]
    methods = [m.signature() for m in members.values() if m.kind == "method"]
    lines = ["属性（直接取值，不要加括号）："]
    lines += [f"- {p}" for p in props]
    lines += ["", "方法（必须带括号，参数照抄）："]
    lines += [f"- {m}" for m in methods]
    return "\n".join(lines)


def check_code(code: str, members: dict[str, Member] | None = None) -> list[str]:
    """返回违规列表（空列表 = 通过）。只检查 `qa.<name>` 这一种用法。"""
    members = members if members is not None else load_members()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"语法错误：{exc.msg}"]

    # 先找出代码里哪个变量是 QaPage 实例（通常是 qa）
    instance_names = {"qa"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id in {"QaPage"}:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        instance_names.add(target.id)

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            attr = node.func.attr
            if isinstance(base, ast.Name) and base.id in instance_names:
                if attr not in members:
                    violations.append(f"调用了不存在的接口：{base.id}.{attr}()")
                elif members[attr].kind == "property":
                    violations.append(
                        f"{base.id}.{attr} 是属性，多写了一对括号：应为 {base.id}.{attr}"
                    )
                elif len(node.args) != len(members[attr].args):
                    violations.append(
                        f"{base.id}.{attr}(...) 参数个数不对：期望 {len(members[attr].args)} 个"
                        f"（{', '.join(members[attr].args) or '无'}），实际 {len(node.args)} 个"
                    )
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in instance_names and node.attr not in members:
                violations.append(f"访问了不存在的属性：{node.value.id}.{node.attr}")
    # 去重保序
    seen: set[str] = set()
    return [v for v in violations if not (v in seen or seen.add(v))]
