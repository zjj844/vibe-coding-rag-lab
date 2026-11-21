import { useEffect, useState } from "react";
import { getHealth } from "../api.js";

/**
 * 健康徽章：组件只负责"显示状态"，取数逻辑在 api.js。
 * 这就是 React 的"受控组件 + 副作用分离"：useState 存数据，useEffect 触发一次请求。
 */
export default function HealthBadge() {
  const [health, setHealth] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false; // 防止组件卸载后 setState（React 里的经典坑）
    getHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ok = health && health.status === "ok";
  const cls = failed ? "pill bad" : ok ? "pill ok" : "pill";
  const text = failed
    ? "API 异常"
    : health
    ? `API 正常 · ${health.doc_count} 篇 / ${health.chunk_count} 块`
    : "连接中…";

  return <span className={cls}>{text}</span>;
}
