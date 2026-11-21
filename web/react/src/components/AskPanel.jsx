import { useCallback, useState } from "react";
import { searchChunks } from "../api.js";
import Citations from "./Citations.jsx";

/**
 * 问答 + 检索调试面板。
 *
 * 这里的三个 state 对应三种 UI 状态：loading（按钮禁用）、error（红字）、result（结果卡片）。
 * 用 useCallback 包住请求函数，避免每次渲染都重建（依赖数组为空 = 只创建一次）。
 */
export default function AskPanel() {
  const [question, setQuestion] = useState("清华镜像装 torch 失败是什么原因");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [hits, setHits] = useState([]);

  const ask = useCallback(async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: topK }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || data.detail || `请求失败 ${resp.status}`);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [question, topK]);

  const onlySearch = useCallback(async () => {
    setLoading(true);
    setError("");
    setHits([]);
    setResult(null);
    try {
      const data = await searchChunks(question, topK);
      setHits(data.hits);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [question, topK]);

  return (
    <>
      <div className="card">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="输入问题，例如：libGL.so.1 缺失该用什么命令安装"
        />
        <div className="row">
          <button className="primary" disabled={loading || !question.trim()} onClick={ask}>
            {loading ? "查询中…" : "提问（带出处）"}
          </button>
          <button className="ghost" disabled={loading || !question.trim()} onClick={onlySearch}>
            只检索
          </button>
          <label className="dim small">
            top_k{" "}
            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
              {[1, 3, 5, 8].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && <p className="err">{error}</p>}
      </div>

      {result && (
        <div className="card">
          <div className={result.refused ? "answer refused" : "answer"}>{result.answer}</div>
          <div className="meta">
            <span>生成器：{result.llm}</span>
            <span>耗时：{result.latency_ms} ms</span>
            <span className={result.refused ? "dim" : "ok"}>
              {result.refused
                ? "已拒答（语料中未提及）"
                : `引用合法：${result.citation_valid ? "是" : "否"}`}
            </span>
            <span className="dim">检索到 {result.retrieved.length} 块</span>
          </div>

          <Citations citations={result.citations} />

          <div style={{ marginTop: 16 }}>
            <div className="dim small" style={{ marginBottom: 6 }}>
              检索命中（按分数降序）
            </div>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>文档</th>
                  <th>块</th>
                  <th>分数</th>
                </tr>
              </thead>
              <tbody>
                {result.retrieved.map((r, i) => (
                  <tr key={r.chunk_id}>
                    <td className="dim">{i + 1}</td>
                    <td>{r.doc_id}</td>
                    <td className="dim">{r.chunk_id}</td>
                    <td>{r.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {hits.length > 0 && (
        <div className="card">
          <Citations citations={hits.map((h, i) => ({ ...h, index: i + 1, quote: h.text }))} />
        </div>
      )}
    </>
  );
}
