# Plan: Dashboard API 端点找不到问题根因修复

Date: 2026-05-07

## 问题

Dashboard 打开时显示找不到 API 端点。

## 根因分析

1. **直接根因：Vanilla Dashboard 被 React 构建产物覆盖**
   - Journey log (`2026-05-06-react-dashboard-removal-cleanup.md`) 明确记录了 Vanilla HTML/JS/CSS dashboard（`app.js` + `style.css`）已实现，旧的 React 产物已删除
   - 但当前 `devflow/dashboard/dist/` 中的文件是 **React/Vite 构建产物**（`index-DeOHXBy9.js` + `index-DRPm6xEI.css`），与 `index.html` 中的引用一致
   - 这意味着某次后续 agent 会话可能重新运行了 `npm run build`，用 React 产物覆盖了 Vanilla 文件
   - React 产物在浏览器中初始化失败时，显示"API 服务连接失败"界面

2. **次要问题：HTTPServer 单线程阻塞**
   - `devflow/api.py` 使用 `HTTPServer`（单线程），浏览器并发请求（JS + CSS + API）时可能阻塞
   - 改用 `ThreadingHTTPServer` 确保并发请求不互相阻塞

3. **缺失路由：/dashboard/favicon.svg 等静态文件 404**
   - `_ROUTE_PATTERNS` 只有 `/dashboard/assets/(.+)` 路由，没有 `/dashboard/([\w.-]+)` 处理 favicon.svg 等根级静态文件

## 修复方案

1. 重建 Vanilla HTML/JS/CSS dashboard（`index.html` + `assets/app.js` + `assets/style.css`）
2. 删除 React 构建产物（`index-DeOHXBy9.js` + `index-DRPm6xEI.css`）
3. 升级 `HTTPServer` → `ThreadingHTTPServer`
4. 添加 `/dashboard/([\w.-]+)` 路由和 `_handle_dashboard_static()` 方法

## 验证标准

- [x] Dashboard HTML 引用 `app.js` 和 `style.css`，无 React 引用
- [x] 所有 API 端点返回 200
- [x] favicon.svg 返回 200
- [x] 23 个 API 测试全部通过
