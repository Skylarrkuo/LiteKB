<img src="ui/public/litekb.svg" width="56" alt="LiteKB">

# LiteKB

LiteKB 是独立部署的 RAG Agent 服务。业务产品保留自己的界面、账号和权限，通过 API 把文档交给 LiteKB，检索带来源的分段，或调用已发布的多步工作流。运营人员在同一控制台维护知识、调试草稿、发布 Agent 和查看每次运行的轨迹。[English](README.md)

## 系统组成

| 组件 | 职责 |
| --- | --- |
| API 与控制台 | Django 提供项目级 `/v1` API 和管理接口，Vue 控制台提供知识库、工具、工作流画布、调试聊天和系统品牌设置 |
| Worker | Celery 执行向量化、Agent 运行和工作流节点。支持条件、循环、子应用、表单续跑及 MCP 工具 |
| PostgreSQL + pgvector | 保存知识库、向量、发布版本、聊天记录、节点结果和可重放的运行事件 |
| Redis | 缓存、任务队列与任务协调 |

默认通过远程模型进行推理和向量化。控制台提供兼容的上游在线工具目录，管理员可在「设置 → 系统品牌」更改名称与图标。默认静态发行文件约 28.3 MB，管理端入口 JS 经 gzip 压缩后约 0.71 MB。测量口径及模块关系见[架构与体积基线](docs/architecture.md)。

## 首次部署

从仓库根目录操作。需要可运行 Linux 容器的 Docker、Docker Compose v2 和用于生成随机凭据的 Python 3。第一次构建需要访问镜像仓库和软件包源。

```sh
python installer/init_env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
curl -fsS http://127.0.0.1:8080/admin/api/capabilities
```

