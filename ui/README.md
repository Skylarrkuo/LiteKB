# LiteKB 控制台

控制台使用 Vue 3、TypeScript、Element Plus 和 Vite。管理员在这里维护知识库、工具和 Agent，在 LogicFlow 画布中调试多步工作流，并查看已发布 Agent 的运行记录。业务产品通过后端调用 LiteKB。部署、凭据和第一次 API 调用见[项目说明](../README_CN.md)。

## 本地开发

使用 Node.js 24 和 npm，从仓库根目录运行以下命令。先在 `127.0.0.1:8080` 启动 LiteKB API，需要向量化或执行产品 Run 时还需启动 Worker。

```sh
cd ui
npm ci
npm run dev
```

开发服务器默认使用 3000 端口，将管理 API 请求代理到 8080。入口、端口和管理路径在 `env/.env` 中配置。

## 发布与检查

```sh
npm run type-check
npm run build
```

`npm run build` 会运行类型检查并生成 `dist/admin/index.html` 及其资源。Django 的 `collectstatic` 收集产物并在管理路径下提供访问。Docker 构建会自动完成这两步。工作流调试聊天随控制台发布。

默认构建包含知识检索、条件、循环和 MCP 节点。使用 Compose 时，在仓库根目录的 `.env` 中设置 `LITEKB_MEDIA_NODES=1` 后重建。源码开发时给前端设置 `VITE_LITEKB_MEDIA_NODES=1`、给服务端设置 `LITEKB_MEDIA_NODES=1` 并安装媒体依赖。控制台从 `/admin/api/capabilities` 读取已启用节点。

## 修改入口

| 需要修改的内容 | 位置 |
| --- | --- |
| 导航与页面 | `src/router/`、`src/views/` |
| 工作流画布和节点 | `src/workflow/` |
| 草稿调试聊天 | `src/components/ai-chat/` |
| 运行记录和步骤展示 | `src/views/studio/` |
| 系统名称、图标和默认图形 | `src/utils/branding.ts`、`public/litekb.svg` |

已部署实例可直接在「设置 → 系统品牌」修改显示名称和图标。[系统架构](../docs/architecture.md)
