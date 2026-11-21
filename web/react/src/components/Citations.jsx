/**
 * 出处列表：纯展示组件（无状态），符合"展示与数据分离"。
 *
 * props.citations: [{ index, doc_id, chunk_id, quote, score }]
 */
export default function Citations({ citations }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <div className="dim small" style={{ marginBottom: 6 }}>
        出处（可追溯原文片段）
      </div>
      {citations.map((c) => (
        <div className="cite" key={c.index}>
          <div className="head">
            <span>
              [{c.index}] {c.doc_id} / {c.chunk_id}
            </span>
            <span>相似度 {c.score}</span>
          </div>
          <div className="bar">
            <i style={{ width: `${Math.max(2, Math.round(c.score * 100))}%` }} />
          </div>
          <div className="quote">{c.quote}</div>
        </div>
      ))}
    </div>
  );
}
