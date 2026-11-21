"""生成层：拼提示词、产出带引用的答案、校验引用。

两个实现：
- ExtractiveLLM：离线、确定性，从命中块里抽最相关的一句 —— CI 用它，永不时红时绿；
- DeepSeekLLM：真实调用（需要 DEEPSEEK_API_KEY），只在人工评估时用。

validate_citations 是**纯规则校验**，不调模型，所以它是确定性断言，
可以设成硬门槛（等于 1.0），这是"回答可溯源"这条验收的机器化表达。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .embedding import grams
from .env import urllib_opener

_CITE = re.compile(r"\[(\d+)\]")
# 切句时必须把换行也算上：否则 "# 标题\n第一句。" 会被当成一句，
# 导致答案里混进 Markdown 标题（第一版就是这个 bug，页面上看得很明显）。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def build_prompt(question: str, hits: list[dict]) -> str:
    """把检索结果编号后放进提示词——编号是引用的锚点。"""
    lines = ["你是一个只依据给定资料回答问题的助手。", "", "资料："]
    for i, h in enumerate(hits, 1):
        lines.append(f"[{i}]（{h['doc_id']} / {h['chunk_id']}）{h['text']}")
    lines += [
        "",
        f"问题：{question}",
        "",
        "要求：",
        "1. 只依据上面的资料回答，不要使用资料之外的知识；",
        "2. 每个结论后面标注来源编号，例如 [1]；",
        "3. 如果资料里没有答案，只回答：资料中未提及。",
    ]
    return "\n".join(lines)


def validate_citations(answer: str, citations: list[dict]) -> tuple[bool, list[str]]:
    """确定性校验：答案里出现的每个 [n] 都必须在 citations 里存在。

    ⚠️ 规则修正记录（换真模型后发现）：
    第一版还禁止"重复引用编号"，因为假模型只会输出一个 `[1]`。
    但真实模型经常 `[1] … [1]` ——同一份资料支撑了两句话，这在人类写作里完全正常。
    那条规则是**为假模型量身定做的假规则**，会把合法回答判成非法
    （实测让真模型的引用合法率从 1.0 掉到 0.33）。
    现在的判定只保留两条真正的不变量：
      1. 每个 [n] 都必须能在出处列表里找到（不越界）；
      2. 有答案就必须有出处（拒答除外）。
    """
    problems: list[str] = []
    answer = answer or ""
    valid_ids = {c["index"] for c in citations}
    used = [int(m.group(1)) for m in _CITE.finditer(answer)]

    if "资料中未提及" not in answer:
        if not used:
            problems.append("有答案但没有任何 [n] 引用")
        if not citations:
            problems.append("有答案但出处列表为空")
    for n in used:
        if n not in valid_ids:
            problems.append(f"引用 [{n}] 不在出处列表中（越界引用）")
    return (not problems, problems)



class ExtractiveLLM:
    """离线假模型：抽最相关的一句当答案。

    它刻意"不聪明"——因为测试要测的是**链路**（检索→编号→引用→拒答），
    不是模型的智商。真实模型放进来只会引入波动。
    """

    name = "stub-extractive"

    # 阈值来源：实测 gold set 的支持度分布（fix 掉 ASCII 噪声 n-gram 之后重测）：
    #   语料内问题 best_any: 0.095 ~ 0.400
    #   语料外问题 best_any: 0.043 / 0.059
    # 0.075 落在 0.059 与 0.095 之间的空隙里。**换语料必须重测，不能沿用。**
    def __init__(self, min_support: float = 0.075) -> None:
        self.min_support = min_support

    def answer(self, question: str, hits: list[dict]) -> dict:
        qg = set(grams(question))
        best = None       # 可作为出处的句子（正文）
        best_any = None   # 含标题行在内的最大支持度，只用于"能不能答"的判断

        for i, h in enumerate(hits, 1):
            for sent in (s.strip() for s in _SENT_SPLIT.split(h["text"])):
                if len(sent) < 4:
                    continue
                sg = set(grams(sent))
                support = len(qg & sg) / max(1, len(qg))
                if best_any is None or support > best_any:
                    best_any = support
                # 标题行参与"能否回答"的判断（标题信息量大），但不能当引用出处
                if sent.startswith("#") or len(sent) < 6:
                    continue
                if best is None or support > best[0]:
                    best = (support, i, sent)

        # 判定只看 best_any（含标题），不再对正文句加第二道阈值：
        # 正文句天然比标题短、重合少，双阈值等于对同一件事重复打卡，
        # 实测会把 q03 / q11 这些本来能答的问题误拒。
        answerable = best_any is not None and best_any >= self.min_support
        if not answerable or best is None:
            # 检索到的东西和问题对不上 → 必须拒答，而不是硬编一个
            return {"answer": "资料中未提及。", "citations": [], "refused": True}

        # 已知缺陷（登记在 gold_set.jsonl 的 notes 里，用 xfail 语义看待）：
        # 词面重合高 ≠ 能回答。例如"安装包有多大"与文档字面高度重合，
        # 但文档没有大小信息，抽取式实现仍会硬答。这属于方法论缺陷，
        # 不是实现 bug —— 修法是换语义相似度 / 真实模型，见 EVAL.md。

        support, idx, sent = best
        hit = hits[idx - 1]
        answer = f"{sent.rstrip('。；;')}。 [{idx}]"
        citations = [
            {
                "index": idx,
                "doc_id": hit["doc_id"],
                "chunk_id": hit["chunk_id"],
                "quote": sent.strip(),
                "score": hit["score"],
            }
        ]
        return {"answer": answer, "citations": citations, "refused": False}


class DeepSeekLLM:
    """真实调用版（只在人工评估时用；CI 里不启用，避免花钱和波动）。

    模型名与地址都从环境变量读：不同账号/网关开放的模型名不一样
    （实测该 key 只有 deepseek-flash 和 deepseek-v4-pro，没有 deepseek-chat），
    所以不要写死在代码里。
    """

    name = "deepseek"

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 retries: int = 3, backoff: float = 1.0) -> None:
        self.model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.retries = max(1, retries)
        self.backoff = backoff
        self.name = f"deepseek:{self.model}"

    def available(self) -> bool:
        return bool(self.api_key)

    def answer(self, question: str, hits: list[dict]) -> dict:
        if not self.available():
            raise RuntimeError("未设置 DEEPSEEK_API_KEY")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": build_prompt(question, hits)}],
            "temperature": 0,  # 温度 0：尽可能降低波动，让评估可比
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        url = f"{self.base_url}/chat/completions"

        # 必须重试：实测通过代理调用时偶发 SSL EOF / 连接重置 / 307 重定向，
        # 单次失败会让整份评估作废（12 条用例里挂 1 条就前功尽弃）。
        # 分类处理：4xx 立刻失败（key 错、模型名不存在，重试没意义）；
        # 3xx 跟随 Location 重发；网络类错误指数退避重试。
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            current = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
            try:
                with urllib_opener().open(current, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:200]
                if 400 <= exc.code < 500:
                    raise RuntimeError(f"DeepSeek 返回 HTTP {exc.code}：{detail}") from exc
                location = exc.headers.get("Location") if 300 <= exc.code < 400 else None
                if location:
                    # 代理/网关偶尔用 307 中转，跟随后重发同样内容
                    url = urllib.parse.urljoin(url, location)
                    last_error = RuntimeError(f"HTTP {exc.code} → 跟随重定向到 {url}")
                else:
                    last_error = RuntimeError(f"HTTP {exc.code}：{detail}")
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(self.backoff * (2 ** (attempt - 1)))
        else:
            raise RuntimeError(f"DeepSeek 调用失败（已重试 {self.retries} 次）：{last_error}")
        text = data["choices"][0]["message"]["content"].strip()

        if "资料中未提及" in text:
            return {"answer": text, "citations": [], "refused": True}

        used = sorted({int(m.group(1)) for m in _CITE.finditer(text)})
        citations = []
        for n in used:
            if 1 <= n <= len(hits):
                h = hits[n - 1]
                citations.append(
                    {
                        "index": n,
                        "doc_id": h["doc_id"],
                        "chunk_id": h["chunk_id"],
                        "quote": h["text"][:80],
                        "score": h["score"],
                    }
                )
        return {"answer": text, "citations": citations, "refused": False}