初始化脚本生成 `LITEKB_DB_PASSWORD`、`LITEKB_REDIS_PASSWORD`、`LITEKB_SECRET_KEY` 和 `LITEKB_ADMIN_PASSWORD`。已有 `.env` 时，在原文件中补全缺失项并保留已有实例的密钥。登录账号为 `admin`，首次密码取自本地 `.env` 中的 `LITEKB_ADMIN_PASSWORD`。这个密码变量仅在首次创建管理员时生效。默认仅监听本机 8080，监听地址和端口可用 `LITEKB_BIND` 与 `LITEKB_PORT` 设置。[打开控制台](http://127.0.0.1:8080/admin/)

## 给产品接入第一个 Agent

1. 在「设置 → 模型」添加可用的向量模型和对话模型。默认支持 OpenAI、阿里云百炼（千问）、小米 MiMo、DeepSeek、vLLM 和硅基流动。选择模型后会自动载入端点与参数。[模型目录与 API 示例](docs/model-providers.md)
2. 创建普通知识库并选择向量模型。建一个关联该库的问答应用，或在工作流中连接知识检索和回答节点。在调试聊天中检查结果，然后发布。
3. 为业务产品创建 Project 并签发服务密钥。下面命令中的模型、知识库和 Agent 变量均为刚才创建的资源 UUID。项目已有知识库时，将知识库及其向量模型一起授权。用到的子应用也需要授权。

管理员需要查找默认工作区的资源 UUID 时，可以按名称列出它们。

```sh
docker compose exec api python apps/manage.py shell -c "from models_provider.models import Model; from application.models import Application; from knowledge.models import Knowledge; print([(m.__name__, list(m.objects.filter(workspace_id='default').values_list('name', 'id'))) for m in (Model, Knowledge, Application)])"
```

将选中的 UUID 填入变量并执行签发命令。

```sh
docker compose exec api python apps/manage.py litekb_client support \
  --owner admin --issue support-backend \
  --model "$EMBEDDING_ID" --model "$LLM_ID" --knowledge "$KB_ID" --agent "$AGENT_ID"
```

命令返回 `client_id` 和一次显示的 `service_key`。将密钥写入业务后端的密钥配置。一个项目可以有多个客户端，知识库归属单个项目。管理员可用 `litekb_client support --revoke CLIENT_UUID` 单独撤销客户端。

### 上传与检索

以下 HTTP 示例使用 POSIX shell、curl 和 jq，`KEY` 为服务密钥，`KB_ID` 与 `AGENT_ID` 来自上一步。文档通过 JSON 或 multipart 上传，事务提交后由 Worker 建立索引。

```sh
BASE=http://127.0.0.1:8080
AUTH="Authorization: Bearer $KEY"
curl -fsS -H "$AUTH" "$BASE/v1/agents"

DOC_ID=$(curl -fsS -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"售后手册","content":"标准保修期为两年。"}' \
  "$BASE/v1/knowledge-bases/$KB_ID/documents" | jq -er '.documents[0].id')
curl -fsS -H "$AUTH" "$BASE/v1/knowledge-bases/$KB_ID/documents/$DOC_ID" | jq '.index_status'
```

等 `index_status` 为 `success` 后执行检索。结果包括文档、分段 ID、正文和相似度。产品也可自行创建知识库、维护原件、分段、标签和关联问题，或分页导入导出 JSON。[知识库 API 及示例](docs/knowledge-api.md)

```sh
curl -fsS -H "$AUTH" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg id "$KB_ID" '{knowledge_base_ids:[$id],query:"保修多久？",mode:"blend",top_k:3}')" \
  "$BASE/v1/retrievals" | jq '.hits'
```

### 调用工作流与接收事件

产品后端用 `X-LiteKB-Subject` 传递自己的稳定用户标识。同一用户重复提交同一业务请求时复用幂等键，新请求使用新键。服务端返回 Run ID 和会话 ID。

```sh
SUBJECT='X-LiteKB-Subject: customer-42'
RUN_ID=$(curl -fsS -H "$AUTH" -H "$SUBJECT" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: support-ticket-42-turn-1' \
  -d '{"message":"标准保修期是多久？","max_runtime_seconds":120}' \
  "$BASE/v1/agents/$AGENT_ID/runs" | jq -er '.id')
curl -N -H "$AUTH" -H "$SUBJECT" "$BASE/v1/runs/$RUN_ID/events"
curl -fsS -H "$AUTH" -H "$SUBJECT" "$BASE/v1/runs/$RUN_ID" | jq '{status,session_id,result}'
```

断线后传 `Last-Event-ID` 回放后续事件。遇到 `waiting_input` 时向 `/v1/runs/{id}/resume` 提交 `node_data` 和当前表单的 `waiting_event_id`。下一轮对话带上返回的 `session_id`。管理员可在「运行记录」中检查发布版本、循环迭代、节点耗时和输出引用。[运行 API](docs/run-api.md)

Python 业务后端可以运行 `python -m pip install ./sdk/python`，用 `Client.retrieve` 检索，用 `start_run` 和 `stream_text` 提交问题并读取回答。SDK 处理 SSE 解析、事件游标和断线重连。默认检索模式 `rrf` 分别召回向量与关键词候选，再按名次融合。[接入示例](docs/product-sdk.md) · [检索质量与首字延迟](docs/validation.md) · [Windows 原生运行](docs/deployment.md)

## 构建选项

| 设置在根目录 `.env` 中的变量 | 效果 |
| --- | --- |
| `LITEKB_MEDIA_NODES=1` | 构建语音、图片生成、视频节点与媒体依赖，控制台和服务端同时启用 |
| `LITEKB_EXTENDED_PROVIDERS=1` | 安装扩展供应商适配器 |
| `LITEKB_LOCAL_MODEL=1` | 安装本地推理依赖，配合 `--profile local-model` 启动本地模型服务，权重单独准备 |

改动选项后重建镜像。默认构建只发布管理控制台，应用调试聊天包含在内。

```sh
# 构建 Compose 使用的镜像并启动
docker compose build api
docker compose up -d --wait
# 只生成本地独立镜像
docker build -f installer/Dockerfile -t litekb:local .
# 在 .env 启用本地推理后
docker compose --profile local-model up -d --build --wait
```

## 升级、开发与排错

升级前备份 PostgreSQL、保持原有密钥和存储，停掉旧版 Worker。API 启动时执行迁移并收集静态文件。此次迁移会清理旧定时触发任务。已有工作流若含媒体节点或使用扩展供应商，请在升级时启用对应构建选项。

| 现象 | 优先检查 |
| --- | --- |
| API 返回 401 或 404 | 服务密钥是否有效、资源是否授权给该项目。读运行时使用创建它的客户端和用户标识 |
| 入库后没有命中 | 文档是否启用、`index_status` 是否成功、向量模型是否可用，以及 Worker 日志 |
| Run 一直排队 | `docker compose ps`、Worker 与 Redis 连通性。SSE 无实时输出时检查反向代理缓冲 |
| 老工作流提示节点未安装 | 查看 `/admin/api/capabilities`，核对镜像的能力选项 |

```sh
docker compose logs --tail=100 api worker
docker compose exec api python apps/manage.py check
docker compose exec api python apps/manage.py migrate --check
```

源码使用 Python 3.11、Django 5.2、Vue 3 与 Vite。控制台在 `ui/` 下执行 `npm ci`、`npm run dev` 或 `npm run build`。后端开发使用 `python main.py dev` 和独立的 `python main.py dev celery` 进程。数据库、Redis 和 Linux 工具沙箱配置及测试步骤见[部署与验证](docs/deployment.md)和[开发约定](AGENTS.md)。

LiteKB 源自 MaxKB 社区版，沿用 GPL-3.0 许可。[LICENSE](LICENSE)
