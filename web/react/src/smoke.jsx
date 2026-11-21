// 冒烟测试入口：在 Node 里把 App 渲染成字符串。
// 目的：在没有浏览器的环境里验证"组件树能不能渲染"，把黑屏问题定位到
//       「组件逻辑错」还是「浏览器加载/挂载错」。
import React from "react";
import { renderToString } from "react-dom/server";
import App from "./App.jsx";

const html = renderToString(React.createElement(App));
console.log("RENDER_OK length=", html.length);
console.log("含 RAG 问答标题:", html.includes("RAG 问答"));
console.log("含 提问按钮:", html.includes("提问（带出处）"));
