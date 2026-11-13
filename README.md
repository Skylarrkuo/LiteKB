<img src="ui/public/litekb.svg" width="56" alt="LiteKB">

# LiteKB

LiteKB is a self-hosted RAG and agent workflow service. Your product owns the user interface and identity. Its backend can ingest documents, retrieve cited passages, call a published agent and resume a workflow waiting for user input. Operators manage knowledge, debug drafts, publish agents and inspect runs in the studio. [简体中文](README_CN.md)

## What runs

| Component | Responsibility |
| --- | --- |
| API and studio | Django serves the project-scoped `/v1` API and management endpoints. The Vue studio includes the workflow editor, debug chat, tools and brand settings |
| Worker | Celery indexes documents and executes agents. The graph engine supports branching, loops, subagents, forms and MCP tools |
| PostgreSQL with pgvector | Stores knowledge, vectors, published versions, conversations, node results and replayable run events |
| Redis | Provides the task broker, cache and task coordination |

The default installation uses remote model inference. Administrators can change the studio name and icon under **Settings → System branding** and import compatible online tools from the upstream catalog. The default studio build is about 28.3 MB of static files. The main JavaScript entry is about 0.71 MB compressed. [Architecture and build measurements](docs/architecture.md)

## Run locally with Docker

Run the following from the repository root. You need Docker with Linux containers, Compose v2, Python 3 for initial credential generation, and network access to the image and package registries during the first build.

```sh
python installer/init_env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
curl -fsS http://127.0.0.1:8080/admin/api/capabilities
```

