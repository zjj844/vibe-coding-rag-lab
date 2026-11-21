# RAG 自动化测试起步包（可跑）

一套**能跑、能出数字、能被改坏后报红**的 RAG 测试脚手架，附带 **Web 后端 + Vue 3 / React 18 两个前端**。
核心零第三方依赖（除 pytest），不需要下载模型、不需要 API Key。

## 快速开始

```bash
pip install pytest                     # 核心测试的唯一依赖
python -m pytest                       # 56 个测试
python evals/run_eval.py --md          # 跑评估（离线假模型），刷新 EVAL.md
python scripts/tune.py                 # 参数实验：chunk_size × overlap

python scripts/check_env.py            # ★ 环境自检：key / 代理 / 依赖 / 网络
python scripts/serve.py                # 起 Web 服务 → http://127.0.0.1:8000/
#   /        落地页（两个前端入口）
#   /vue/    Vue 3 前端（离线可用，库文件已本地化）
#   /react/  React 18 前端（已预构建，直接可开）
```

## 怎么接真实模型（DeepSeek）

**第 1 步：拿 key** — <https://platform.deepseek.com> → API keys。

**第 2 步：让它能被程序读到**。二选一：

```bash
# 方式 A：写进项目 .env（推荐，不进 git）
cp .env.example .env
# 编辑 .env：
#   DEEPSEEK_API_KEY=sk-xxxx
#   DEEPSEEK_MODEL=deepseek-v4-pro

# 方式 B：设成 Windows 用户级环境变量（对所有新进程生效）
setx DEEPSEEK_API_KEY "sk-xxxx"
setx DEEPSEEK_MODEL "deepseek-v4-pro"
```

**第 3 步：自检 + 开跑**

```bash
python scripts/check_env.py                    # 应看到「key 有效，可用模型：...」
python evals/run_eval.py --llm deepseek --md   # 用真模型跑同一份 gold set
```

想在网页里也用真模型：把 `.env` 里的 `RAG_LLM=deepseek` 打开，重启 `scripts/serve.py`。

**四个必须知道的坑（都是实测踩到的）**

1. **模型名别照抄文档**：本机这个 key 可用的是 `deepseek-flash` / `deepseek-v4-pro`，
   官方文档里的 `deepseek-chat` 在这里会 400。所以模型名从环境变量读，不写死。
2. **`setx` 设的变量，早于它启动的进程读不到**。`rag/env.py` 会额外从注册表
   `HKCU\Environment` 兜底读取，所以你在 GUI 里设完变量，不用重启任何东西。
3. **网络抖动是常态**：实测通过代理调用会偶发 `SSL: UNEXPECTED_EOF`。
   `DeepSeekLLM` 内置 3 次指数退避重试（只重试网络/5xx，4xx 立刻失败）。
4. **先跑一次 `check_env.py` 再跑评估**，否则你分不清是 key 错、代理错还是模型名错。

## 怎么装前端依赖（本机实测有效的命令）

```bash
# 0) 代理（本机 Clash 的 HTTP 端口是 7877，换成你自己的）
$env:HTTP_PROXY="http://127.0.0.1:7877"; $env:HTTPS_PROXY="http://127.0.0.1:7877"

# 1) 装依赖。两个坑：
#    --cache 指到工作区：npm 默认缓存目录可能不可写（沙箱/权限）
#    --ignore-scripts：esbuild 的 postinstall 需要派生子进程，受限环境会 EPERM
cd web/react
npm install --ignore-scripts --cache D:\dsh\rag-eval-starter\.npm-cache

# 2) 打成可直接打开的静态包（无需 dev server）
cd web/react
build.cmd        # 产物：dist/app.js（production React，约 150KB）

# 3) 或者用 Vite 开发服务器（需要能正常派生子进程的普通终端）
npm run dev      # http://127.0.0.1:5173 ，/api 已代理到 8000
```

### ⚠️ `build.cmd` 里三个参数一个都不能少

| 参数 | 少了会怎样 |
|---|---|
| `--jsx=automatic` | 组件里没有 `import React`，esbuild 默认用经典运行时 → `ReferenceError: React is not defined` → **整页黑屏**（真实踩过） |
| `--format=iife` | 输出成 ESM，普通 `<script src>` 加载直接语法错误 |
| `--define:process.env.NODE_ENV=\"production\"` | 引号被 cmd 吃掉 → esbuild 定义的是标识符而非字符串 → React 停在 development 版（150KB→465KB），且运行时会抛错 |

页面还内置了 `window.onerror` 浮层：以后再出问题，会**直接把错误红字画在页面上**，而不是黑屏。

打好的 `dist/app.js` 已提交，所以**别人 clone 后不用装 node_modules 也能打开 `/react/`**。

## 目录结构（测试与评估分轨）

