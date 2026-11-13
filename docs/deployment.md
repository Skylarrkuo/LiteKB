# LiteKB 轻量部署

默认启动 API、Celery Worker、PostgreSQL 17（pgvector）和 Redis 四个服务。API 与 Worker 共用 Python 3.11 镜像，容器内沿用上游的包名和 MAXKB_* 配置。镜像只构建管理控制台，推理和向量化使用远程模型。默认适配器包括 OpenAI、阿里云百炼、小米 MiMo、DeepSeek、vLLM 和硅基流动。知识库首次入库前，请在控制台配置可用的 Embedding 模型，授权给调用方所属项目，再为知识库选择该模型。外部 /v1/models 列出项目已获授权的模型。

## 首次启动

在支持 Linux 容器的 Docker Compose v2 环境中，从仓库根目录运行以下命令。初始化脚本使用 Python 标准库创建四项独立凭据，重复执行会保留已有值并补齐缺少的凭据。

```sh
python installer/init_env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
curl --fail http://127.0.0.1:8080/health/ready
```

只构建镜像可执行 `docker compose build api`。独立构建使用 `docker build -f installer/Dockerfile -t litekb:local .`，从仓库根目录传入构建上下文。镜像将管理控制台、Linux 工具沙箱和 Python 运行环境分阶段构建。发布流水线手动触发后从同一 Dockerfile 构建，目标仓库为当前 Fork 所有者的 GHCR。CPU 架构由构建平台决定。

用账号 admin 和 .env 中的 LITEKB_ADMIN_PASSWORD 登录 http://127.0.0.1:8080/admin/。Compose 仅向 API 容器传入 MAXKB_BOOTSTRAP_ADMIN_PASSWORD，admin 密码只在首次迁移时写入。升级时沿用原密码。直接运行源码时也请在首次迁移前设置该变量。该文件包含服务凭据，请限制访问并随备份妥善保管。容器间的任务签名使用同一个 LITEKB_SECRET_KEY。

API 在首次启动时执行数据库迁移并收集静态文件，健康检查通过后 Worker 开始消费 celery 和 model 两个队列。PostgreSQL 初始化脚本启用 vector 扩展。连接已有数据库时，请先由数据库管理员在目标数据库中执行 `CREATE EXTENSION IF NOT EXISTS vector`。迁移会撤销旧版应用定时任务，以及按时间提炼长期记忆的计划。迁移前停止旧 Worker、备份数据库，并保留原有密钥与文件存储。

默认端口只绑定到本机。在 .env 设置 LITEKB_BIND、LITEKB_PORT 可更改监听地址及端口。嵌入产品的服务器通过 /v1/ 调用服务；从其他主机访问时，在反向代理配置 TLS，关闭 SSE 路径的代理缓冲。数据库和 Redis 通过内部网络通信。原有工具代码使用专用 sandbox 用户和编译后的 sandbox.so 执行。

## Windows 原生开发与验收

准备 Python 3.11、uv、Node.js 24、可访问的 PostgreSQL 和 Redis。pgvector 的二进制需与 PostgreSQL 主版本匹配，目标库需启用 `vector`。Compose 使用 PostgreSQL 17。本机控制台已在 PostgreSQL 18.6 和 pgvector 0.8.7 上验收，独立回归实例使用 PostgreSQL 16.15。从仓库根目录执行以下 PowerShell 命令。已有开发虚拟环境可以直接复用。

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r pyproject.toml
npm --prefix ui ci
npm --prefix ui run build
python installer/init_env.py
```

在生成的 `.env` 凭据后面加入以下源码运行配置，将数据库和 Redis 的地址、账号、密码改为实际值。示例中的凭据引用由 python-dotenv 展开。如果 Redis 实例使用空密码，将 `MAXKB_REDIS_PASSWORD=` 留空。

```dotenv
MAXKB_CONFIG_TYPE=ENV
MAXKB_DB_HOST=127.0.0.1
MAXKB_DB_PORT=5432
MAXKB_DB_NAME=litekb
MAXKB_DB_USER=litekb
MAXKB_DB_PASSWORD=${LITEKB_DB_PASSWORD}
MAXKB_REDIS_HOST=127.0.0.1
MAXKB_REDIS_PORT=6379
MAXKB_REDIS_PASSWORD=${LITEKB_REDIS_PASSWORD}
MAXKB_SECRET_KEY=${LITEKB_SECRET_KEY}
MAXKB_BOOTSTRAP_ADMIN_PASSWORD=${LITEKB_ADMIN_PASSWORD}
```

在第一个 PowerShell 窗口运行 `.venv/Scripts/python main.py dev web`，它收集静态文件、执行迁移并在 `127.0.0.1:8080` 启动同一 Django WSGI 应用。可通过 `LITEKB_DEV_BIND` 修改开发监听地址。在第二个窗口从相同目录运行以下命令，确认就绪后启动 Windows 的 Celery solo Worker。

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health/ready
.venv/Scripts/python main.py dev celery
```

