// 所有 HTTP 调用集中在这里：组件只关心"拿到什么数据"，不关心怎么发请求。
// 好处：换后端地址、加鉴权、统一错误处理，只改这一个文件。

async function request(path, body) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : { method: "GET" };

  const resp = await fetch(path, options);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error || data.detail || `请求失败 ${resp.status}`);
  }
  return data;
}

export const getHealth = () => request("/api/health");
export const askQuestion = (question, topK) => request("/api/ask", { question, top_k: topK });
export const searchChunks = (question, topK) => request("/api/search", { question, top_k: topK });
export const getGoldSet = () => request("/api/gold");
export const runEval = (chunkSize = 200, overlap = 40, topK = 5) =>
  request("/api/eval", { chunk_size: chunkSize, overlap, top_k: topK });