```
./
├── rag/                     # 被测试的系统
│   ├── chunking.py          # 分块（纯函数，可单测）
│   ├── embedding.py         # 哈希 n-gram 嵌入（确定性，零依赖）
│   ├── store.py             # 内存向量库（接口同 Chroma：add/search）
│   ├── retriever.py         # 检索（L2 指标就测这一层）
│   ├── generator.py         # 提示词 + 抽取式假模型 + 引用校验
│   └── pipeline.py          # 编排：search() / ask()
├── corpus/                  # 8 篇语料（就是你的踩坑笔记）
├── gold_set.jsonl           # 12 条黄金用例（hit/boundary/multi/refuse）
├── tests/                   # ✅ 确定性：必须全绿，可进 CI
│   ├── test_chunking.py     #    分块不变量
│   ├── test_citation.py     #    引用合法性（硬门禁）
│   ├── test_pipeline_contract.py  # 接口契约
│   └── test_retrieval_quality.py  # 检索质量门槛（统计）
├── evals/                   # 📊 质量评估：出报告，不卡 CI
│   ├── run_eval.py
│   └── artifacts/           # 每次评估的 JSON 存档，用于版本对比
├── scripts/tune.py          # 参数实验
├── api/                     # 🌐 后端（传输层无关）
│   ├── service.py           #    纯逻辑：ask/search/evaluate/health
│   ├── app_flask.py         #    Flask 适配器（本机可跑）
│   └── app_fastapi.py       #    FastAPI 适配器（契约一致，有网时用）
├── web/                     # 🎨 两个前端，同一套 API
│   ├── index.html           #    落地页 + API 契约说明
│   ├── vue/index.html       #    Vue 3.5（Composition API，离线可用）
│   ├── react/               #    React 18 + Vite（Hooks）
│   └── vendor/              #    vue.global.prod.js（本地化，不依赖 CDN）
├── EVAL.md                  # 评估报告（表格自动生成，分析手写）
└── .github/workflows/ci.yml # 两个 job：确定性测试 + 质量评估
```

## 后端 API 契约（两个前端都对着它写）

```
GET  /api/health                           → { status, doc_count, chunk_count, llm, api_version }
POST /api/ask     {"question","top_k"}     → { answer, citations[], refused, retrieved[],
                                               citation_valid, citation_problems[], latency_ms }
POST /api/search  {"question","top_k"}     → { hits:[{doc_id, chunk_id, text, score}] }
GET  /api/gold                             → { items:[黄金用例] }
POST /api/eval    {"chunk_size","overlap"} → { metrics, gates[], all_pass, failures[], known_issues[] }
```

**为什么分 service / 两个适配器**：接口契约只在 `api/service.py` 定义一次；
Flask 与 FastAPI 只是薄薄的传输层，**换框架不影响前端和测试**。

## 两个前端，一套后端

| | Vue 3.5.16 | React 18.3.1 |
|---|---|---|
| 构建 | 无需构建（`vue.global.prod.js` 本地化） | Vite 5 + JSX |
| 状态 | `ref()` 自动依赖追踪 | `useState` 不可变更新 |
| 副作用 | `onMounted` | `useEffect` + 手动 `cancelled` 保护 |
| 派生 | `computed()` 自动缓存 | `useMemo` 显式声明 |
| 现在能跑吗 | ✅ 离线可跑，直接打开 `/vue/` | ⚠️ 需 `npm install`（本机无外网） |

对照笔记写在 `web/react/README.md`，可以直接当面试时的"框架对比心得"。

## 为什么分成 tests/ 和 evals/

| | tests/ | evals/ |
|---|---|---|
| 判定 | 布尔（红/绿） | 统计（数字） |
| 波动 | 不允许 | 天然有 |
| CI | **卡住合并** | 只出报告 |
| 结果 | 必须 100% 通过 | 记录趋势与失败案例 |

LLM 应用的输出天然不确定，把两类混在一起的结果是：测试时红时绿 → 被 `skip` → 最后没人信测试。
这里的分轨让**确定性指标（引用合法率）当硬门禁**，统计指标（Recall@5）设下限并留波动空间。

## 四层测试分别测什么

| 层 | 文件 | 测什么 | 花钱 | CI |
|---|---|---|---|---|
| L0 | `test_pipeline_contract.py` | 接口没坏、top_k 生效、空输入报错、同问同答 | 否 | ✅ |
| L1 | `test_chunking.py` / `test_citation.py` | 块长上限、overlap 真共享、引用不越界 | 否 | ✅ |
| L2 | `test_retrieval_quality.py` | Recall@5 / MRR / 拒答准确率门槛 | 否 | ✅ |
| L3 | `evals/run_eval.py` | 答案质量、失败案例、artifacts 存档 | 否（用假模型） | 只出报告 |

## 四个可以写进博客的结论

1. **块越小 ≠ 越准**：`chunk_size=120` 时块数翻倍，MRR 反而最高（0.944），但**证据命中率掉到 0.778**——排序变好不等于能答好，两个指标指向相反方向。
2. **测试也会假绿**：变异测试发现，重复字符串 / 相同后缀的测试数据会让断言恒成立；改成唯一标记后才真正抓到注入的 bug。
3. **指标变化必须归因**：我一度报出"overlap 让 Recall@5 从 0.889→1.000"，后来发现那是分词噪声（`RAG` 被切成 `ra`/`ag`）导致的测量错误。修掉后差异消失——详见 `EVAL.md` 的**更正记录**。
4. **CLI 能跑不等于页面能看**：接口测试全绿，但页面上第一条答案把 Markdown 标题和正文粘成了一句。展示层质量必须用眼睛看一遍。

## 换成真实组件（三处改动，接口不变）

| 现在 | 换成 | 改哪里 |
|---|---|---|
| `HashingEmbedder` | bge-small-zh-v1.5 | `rag/embedding.py` 加一个类，签名 `embed(text)->list[float]` |
| `VectorStore`（内存） | Chroma / Milvus | `rag/store.py`，只需实现 `add` / `search` |
| `ExtractiveLLM` | DeepSeek / 任意 LLM | `rag/generator.py` 里的 `DeepSeekLLM` 已写好，`RagPipeline(llm=...)` 注入 |

换完之后 **`tests/` 一行都不用改**——这是把嵌入器/向量库/LLM 都做成可注入对象的原因。

## 首次使用注意

- 换嵌入模型后，**所有门槛值必须重测**（`GATES` 在 `evals/run_eval.py`，测试里的门槛在 `test_retrieval_quality.py`）。哈希嵌入和语义嵌入的分数分布完全不同。
- 语料从 8 篇扩到几十篇后，Recall@5 会下降，这是正常的（更难了），别急着改门槛——先看失败案例是不是真的漏召。
