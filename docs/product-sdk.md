# 将 LiteKB 嵌入业务产品

Python 3.10 及以上可使用仓库内的同步 SDK。它只依赖标准库，通过 `/v1` 访问知识库、发布版本和 Run。服务密钥保存在产品后端。前端接收产品后端转发的文本或事件。

```sh
python -m pip install ./sdk/python
```

## 上传产品知识

以下示例中的 `LITEKB_URL` 是服务根地址，例如 `http://127.0.0.1:8080`。管理员提前为项目授权向量模型。业务端用创建文档返回的 ID 查询索引状态，文档状态变为 `success` 后可发起检索。

```python
import os
from litekb_client import Client

api = Client(os.environ["LITEKB_URL"], os.environ["LITEKB_KEY"])
kb = api.create_knowledge_base("售后手册", os.environ["LITEKB_EMBEDDING_ID"])
doc = api.add_text(kb["id"], "保修政策", "标准保修期为两年。")
state = api.document(kb["id"], doc["id"])["index_status"]
# 在产品的状态轮询或后台任务中确认 state == "success" 后执行
hits = api.retrieve([kb["id"]], "保修期多久？", top_k=3)
```

SDK 默认采用 `rrf` 双路融合。业务端可保留结果中的文档和分段标识，用于展示来源或回读正文。文件上传、标签、原件维护、分页导入导出和授权细节见[知识库 API](knowledge-api.md)。

## 调用已发布的 Agent

每个请求从产品登录态取得稳定的用户标识，并从产品数据库取得该条消息的唯一 ID 作为幂等键。后续轮次复用返回的 `session_id`。同一业务消息因网络超时需要重试时，使用原消息、用户和原幂等键重新调用 `start_run`。

```python
user_api = Client(os.environ["LITEKB_URL"], os.environ["LITEKB_KEY"], subject="customer-42")
run = user_api.start_run(os.environ["LITEKB_AGENT_ID"], "我的保修期有多长？",
                         idempotency_key="ticket-42-message-1", max_runtime_seconds=120)
for text in user_api.stream_text(run["id"]):
    print(text, end="", flush=True)
detail = user_api.run(run["id"])
print(detail["status"], detail["result"].get("sources", []))
```

如需表单或过程展示，改用 `events(run_id, after=last_id)`。每次处理完成后持久化事件编号，产品重启后传入上次编号。SDK 在连接中断后按编号续读，读取重试次数由 `max_retries` 控制。业务端如果先写入消息、再保存游标并在两步之间崩溃，会重新收到同一条事件，可用 `(run_id, event.id)` 对消息存储去重。

```python
for event in user_api.events(run["id"], after=saved_cursor):
    deliver_and_save_cursor(run["id"], event.id, event.kind, event.data)  # 产品自己的持久化操作
    if event.kind == "run.waiting_input":
        show_form_to_user(run["id"], waiting_event_id=event.id)
```

用户提交表单时调用 `user_api.resume(run_id, fields, waiting_event_id=shown_event_id)`，随后从该事件号继续读取。用户主动停止时调用 `user_api.cancel(run_id)`。超时、取消和外部写入的处理规则见[Run API](run-api.md)。

## 在自己的部署复测

仓库里的[产品后端示例](../examples/product_agent.py)可直接通过环境变量运行。[首字延迟脚本](../examples/measure_ttft.py)从提交请求前开始计时，直到产品客户端收到首个含可见文本的事件，并记录提交、首字和完成耗时。每个样本使用独立会话、独立幂等键，预热不计入分位数。等待表单、执行失败或没有文本的运行会列入原始样本，并导致命令以非零退出。

```sh
# 设置 LITEKB_URL、LITEKB_KEY、LITEKB_AGENT_ID 后执行
python examples/measure_ttft.py --warmup 2 --samples 20 --message "标准保修期有多长？"
```

质量和延迟的实测口径与结果见[验收记录](validation.md)。