The initializer writes `LITEKB_DB_PASSWORD`, `LITEKB_REDIS_PASSWORD`, `LITEKB_SECRET_KEY` and `LITEKB_ADMIN_PASSWORD` to a root `.env`. If the file exists, it adds missing settings and preserves existing credentials. Sign in as `admin` with the local `LITEKB_ADMIN_PASSWORD`. This value initializes the first account in a new database. The default listener is `127.0.0.1:8080`. Set `LITEKB_BIND` and `LITEKB_PORT` to change it. [Open the studio](http://127.0.0.1:8080/admin/)

## Connect your first product

1. Add an embedding model and a chat model in **Settings → Models**. The default providers include OpenAI, Alibaba Cloud Model Studio (Qwen), Xiaomi MiMo, DeepSeek, vLLM and SiliconFlow. Selecting a model loads its endpoint and parameter form. [Model catalog and API examples](docs/model-providers.md)
2. Create a basic knowledge base using the embedding model. Bind it to a simple agent or connect retrieval and answer nodes on a workflow. Try a question in debug chat and publish the agent.
3. Issue a server-side service key for the product. Set the variables below to the resource UUIDs you created. Grant the knowledge base's embedding model and any child agents used by your workflow.

An administrator can look up resource names and IDs in the default workspace with this read-only command.

```sh
docker compose exec api python apps/manage.py shell -c "from models_provider.models import Model; from application.models import Application; from knowledge.models import Knowledge; print([(m.__name__, list(m.objects.filter(workspace_id='default').values_list('name', 'id'))) for m in (Model, Knowledge, Application)])"
```

Set the shell variables to the selected IDs and issue the key.

```sh
docker compose exec api python apps/manage.py litekb_client support \
  --owner admin --issue support-backend \
  --model "$EMBEDDING_ID" --model "$LLM_ID" --knowledge "$KB_ID" --agent "$AGENT_ID"
```

The command prints a client ID and a service key once. Store the key in your product backend. A project may issue multiple keys, and each knowledge base belongs to one product project. To revoke one client, run `litekb_client support --revoke CLIENT_UUID` through the same management entry point.

### Ingest and retrieve a passage

The HTTP examples use a POSIX shell, curl and jq. Set `KEY` to the issued key. Use the `KB_ID` and `AGENT_ID` from the preceding step. A successful upload returns its document ID. The worker builds the index after the database transaction commits.

```sh
BASE=http://127.0.0.1:8080
AUTH="Authorization: Bearer $KEY"
curl -fsS -H "$AUTH" "$BASE/v1/agents"

DOC_ID=$(curl -fsS -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"Support handbook","content":"The standard warranty lasts two years."}' \
  "$BASE/v1/knowledge-bases/$KB_ID/documents" | jq -er '.documents[0].id')
curl -fsS -H "$AUTH" "$BASE/v1/knowledge-bases/$KB_ID/documents/$DOC_ID" | jq '.index_status'
```

Once the status is `success`, retrieve the matching text. Hits include the document ID, paragraph ID and score. Products can also create their own knowledge bases, upload files, manage paragraphs, tags and related questions, and import or export JSON. [Knowledge API reference](docs/knowledge-api.md)

```sh
curl -fsS -H "$AUTH" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg id "$KB_ID" '{knowledge_base_ids:[$id],query:"How long is the warranty?",mode:"blend",top_k:3}')" \
  "$BASE/v1/retrievals" | jq '.hits'
```

### Run an agent and read events

Supply a stable user identifier from your backend in `X-LiteKB-Subject`. Reuse the same idempotency key when retrying one request. Use a new key for another turn.

```sh
SUBJECT='X-LiteKB-Subject: customer-42'
RUN_ID=$(curl -fsS -H "$AUTH" -H "$SUBJECT" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: support-ticket-42-turn-1' \
  -d '{"message":"How long is the standard warranty?","max_runtime_seconds":120}' \
  "$BASE/v1/agents/$AGENT_ID/runs" | jq -er '.id')
curl -N -H "$AUTH" -H "$SUBJECT" "$BASE/v1/runs/$RUN_ID/events"
curl -fsS -H "$AUTH" -H "$SUBJECT" "$BASE/v1/runs/$RUN_ID" | jq '{status,session_id,result}'
```

Reconnect with `Last-Event-ID` to replay later events. At `waiting_input`, post `node_data` and the current form's `waiting_event_id` to `/v1/runs/{id}/resume`. Start the next turn with the returned `session_id`. The studio's runs page shows the pinned top-level version, loop iterations, timings and output references. [Run API reference](docs/run-api.md)

Python backends can install the standard-library client with `python -m pip install ./sdk/python`. Use `Client.retrieve` for ranked passages, then `start_run` and `stream_text` for streamed answers. The SDK handles SSE parsing and reconnects from the last event ID. Its default retrieval mode, `rrf`, fuses separately ranked vector and keyword candidates. [Integration example](examples/product_agent.py) · [SDK guide](docs/product-sdk.md) · [Retrieval quality and time to first text](docs/validation.md)

## Build options

| Root `.env` setting | Included capability |
| --- | --- |
| `LITEKB_MEDIA_NODES=1` | Speech, image generation and video nodes, their frontend components and media dependencies |
| `LITEKB_EXTENDED_PROVIDERS=1` | Additional model provider adapters |
| `LITEKB_LOCAL_MODEL=1` | Local embedding and reranking dependencies. Also use the `local-model` Compose profile and supply the weights |

Rebuild after changing these options. API and worker use the same image. Build from the repository root so the Dockerfile can access both frontend and backend sources.

```sh
# Build the Compose image and launch its services
docker compose build api
docker compose up -d --wait
# Build a standalone local image
docker build -f installer/Dockerfile -t litekb:local .
# With local inference enabled in .env
docker compose --profile local-model up -d --build --wait
```

## Upgrade, develop and troubleshoot

Before upgrading, back up PostgreSQL and storage, retain your signing and service credentials, and stop the old workers. The API applies migrations and collects static files at startup. The migration retires old scheduled triggers. Enable the matching build options if existing workflows depend on media nodes or an extended provider.

| Symptom | What to check |
| --- | --- |
| HTTP 401 or 404 | Verify the service key, project grants and resource IDs. A run belongs to the client and subject that created it |
| Documents return no hits | Check document activation, indexing status, embedding model availability and worker logs |
| A run stays queued | Check worker health and Redis connectivity. For delayed SSE delivery, inspect reverse-proxy buffering |
| An imported graph contains a disabled node | Read `/admin/api/capabilities` and check the image build options |

```sh
docker compose logs --tail=100 api worker
docker compose exec api python apps/manage.py check
docker compose exec api python apps/manage.py migrate --check
```

The backend uses Python 3.11 and Django 5.2. The studio uses Vue 3 and Vite. In `ui/`, run `npm ci` and `npm run dev` for development or `npm run build` for a type-checked production build. Backend development uses separate `python main.py dev` and `python main.py dev celery` processes. Database, Redis, Linux sandbox and regression-test instructions are in the [deployment guide](docs/deployment.md) and [repository guide](AGENTS.md).

LiteKB derives from the MaxKB Community Edition and uses GPL-3.0. [License](LICENSE)
