# AGENTS.md

This file provides repository-specific development instructions for LiteKB.

## Project Overview

LiteKB is a standalone RAG and workflow API derived from MaxKB Community Edition. Backend is Python 3.11 / Django 5.2 / LangChain and frontend is Vue 3 / Vite. PostgreSQL + pgvector stores application data. Redis and Celery handle background work. GPL-3.0. See docs/deployment.md for the Linux Compose deployment.

## Development Commands

The backend is driven by a single entrypoint `main.py` (not `manage.py` directly). It sets `apps/` on `sys.path` and configures Django settings, so module imports are `from application...`, `from common...` — not `from apps.application...`.

```bash
# Dev: runs collectstatic + migrate, then one service. Start web and worker in separate terminals.
python main.py dev            # web      (Django runserver on 0.0.0.0:8080)
python main.py dev celery     # celery worker (queues: celery, model)
python main.py dev local_model # optional embedding/local model server on 127.0.0.1:11636

# Legacy process supervisor. Compose runs API and worker separately by default.
python main.py start all -d
python main.py start web -w 3      # gunicorn, plus the model service if enabled
python main.py start task          # worker consuming celery and model queues
python main.py stop all            # stop daemons
python main.py status              # daemon status

# Database / static
python main.py upgrade_db          # run migrations (has PG-crash-recovery retry logic)
python main.py collect_static      # collect static files (serves ui/dist)
python apps/manage.py makemigrations <app>
python apps/manage.py migrate

# i18n — .po files live in apps/locales/{en_US,zh_CN,zh_Hant}/LC_MESSAGES/
python apps/manage.py makemessages -l zh_Hant  # extract strings
python apps/manage.py compilemessages            # compile .po -> .mo (required at build time)
```

Frontend (`ui/`):
```bash
cd ui
npm ci
npm run dev          # admin SPA (Vite dev server, proxies /admin/api & /chat/api -> :8080)
npm run build        # build admin dist
npm run lint         # eslint --fix
npm run type-check   # vue-tsc
```

Python linting uses `ruff` (line length 120). Run the Django integration suite with `python apps/manage.py test litekb_api maxkb.test_runtime_profile system_manage.test_branding users.test_bootstrap` using an isolated PostgreSQL instance with pgvector and Redis.

Python requires 3.11. The image resolves the selected dependencies from `pyproject.toml` with `uv`, using `installer/build-dependencies.sh`. The studio installs from `ui/package-lock.json`.

## Architecture

### Settings: one project, two runtimes

`apps/maxkb/settings/` is split by the `SERVER_NAME` env var (set by `main.py` based on the service):
- `base/web.py` — full Django app (DB, cache, REST framework, all `INSTALLED_APPS`, templates, i18n). Default for `web`.
- `base/model.py` — minimal settings for the local-embedding model server. Selected when `SERVER_NAME=local_model`.
- `settings/__init__.py` imports `web` or `model` accordingly. This is why a missing/wrong `SERVER_NAME` silently loads the wrong app set.

All runtime config comes from the `CONFIG` singleton (`apps/maxkb/const.py` + `conf.py`). `MAXKB_CONFIG_TYPE=ENV` reads `MAXKB_*` env vars (the `.env` file uses this); otherwise it loads YAML from `/opt/maxkb/conf`. `CONFIG.get_db_setting()` / `get_cache_setting()` build the DB and Redis configs (with optional Redis Sentinel support).

### URL layout

Product and management surfaces:
- `/v1/*` — project-scoped knowledge and Run API. The Python SDK in `sdk/python/` uses this surface. See `docs/knowledge-api.md`, `docs/run-api.md` and `docs/product-sdk.md`.
- `/admin/api/*` — management API and authenticated studio debugging. Backed by DRF + drf-spectacular.
- `/chat/api/*` — retained machine chat and MCP interfaces. The admin and legacy chat prefixes are configurable.

