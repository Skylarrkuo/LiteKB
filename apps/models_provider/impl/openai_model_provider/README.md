# OpenAI 模型适配

已于 2026-11-12 按 OpenAI 官方文档核对。模型选择器会给出每个模型的官方说明链接。项目 API Key 可用的模型仍取决于 OpenAI 项目的授权。[模型目录](https://developers.openai.com/api/docs/models)

| LiteKB 模型类型 | 默认模型 | 工作流调用方式 |
| --- | --- | --- |
| LLM | `gpt-6.1-sol` | GPT-6、5.6、5.5、5.4 系列通过 `/v1/responses` 生成文本、流式输出或执行工具调用。表单按具体模型列出推理强度。[模型选择与接口约束](https://developers.openai.com/api/docs/guides/latest-model) |
| IMAGE | `gpt-6.1-terra` | 同一 Responses 端点接受文本和图片输入，输出文本。[模型说明](https://developers.openai.com/api/docs/models/gpt-6.1-terra) |
| EMBEDDING | `text-embedding-3-small` | `/v1/embeddings`。small 默认 1536 维，large 默认 3072 维，两者都允许指定较低维数。已有知识库更改模型或维数后须重建文档向量。[向量嵌入](https://developers.openai.com/api/docs/guides/embeddings) |
| STT | `gpt-transcribe` | 已录好的音频通过 `/v1/audio/transcriptions` 上传，可设置语言和关键词。带说话人标签的旧型号使用 `diarized_json`，节点交付其文本。[文件转录](https://developers.openai.com/api/docs/guides/speech-to-text) |
| TTS | `gpt-4o-mini-tts` | `/v1/audio/speech` 默认输出 MP3，可设置音色和朗读指令。OpenAI 计划于 2027-01-06 停用现有 Speech 型号，官方推荐的 Realtime 音频模型需要单独的会话协议。[语音合成](https://developers.openai.com/api/docs/guides/text-to-speech) · [停用日期](https://developers.openai.com/api/docs/deprecations) |
| TTI | `gpt-image-2.6-flare` | `/v1/images/generations` 返回 base64 图像。2.6 提供 `complexity`，2.5 和 2.6 均允许 `xhigh`、`max` 画质。[模型参数](https://developers.openai.com/api/docs/guides/image-prompting) |

现代推理模型默认发送 `store=false`。工作流从消息中读取文本，后续工具回合复用原有的有序输出项，包括加密推理和函数调用 ID。旧对话模型及未知的自定义模型 ID 沿用 Chat Completions 接口。[无状态工具调用](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses)

语音和图片生成需要启用对应媒体功能。历史 DALL·E 3 和旧 GPT 配置仍可读取，官方已关闭的模型从新建列表中移除。OpenAI 于 2026-09-24 关闭 Sora 2 和 Videos API，当前目录未提供 OpenAI 视频生成模型。[停用记录](https://developers.openai.com/api/docs/deprecations)

用 `python apps/manage.py test models_provider.impl.openai_model_provider.test_models` 运行离线契约测试。测试使用真实 SDK 和本地 HTTP 模拟传输，覆盖同步、异步、流式、工具回合、向量顺序和媒体请求格式。
