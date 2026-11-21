# React 18 前端（Vite）

与 `web/vue/` 共用**同一套后端 API**（契约见 `web/index.html`），只换框架。

## 怎么跑

```bash
# 1) 先起后端（另开一个终端）
cd D:\dsh\rag-eval-starter
python scripts/serve.py            # http://127.0.0.1:8000

# 2) 再起前端
cd web/react
npm install                        # ⚠️ 需要外网；本机当前无外网，装不了
npm run dev                        # http://127.0.0.1:5173
```

Vite 已配置 `/api` 代理到 `127.0.0.1:8000`，所以前端代码里只写相对路径，不需要改 host。

## 国内网络装不上依赖时

```bash
npm config set registry https://registry.npmmirror.com
npm install
```

或者在联网环境（GitHub Codespaces / 公司网络）里先 `npm install`，再把 `node_modules` 一起带回来。

## 文件说明

```
web/react/
├── package.json          # React 18 + Vite 5 + @vitejs/plugin-react
├── vite.config.js        # 关键：/api 代理配置
├── index.html            # 挂载点 + /src/main.jsx 入口
└── src/
    ├── main.jsx          # createRoot 挂载（React 18 写法）
    ├── App.jsx           # 顶层：标签切换 + 组合子组件
    ├── api.js            # 所有 HTTP 调用集中在这里
    ├── styles.css
    └── components/
        ├── HealthBadge.jsx  # useEffect 取健康状态（含卸载保护）
        ├── AskPanel.jsx     # 提问 + 只检索，含 loading/error 三态
        ├── Citations.jsx    # 纯展示组件（无状态）
        └── EvalPanel.jsx    # 一键跑评估，useMemo 派生"是否全通过"
```

## 与 Vue 版的对照（面试可以直接讲）

| 维度 | React 版 | Vue 版 |
|---|---|---|
| 状态 | `useState`，值不可变，靠 setState 触发重渲染 | `ref()`，`.value` 可变，依赖收集自动追踪 |
| 副作用 | `useEffect(fn, [])` + 手动写 `cancelled` 防卸载后 setState | `onMounted(fn)`，卸载由框架管理 |
| 派生状态 | `useMemo` 显式声明 | `computed()` 自动缓存 |
| 取数 | 手写 `fetch` + 三态（loading/error/data） | 同样手写，但可以更少样板 |
| 模板 | JSX（表达式能力强，但和逻辑混在一起） | 模板字符串（职责更清晰，但表达式受限） |
| 首次心智负担 | 需要理解"不可变 + 重渲染" | 更接近直觉，"改数据视图就变" |

一句话总结：**React 把控制权交给你（显式缓存、显式清理），Vue 帮你兜底（自动追踪、自动清理）；项目越大 React 的自由度越值钱，项目越小 Vue 的上手速度越值钱。**