The Vue studio builds to `ui/dist/admin`.

### Model provider abstraction (`apps/models_provider/`)

Each vendor implements `IModelProvider` in `impl/<vendor>_model_provider/` and registers its model types, credentials and classes with `ModelInfoManage`. OpenAI-compatible, vLLM and SiliconFlow adapters ship by default. See `apps/maxkb/capabilities.py` for media, extended-provider and local-inference options. Local inference uses operator-provided model weights. To add a model, register `ModelInfo` with a `MaxKBBaseModel` subclass and a `BaseModelCredential`.

### Application & chat (`apps/application/`, `apps/chat/`)

An "application" is a configurable agent. Two execution engines coexist:
- `chat_pipeline/` — older linear step pipeline (`PipelineManage` builder, steps in `step/`).
- `flow/` — the workflow engine. A graph of `step_node/*` nodes (start, ai_chat, search_knowledge, search_document, reranker, condition, tool, mcp, loop/*, variable_*, form, document_split/extract, knowledge_write, speech/text/image/video nodes, etc.). `workflow_manage.py` runs nodes concurrently on a `ThreadPoolExecutor`, streams output, and merges node details. Default workflows are seeded from `default_workflow*.json`. Specialized managers: `tool_workflow_manage`, `knowledge_workflow_manage`, `loop_workflow_manage` (and their `_loop_` variants).

Streaming chat responses go through `BaseToResponse` (`apps/common/handle/base_to_response.py`) with three impls: `system_to_response` (MaxKB SSE protocol), `openai_to_response` (OpenAI-compatible), `loop_to_response`. SSE frames are `data: <json>\n\n`.

### RAG / knowledge (`apps/knowledge/`)

Documents are split into paragraphs and indexed by pgvector. See `knowledge/vector/pg_vector.py` for vector queries and `knowledge/vector/hybrid.py` for independent lexical and vector candidates used by RRF. Tasks under `knowledge/task/` handle parsing and embedding. The labeled retrieval evaluation and client-side latency samples are under `benchmarks/`.

### Async jobs (`apps/ops/`)

Celery app `ops.celery` is named `LiteKB`. The worker consumes the `celery` and `model` queues and uses Redis as broker and result backend. Tasks use the custom `hmac_signed_serializer`. Historical scheduler tables are retained for upgrades. LiteKB does not start a scheduler or register web-sync jobs.

### MCP (`apps/chat/views/mcp.py`)

LiteKB applications can be exposed as MCP tools through the JSON-RPC methods `initialize`, `tools/list` and `tools/call` in `chat.mcp.tools.MCPToolHandler`. Workflows consume external MCP servers via `mcp_node` and `langchain-mcp-adapters`.

### Frontend (`ui/`)

The studio is built with `npm run build`. Its workflow canvas uses LogicFlow and its markdown editor is md-editor-v3. Env files are in `ui/env/`.

### Sandbox

`installer/sandbox.c` is compiled to `sandbox.so` (loaded via ctypes) to run untrusted Python from tools/nodes in a restricted namespace. Banned keywords/hosts come from `MAXKB_SANDBOX_PYTHON_BANNED_KEYWORDS` / `MAXKB_SANDBOX_PYTHON_BANNED_HOSTS`. Pre-installed packages for sandbox execution live under the path in `MAXKB_SANDBOX_PYTHON_PACKAGE_PATHS`.

## Coding Conventions

- Python line length: **120** (`.editorconfig`, `pyproject.toml`, Copilot rules).
- **Minimize diffs.** Do not reformat entire files, reflow lines, or rename unless required. Make the smallest possible change and preserve existing structure/formatting. (`.github/copilot-instructions.md`)
- Match the existing module header style (most files begin with a `# coding=utf-8` block-style docstring with `@project/@Author/@file/@date/@desc`).
- UI code follows the existing Vue 3 Composition API + `<script setup>` + Element Plus patterns; lint with `npm run lint` before finishing.
