import { useMemo, useState } from "react";
import { runEval } from "../api.js";

/**
 * 评估面板：把 CLI 的 `python evals/run_eval.py` 变成按钮。
 *
 * 用 useMemo 缓存"是否全部通过"的派生状态——这是 React 里
 * "能算出来的就不要存进 state" 的原则。
 */
export default function EvalPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const allPass = useMemo(() => (data ? data.all_pass : false), [data]);

  async function handleRun() {
    setLoading(true);
    setError("");
    try {
      setData(await runEval(200, 40, 5));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <button className="primary" disabled={loading} onClick={handleRun}>
        {loading ? "跑评估中…" : "跑一遍 gold set"}
      </button>

      {error && <p className="err">{error}</p>}

      {data && (
        <div style={{ marginTop: 16 }}>
          <p className={allPass ? "ok" : "bad"}>
            {allPass ? "✅ 全部门禁通过" : "❌ 有门禁未通过"}{" "}
            <span className="dim">
              （语料 {data.metrics.doc_count} 篇 / {data.metrics.chunk_count} 块）
            </span>
          </p>

          <table>
            <thead>
              <tr>
                <th>指标</th>
                <th>实测</th>
                <th>门槛</th>
                <th>判定</th>
              </tr>
            </thead>
            <tbody>
              {data.gates.map((g) => (
                <tr key={g.metric}>
                  <td>{g.metric}</td>
                  <td>{g.value}</td>
                  <td className="dim">≥ {g.floor}</td>
                  <td className={g.pass ? "ok" : "bad"}>{g.pass ? "PASS" : "FAIL"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.failures.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="bad small">失败案例</div>
              <ul className="list">
                {data.failures.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {data.known_issues.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="warn small">已登记缺陷</div>
              <ul className="list">
                {data.known_issues.map((k, i) => (
                  <li key={i}>{k}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