两种进程读取相同的签名密钥。访问 `http://127.0.0.1:8080/admin/` 打开控制台。原生 Windows 支持远程模型、知识库处理及通用工作流。执行自定义 Python、Shell 和需要沙箱的 MCP 工具时要求 Linux 沙箱。Windows 默认日志位于 `data/logs`，可用 `MAXKB_LOG_DIR` 修改。

需要关闭终端后继续运行，可从项目根目录使用后台启动器。它在启动前执行迁移、收集静态文件，并等待 API 和一个单并发 Worker 就绪。默认连接 `.env` 指定的 Redis。如果使用项目自己的便携版 Redis，将 `LITEKB_DEV_REDIS_EXE` 设为可执行文件路径，同时设好 `MAXKB_REDIS_HOST=127.0.0.1`、`MAXKB_REDIS_PORT` 和密码。启动器把进程记录、日志和托管 Redis 的 AOF 放在 `.dev/run/`。停止操作只作用于该启动器登记的进程。

```powershell
.venv/Scripts/python installer/dev_windows.py start
.venv/Scripts/python installer/dev_windows.py status
.venv/Scripts/python installer/dev_windows.py stop
```

## 可选能力

| .env 配置 | 启用内容 |
| --- | --- |
| LITEKB_MEDIA_NODES=1 | 构建语音、图片生成、视频节点以及 ffmpeg，控制台和服务端同时启用 |
| LITEKB_EXTENDED_PROVIDERS=1 | 安装其他供应商 SDK，恢复原有模型适配器 |
| LITEKB_LOCAL_MODEL=1 | 安装本地 Embedding 与 Rerank 依赖，包括 CPU 版 PyTorch |

直接构建镜像时，通过 `--build-arg LITEKB_MEDIA_NODES=1` 等同名参数选择能力，三个开关可组合。Compose 中修改能力开关后执行 `docker compose up -d --build --wait`。有历史版本依赖某厂商或媒体节点时，先启用对应选项，或编辑工作流并重新发布。图像理解、循环、条件、MCP 与多步骤编排默认可用。

启用本地模型时，使用 `docker compose --profile local-model up -d --build --wait`。提前将已有权重复制进模型服务的 /models 目录，例如 `docker compose cp ./my-embedding local-model:/models/my-embedding`，在本地模型适配器中填写模型名称或路径以及缓存目录。models 命名卷用于持久保存权重，首次启用不会安装模型权重。

## 验证和维护

API 和本地模型的 /health/ready 会检查 PostgreSQL 与 Redis，依赖不可用时返回 HTTP 503。Worker 健康检查读取就绪标记和 Celery 心跳时间。容器中可执行 `litekb health` 检查当前进程角色。

首次启动未就绪时执行 `docker compose logs --tail=200 api`。入口按数据库迁移、收集静态文件、启动 WSGI 三个阶段输出日志，Gunicorn 的 worker 启动异常也会写入同一份日志。构建镜像时会在禁网环境中导入实际 WSGI 应用并解析就绪路由，运行时的探针另行检查实际数据库与 Redis 的连接。

```sh
docker compose exec api python apps/manage.py check
docker compose exec api python apps/manage.py migrate --check
docker compose exec api python -m unittest maxkb.test_runtime_profile
docker compose exec worker celery -A ops.celery:app inspect registered
docker compose logs --tail=100 api worker
```

基础镜像的已注册任务应包含知识库向量化任务和 LiteKB 的 Run 任务。升级前先备份 pgdata，保留 redisdata 可以保留等待执行的任务。使用 `docker compose down` 停止服务后，命名卷会保留。

在独立的开发或验收用 Compose 实例中，可以运行项目回归。下面的命令在首次执行时创建专门的测试库并启用 pgvector，后续直接重复最后一行。测试使用当前实例的 Redis，因此请使用测试实例。

```sh
docker compose exec postgres createdb -U litekb test_litekb
docker compose exec postgres psql -U litekb -d test_litekb -c 'CREATE EXTENSION IF NOT EXISTS vector'
docker compose exec api python apps/manage.py test litekb_api maxkb.test_runtime_profile system_manage.test_branding users.test_bootstrap application.test_reranker_node common.tests_split_model --keepdb
```

启用媒体构建后，可在上述测试列表中加入 `common.test_media_audio`，检查 SILK 音频解码与 MP3 转码。在源码开发环境执行 `python apps/manage.py test maxkb.test_console_base` 可验证自定义控制台前缀和深层链接。在仓库根目录执行 `python -m unittest installer.test_init_env` 可验证已有凭据的保留和并发初始化。
