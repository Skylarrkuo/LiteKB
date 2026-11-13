# LiteKB 知识库 API

产品后端通过 `/v1` 管理项目下的普通知识库。知识库只属于一个 API 项目。同一项目可使用多个服务密钥。管理员在控制台配置 Embedding 模型后，使用管理命令把模型或已有普通知识库授权给项目。

```sh
python apps/manage.py litekb_client crm --owner admin --issue crm-backend --model MODEL_UUID
python apps/manage.py litekb_client crm --issue crm-import --knowledge KNOWLEDGE_UUID
python apps/manage.py litekb_client crm --revoke CLIENT_UUID
```

首次签发需指定现有工作区的活跃用户。默认工作区为 `default`。可通过 `--workspace` 指定工作区，通过重复的 `--model`、`--knowledge` 和 `--agent` 参数授权多个资源。已有知识库的向量模型也需要授权。命令返回 `client_id` 和一次显示的 `service_key`。后端用 `Authorization: Bearer <service_key>` 调用。密钥以摘要保存。撤销密钥或停用项目所有者后，后续请求返回 HTTP 401。

例如在设置了 `BASE` 和 `KEY` 的服务端环境中发起一次入库：

```sh
curl -H "Authorization: Bearer $KEY" "$BASE/v1/models"
curl -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"name":"产品手册","description":"售后资料","embedding_model_id":"MODEL_UUID"}' "$BASE/v1/knowledge-bases"
curl -X POST -H "Authorization: Bearer $KEY" -F "file=@manual.pdf" \
  "$BASE/v1/knowledge-bases/KB_UUID/documents"
curl -H "Authorization: Bearer $KEY" "$BASE/v1/knowledge-bases/KB_UUID/documents"
curl -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"knowledge_base_ids":["KB_UUID"],"query":"如何申请售后","mode":"rrf","top_k":5}' "$BASE/v1/retrievals"
```

下表中 `K` 表示 `/v1/knowledge-bases/{knowledge_base_id}`，`D` 表示 `K/documents/{document_id}`，`P` 表示 `D/paragraphs/{paragraph_id}`。

| HTTP | 路径 | 参数与结果 |
| --- | --- | --- |
| GET | `/v1/models` | 已授权模型的 ID、名称、类型和状态 |
| GET、POST | `/v1/knowledge-bases` | 列出或创建。创建传入 `name`、`embedding_model_id` 及可选的 `description` |
| GET、PATCH、DELETE | `K` | 查询、修改或删除。可修改 `name`、`description`、`file_size_limit`（1～1000 MiB）、控制台批量上传的 `file_count_limit`（1～1000），以及 `embedding_model_id` |
| GET、POST | `K/documents` | 列出或导入。支持 JSON 的 `name` 加 `content` 或 `paragraphs`，也支持单文件 multipart。返回 `documents` 数组 |
| POST | `K/split` | multipart 上传 `file`，可传 `split_length`。返回预览文档的 `name`、`paragraphs`、`source_file_id`，可编辑后逐个提交到同库的 `K/documents` |
| DELETE | `K/split/{source_file_id}` | 丢弃预览原文件。已通过 API 导入的文档有自己的原件引用 |
| GET、PATCH、DELETE | `D` | 查询导入状态、改名、启停或删除。PATCH 接受 `name`、`is_active`、`hit_handling_method` 和 `directly_return_similarity`。命中策略及阈值也可在创建 JSON 文档时指定 |
| GET、PUT、DELETE | `D/source` | 下载、通过 multipart 的 `file` 替换或移除可下载的原件。无原件时 GET 返回 404。要同步检索正文，可通过分段 API 更新内容，或者重新导入为新文档 |
| GET、POST | `D/paragraphs` | 按位置分页或追加分段。新增传入 `content` 及可选的 `title`、`is_active` |
| GET、PATCH、DELETE | `P` | 查询、修改或删除文档内的分段 |
| GET、POST | `K/tags` | 列出或创建标签。传 `key` 和 `value`，已存在的键值组合返回 200 |
| GET、PATCH、DELETE | `K/tags/{tag_id}` | 获取、修改或删除标签。修改为同库已有键值组合返回 409 |
| GET、PUT | `D/tags` | 查看或替换文档标签。传 `{"tag_ids":["…"]}`，空数组清除所有关联；其中任一标签越界则整个请求返回 404 |
| GET、POST | `P/questions` | 查看或新增段落关联问题。传 `{"content":"如何申请售后？"}`，响应含关联 ID。相同问题再次关联返回 200 |
| GET、PATCH、DELETE | `P/questions/{question_id}` | 操作此段落的一条关联。修改同一问题在本段落的措辞后，其他段落继续使用原措辞。编辑和删除立即清理旧关联向量，并在事务提交后重建该文档索引 |
| GET | `K/export` | 导出 JSON。通过 `limit` 指定每页文档数（默认 25，最多 200）。有下一页时，响应头 `X-Next-After` 的值可用作下次请求的 `after` 参数 |
| POST | `K/import` | 以 `application/json` 导入一个导出页。成功返回 `created_documents` 和 `skipped_documents`。每页在独立事务内写入 |
| POST | `K/reindex`、`D/reindex` | 提交重建，返回 202。通过文档的 `index_status` 读取索引状态 |
| POST | `/v1/retrievals` | 指定 `knowledge_base_ids`、`query`，可传 `mode`（embedding、keywords、blend、rrf）、`top_k`（1～100）、`min_score`（0～2） |

