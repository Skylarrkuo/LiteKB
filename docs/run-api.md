# LiteKB 运行 API

一个业务产品对应一个 Project。ServiceClient 标识该产品的后端，服务端签发的密钥放在 `Authorization: Bearer <key>`。每次运行请求还要传 `X-LiteKB-Subject`，由产品后端填写已登录用户的稳定标识。Run、会话、取消、表单续跑和事件读取均校验调用方、用户以及 Agent 授权。不要将服务密钥发给浏览器。

## 创建运行

先在控制台发布应用，再用 `litekb_client` 向项目授权应用和所需的模型、知识库及子应用。完整的签发参数见[知识库接入文档](knowledge-api.md)。

```sh
curl -i -X POST "$BASE/v1/agents/$AGENT_ID/runs" \
  -H "Authorization: Bearer $KEY" -H "X-LiteKB-Subject: customer-42" \
  -H "Content-Type: application/json" -H "Idempotency-Key: order-question-1" \
  -d '{"message":"这个订单可以退货吗？","max_runtime_seconds":120}'
```

HTTP 202 返回 `id`、`session_id`、`agent_id`、`version_id`、`status` 和详情地址 `Location`。同一调用方与用户重复提交相同的幂等键和参数会获得同一个 Run，修改参数后重用该键返回 409。新一轮提问可带已有 `session_id`。同一会话同时只接受一个活动或等待表单的 Run。可选的 `form_data` 传入工作流入口参数。

| 操作 | 路径 | 结果 |
| --- | --- | --- |
| 可用 Agent | `GET /v1/agents` | 项目已授权且已发布的 Agent 及最新版本 |
| 运行列表 | `GET /v1/agents/{id}/runs` | 当前调用方和用户的运行，可按 `session_id` 过滤，支持 limit 和 offset |
| 查询 | `GET /v1/runs/{id}` | 状态、最近已提交的事件号 `event_sequence`、步骤、耗时、尝试次数和记录引用，完成后有结果与 token 用量 |
| 读事件 | `GET /v1/runs/{id}/events` | SSE，每条事件有递增 `id`、事件名及 JSON |
| 提交表单 | `POST /v1/runs/{id}/resume` | 提交 `{"waiting_event_id":17,"node_data":{...}}`，恢复同一运行与聊天记录 |
| 取消 | `POST /v1/runs/{id}/cancel` | 立即持久化终态，关停该 Run 的后续写入，已进入外部系统的操作可能继续 |

流会发送 `run.queued`、`run.running`、`answer.delta`、步骤事件以及最终状态。产品端持久保存最后处理的事件编号，重连时使用 `Last-Event-ID` 或 `?after=N`，只会返回该编号之后的事件。等待表单和终态时流结束；活动运行的连接会定期关闭以释放 HTTP 工作线程，可继续按编号连接。需要鉴权请求头时使用支持流式读取的 HTTP 客户端。

游标从 0 开始，每个 Run 单独编号。处理事件后再保存游标；客户端在处理和保存之间崩溃，重连可以再次收到同一事件，按 `(run_id, id)` 去重。当流正常结束且没有新事件时，取运行详情。如果 `event_sequence` 大于本地游标，继续补读。如果已经追平且状态为终态或 `waiting_input`，可以结束本次订阅。等待表单时，回传详情中的 `result.waiting_event_id`，收到 202 后从原游标继续读同一 Run。过期表单号或非等待状态返回 409。首次等待兼容只提交 `node_data` 的旧客户端，从第二次等待起需要当前表单号。升级前已等待的运行可使用详情的 `event_sequence`。每个活动 SSE 连接最长约 60 秒，空闲时约每 10 秒发送注释心跳。

```sh
curl -N "$BASE/v1/runs/$RUN_ID/events" \
  -H "Authorization: Bearer $KEY" -H "X-LiteKB-Subject: customer-42" -H "Last-Event-ID: 0"
```

## 执行与存储

