import { useState } from "react";
import HealthBadge from "./components/HealthBadge.jsx";
import AskPanel from "./components/AskPanel.jsx";
import EvalPanel from "./components/EvalPanel.jsx";

/**
 * 顶层组件：只做两件事——切换标签、组合子组件。
 *
 * 没有把请求逻辑写在这里，是为了让 App 保持"无业务状态"，
 * 子组件各自管理自己的 loading/error，改一个面板不影响另一个。
 */
const TABS = [
  { key: "ask", label: "问答 / 检索" },
  { key: "eval", label: "评估面板" },
];

export default function App() {
  const [tab, setTab] = useState("ask");

  return (
    <div className="wrap">
      <header>
        <h1>
          RAG 问答 <small>React 18 · Hooks</small>
        </h1>
        <div>
          <HealthBadge />
          <a className="pill" href="http://127.0.0.1:8000/" style={{ marginLeft: 8, textDecoration: "none" }}>
            ← 返回入口
          </a>
        </div>
      </header>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? "active" : ""}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "ask" ? <AskPanel /> : <EvalPanel />}
    </div>
  );
}