列表接受 `limit`、`offset`，返回 `count/next/previous/results`。知识库创建、文档导入、分段创建返回 201，删除返回 204。列表和嵌套资源访问均根据已认证客户端项目过滤。越界资源返回 404，输入有误返回 400。

向已有库发送 `PATCH K`，请求体为 `{"embedding_model_id":"NEW_MODEL_UUID"}`，即可切换到本项目已授权且可用的向量模型。新配置立即可读。服务清理旧向量和维度相关索引，提交后逐文档重建。此期间检索可用的内容随索引逐步恢复，请通过文档的 `index_status` 查看进度。重复指定库当前的模型会保留已有索引。

文档命中策略 `optimization` 表示交给模型组织回答，`directly_return` 表示按 `directly_return_similarity` 阈值直接返回，阈值范围为 0～2。GET 文档响应包含这两个字段，JSON 导入导出也会保留它们。知识工作流的设计和发布由管理控制台提供。

上传支持 TXT、Markdown、PDF、DOCX、CSV、XLS、XLSX 和 HTML。解析完成后文档立即可见，Worker 在事务提交后执行向量化。检索命中包含库、文档、分段 ID，文档名称、段落位置、正文和相似度。模型或队列故障会反映在索引状态中，恢复后可用重建接口重新提交。

### 产品检索的排序与阈值

HTTP 请求省略 `mode` 时使用 `embedding`。纯向量检索适合语义相近的表达；`keywords` 按全文匹配排序；已有的 `blend` 给向量候选补算词法分。`rrf` 对每个获准知识库独立取向量和全文候选，能召回向量候选之外的型号、错误码等文本。服务按段落合并两个分支，已授权的多个知识库共享同一最终排名。

在普通应用的知识库参数、工作流「知识库检索」节点或知识库命中测试中，检索模式可选择「排名融合（RRF）」。保存并发布应用后，调用该版本的 Agent 会按此配置检索，后端字段为 `knowledge_setting.search_mode="rrf"`。普通应用和工作流沿用关联知识库使用相同向量模型的约定。API 独立检索支持多个已授权模型。工作流引用上一步的文档列表、禁用文档、排除已用分段等条件在两个召回分支选取候选前生效。调试结果与 Agent 送入提示词的段落均保留融合顺序。

`rrf` 返回的 `hits` 已按 `rank_score` 排序。该字段是段落在每个命中分支上 `1 / (60 + rank)` 的和，名次从 1 起。标题、分块和关联问题在同一分支命中同一段落时只记一票。`score` 保存候选记录中最高的余弦相似度加归一化全文相关度，用于 `score > min_score` 的过滤。产品展示命中时应保留数组顺序。已有 HTTP 模式的分数和排序契约继续生效。项目需要同时获准访问所请求的全部知识库和其当前使用的向量模型，任一缺少授权时整次请求返回 404。

48 条材料、32 个问题的实测和使用自己的模型复测的步骤见[检索质量评测](retrieval-quality.md)。

## 用 JSON 在两个产品间迁移内容

先在目标项目创建普通知识库并授权向量模型。用源项目密钥下载一页 JSON，再用目标项目密钥将该页提交至目标库。读取响应头中的 `X-Next-After` 并继续下一页，直到该响应头消失。

```sh
curl -fsS -D export.headers -o content.json -H "Authorization: Bearer $SOURCE_KEY" \
  "$BASE/v1/knowledge-bases/$SOURCE_KB/export?limit=25"
curl -fsS -H "Authorization: Bearer $TARGET_KEY" -H "Content-Type: application/json" \
  --data-binary @content.json "$BASE/v1/knowledge-bases/$TARGET_KB/import"
```

JSON 格式可直接生成。下例包含文档启停状态、标签、按顺序排列的分段和关联问题。

```json
{
  "format": "litekb.knowledge.v1",
  "tags": [{"key":"产品线","value":"桌面端"}],
  "documents": [{
    "key":"046d5cc2-3bc3-494b-8dd7-28f26a86fd9c",
    "name":"售后手册",
    "is_active":true,
    "tags":[{"key":"产品线","value":"桌面端"}],
    "paragraphs":[{"title":"保修","content":"保修期为两年。","is_active":true,"questions":["保修期有多久？"]}]
  }]
}
```

`key` 是文档的稳定 UUID，可由接入方生成。相同内容和键再次提交会跳过，键冲突且内容变化时返回 409，该页写入全部回滚。新文档在目标库生成自己的文档、段落和关联 ID，使用目标库的模型重新索引。文档标签应在顶层 `tags` 中声明。原文件和嵌入图片需通过产品自己的附件流程另行迁移，Markdown 中的链接按原文字保存。单请求体积受服务配置 `MAXKB_DATA_UPLOAD_MAX_MEMORY_SIZE` 约束。