Run 在提交时固定顶层已发布的 ApplicationVersion。Celery worker 调用原有问答管道或工作流引擎。RunStep 的 `output_ref.chat_record_id` 与 `output_ref.path` 指向该记录的 `details`，循环迭代含索引，子应用引用自己的聊天记录。提交工作流表单后，重新执行的步骤增加 attempt。保留已发布 Agent 的常规删除语义，删除其发布版本会一并删除相关运行轨迹。

执行状态为 `queued`、`running`、`waiting_input`、`succeeded`、`failed` 或 `cancelled`。`max_runtime_seconds` 默认 300，范围 1 至 3600。`budget.used_runtime_seconds` 在每次执行转入等待或终态时结算，包含阻塞调用和该次执行的工作流开销，排队与等待表单的时间不计入。续跑从剩余额度开始。用尽返回 `failed` 和 `error: "timeout"`。

### Worker 重启与工具写入

| 故障时点 | 可观察行为 |
| --- | --- |
| 运行已经入库，消息发布失败或 Redis 回执丢失 | 保留 `queued`。Worker 对超过 60 秒仍未领取的运行重新投递。消息携带本轮队列序号，数据库行锁保证一个序号最多领取一次。 |
| Worker 已领取运行后崩溃 | 租约 30 秒，正常每 5 秒续约。现存或重启的 Worker 每 10 秒检查一批到期运行，访问详情、事件流或后续会话轮次也会检查。到期后记录 `failed / worker_lost` 并释放会话。如果预算先耗尽则为 `timeout`。已领取的运行不会自动从头执行。 |
| 写入型节点抛错、MCP 对端返回错误或响应丢失 | 保留提前提交的 `tool.dispatched` 事件，运行以 `tool_outcome_unknown` 失败。到对端核对实际结果，使用同一个创建幂等键可以查询原 Run。 |
| 相同逻辑调用再次派发 | 同一 Run 同一节点路径的写入派发只允许一次。模型选用的 MCP 与工作流工具按当前位置、工具标识和规范化参数去重。重复派发返回 `effect_already_dispatched`。循环索引和子工作流路径区分不同迭代。 |
| 工具阻塞时调用取消，或超过剩余预算 | 取消在接口返回时可见，独立续约线程在截止时间终止运行。已准入的调用可能在供应商处完成，迟到的 Run 事件、结果和聊天记录写回会被拒绝。 |

派发记录只证明 LiteKB 已允许该次调用，不能判断工具是否已经提交外部事务。进程可能在记录提交与实际发出请求之间退出，也可能在外部提交后丢失响应。并行分支中已经准入的操作可能各自完成。调用方重建 Run、人工再执行、工具代码自身重试，或以不同参数表达同一业务操作，都可能产生新的外部写入。涉及付款、发券等动作时，把业务操作 ID 传给工具，由对端持久化去重。

Run 固定顶层版本，调用子应用与工具工作流时仍解析其已发布版本。节点线程、子应用、工具工作流与循环传递 Run 的取消和租约上下文。Python、工具库、MCP、知识写入，以及可选的图像、视频和语音合成节点会在进入调用前登记。模型选用的 MCP、工作流工具和技能命令也使用派发记录。用户代码内部的网络请求、外部服务内部重试以及已启动的沙箱子进程由各自实现控制。若底层调用长时间不返回，原 worker 线程可能继续占用容量，终态及 SSE 回放仍可查询。

聊天记录与工具工作流快照写入 PostgreSQL，Redis 用于任务投递。Worker 在聊天记录提交前退出时，该轮可能缺少 `RunStep` 输出引用，已提交的 SSE 和派发记录仍可读取。长期记忆沿用独立的 Celery 任务，在 Run 成功后调度，不占本次预算。成功状态提交后发生故障可能导致本次记忆提取未派发。

升级含运行租约的版本时，先停止旧版 Worker，再执行迁移并启动新 Worker。迁移保留历史记录，新 Worker 会将缺少租约的遗留 `running` 运行终止为 `worker_lost`。多主机部署需要同步系统时钟。
