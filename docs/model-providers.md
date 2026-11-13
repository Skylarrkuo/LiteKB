# 模型供应商与接入

模型目录按 2026-11-12 可查的供应商官方文档核对。打开「设置 → 模型 → 添加模型」，选供应商和模型类型。控制台会选择该类型的预设模型，填入模型名称、端点和参数。输入自己的 API Key 就能验证并保存。选择其他模型会重新加载对应配置；已填写的显示名称会保留。账号专属域名、地域和密钥以供应商控制台为准。

打开「高级设置」可直接调整本模型支持的设置，例如推理强度、输出长度、向量维度或音色。需要自定义网关参数时展开「编辑参数定义」。模型名称接受手工输入；未收录的模型使用该供应商及类型已有的通用适配，新模型采用不同协议时需要相应适配器。目录来自随版本发布的预设，实际模型访问权限由 API Key 所属账号决定。

| 供应商 | 常用模型 | LiteKB 的调用方式 |
| --- | --- | --- |
| OpenAI | `gpt-6.1-sol`、`gpt-6.1-terra`、`gpt-6-astra`、`gpt-6-luna`、`text-embedding-3-small/large` | 新推理模型使用 Responses，旧聊天模型和自定义兼容模型保留 Chat Completions。向量走 Embeddings，媒体选装包含文件转写、语音合成和图像生成。具体支持的推理档位随模型切换。[OpenAI 模型目录](https://developers.openai.com/api/docs/models) · [退役公告](https://developers.openai.com/api/docs/deprecations) |
| 阿里云百炼（千问） | `qwen3.8-max`、`qwen3.7-plus`、`qwen3.8-flash`、`qwen3.7-text-embedding`、`qwen3.7-text-rerank` | 对话、视觉、向量和重排使用对应适配器。向量维度选项随模型变化。使用专属地域端点时请从对应工作空间复制地址，重排与对话使用不同的请求路径。[百炼模型列表](https://help.aliyun.com/zh/model-studio/models) · [向量](https://help.aliyun.com/zh/model-studio/embedding-interfaces-compatible-with-openai) · [重排](https://help.aliyun.com/zh/model-studio/text-rerank-api) |
| 小米 MiMo | `mimo-v2.6-flash`、`mimo-v2.6-pro`、`mimo-v2.6-pro-ultraspeed` | 三者支持对话与视觉理解。思考模式默认开启；关闭后可调温度及 Top P。输出预算同时包括推理和回答。UltraSpeed 需相应授权。语音选装可使用 `mimo-v2.5-asr` 转写 WAV/MP3，以及预置音色或文字描述音色的 TTS。[模型列表](https://mimo.mi.com/docs/en-US/quick-start/model) · [推理](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/other/deep-thinking) · [语音接口](https://mimo.mi.com/docs/en-US/api/audio/tts-post) |
| DeepSeek | `deepseek-flash`、`deepseek-v4-pro` | 两者支持工具与推理；视觉入口提供 Flash。推理档位为 `low/high/max`，并按型号与思考模式处理采样参数。旧 Flash 标识可继续用于已有配置。[模型列表](https://api-docs.deepseek.com/quick_start/pricing/) · [推理参数](https://api-docs.deepseek.com/guides/thinking_mode/) |

### 请求示例

下列请求体展示不同适配器发送的参数，供与供应商调试台核对。OpenAI Responses 的文字输入可写成下面的形式。

```json
{"model":"gpt-6.1-sol","input":"概括这段知识库内容。","reasoning":{"effort":"medium"},"max_output_tokens":2048}
```

百炼向量模型从 `/compatible-mode/v1/embeddings` 接收文本和维度。例如，`qwen3.7-text-embedding` 支持 1024 维；一套已建索引的知识库应使用相同的模型和向量维度执行入库与查询。

```json
{"model":"qwen3.7-text-embedding","input":["退货申请须在签收后七日内提交。"],"dimensions":1024}
```

小米 MiMo 和 DeepSeek 均接受 Chat Completions，输出上限的字段分别是 `max_completion_tokens` 和 `max_tokens`。预设采用 8192 tokens 作为 LiteKB 的初始预算，可按工作流调整。

```json
{"model":"mimo-v2.6-flash","messages":[{"role":"user","content":"总结这段材料。"}],"thinking":{"type":"enabled"},"max_completion_tokens":8192}
```

```json
{"model":"deepseek-flash","messages":[{"role":"user","content":"根据证据回答问题。"}],"thinking":{"type":"enabled"},"reasoning_effort":"high","max_tokens":8192}
```

产品后端继续使用 LiteKB 的服务密钥调用发布的 Agent。供应商 API Key 只需配置在 LiteKB 控制台。媒体能力受部署选项控制。[产品接入](product-sdk.md) · [部署选项](deployment.md)
