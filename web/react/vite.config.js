import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 关键：把 /api 代理到 Python 后端，前端代码里就只写相对路径 '/api/ask'，
// 部署时同源、开发时跨端口都能跑，不需要在前端硬编码 host。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
