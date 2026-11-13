# 阿里云百炼

LiteKB 的供应商 ID 为 `aliyun_bai_lian_model_provider`。模型条目提供准确的模型 ID、用途、按型号生成的参数表单及官方说明链接。保存的自定义型号继续按模型类型和协议创建实例。

## 工作空间和密钥

在百炼控制台选择开通模型的地域与业务空间，复制对应的 API Key 和服务地址。北京工作空间的兼容地址示例为 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`，原生接口地址以 `/api/v1` 结尾。适配器会在同一工作空间、同一地域切换这两个后缀。已有配置仍支持旧版北京公共端点。账户开通范围、地域与服务地址决定可调用的具体型号。向量和重排保留历史密钥字段 `dashscope_api_key`，其他类型使用 `api_key`。[端点与地域](https://help.aliyun.com/zh/model-studio/regions) · [北京端点](https://help.aliyun.com/zh/model-studio/beijing-access-information)

## 核心能力

| 用途 | 已接入的代表型号 | 请求与配置 |
| --- | --- | --- |
| 文本、工具调用 | qwen3.8-max / flash、qwen3.7-plus、qwen-plus | Chat Completions；支持流式输出、工具调用历史、temperature、max_tokens、top_p、top_k、seed。适用型号可设置 enable_thinking、thinking_budget。 |
| 视觉理解 | qwen3.8-max / flash、qwen3.7-plus、qwen3-vl-plus / flash、qwen-vl-max | 同一兼容接口接收文本和 image_url，返回文本。 |
| 知识库向量 | qwen3.7-text-embedding / flash、text-embedding-v1 至 v4 | v1/v2 固定为 1536 维，兼容旧记录中的 dimensions 字段。v3/v4、3.7 系列仅提供型号支持的维度。客户端分批并按响应 index 还原顺序。 |
| 段落重排 | qwen3.7-text-rerank、qwen3-rerank、gte-rerank-v2、qwen3-vl-rerank | 原生 text-rerank 接口。top_n 按候选数量截断；Qwen 文本型号支持 instruct。VL 重排接收结构化文本，结果保留段落引用及 relevance_score。 |

RAG 可以启用 `use_query_type`，让查询通过 DashScope 原生接口使用 `text_type=query`。3.7 系列及 v4 还可填写英文检索指令 `instruct`；填写指令同样启用原生查询。入库保持普通文档向量，请求中不带查询指令。两项均留空或关闭时沿用兼容接口。[查询与文档向量](https://help.aliyun.com/zh/model-studio/embedding)

`qwen4-max-preview` 为 Token Plan 专有型号，通用业务空间目录未预设。官方对文本生成、视觉、向量和重排分别列出支持地域、计费与模型限制。[聊天接口](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions) · [思考模式与 Token Plan 限制](https://help.aliyun.com/zh/model-studio/deep-thinking) · [视觉理解](https://help.aliyun.com/zh/model-studio/vision-model/) · [重排接口](https://help.aliyun.com/zh/model-studio/text-rerank-api)

## 可选媒体节点

- **文生图**支持 Qwen Image 3.0、2.0、各自的 Pro 型号与历史 Wanx。可设置分辨率、张数、随机种子、提示词扩写和水印。Qwen 同步返回图片地址，Wanx 异步轮询。[Qwen Image 3.0](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference) · [Qwen Image 2.0](https://help.aliyun.com/zh/model-studio/qwen-image-api)
- **文生与图生视频**支持 Wan 3.0 Video、Video Prime 与 Wan 2.7/2.2/2.1 的对应型号。Wan 3.0、2.7 使用原生异步接口，文本节点支持宽高比，图像节点传首尾帧。轮询当前地域的任务 ID，返回成品视频链接。[Wan 3.0](https://help.aliyun.com/zh/model-studio/wan3-video-generation-api-reference) · [文生视频](https://help.aliyun.com/zh/model-studio/text-to-video-api-reference) · [图生视频](https://help.aliyun.com/zh/model-studio/image-to-video-general-api-reference)
- **录音转写**支持 Qwen-Audio 3.0/3.1 ASR Flash、Qwen3-ASR-Flash 与旧的 Omni、Paraformer。3.0/3.1 发送录音真实格式，可选择输入采样率、热词表；3.1 可保留方言。Qwen3-ASR 提供语言和数字规范化。[Qwen-Audio ASR](https://help.aliyun.com/zh/model-studio/qwen-audio-asr-http-api) · [Qwen3 ASR](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)
- **语音合成**支持 Qwen-Audio 3.0/3.1 TTS Plus/Flash、Qwen3-TTS Flash/Instruct 与旧 CosyVoice。Qwen-Audio 可设置音色 ID、格式、采样率、速率、音调、音量与指令。每个预设使用本型号支持的默认音色。Qwen3 接收系统音色与语言，Instruct 支持朗读指令。[Qwen-Audio TTS](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api) · [音色列表](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list) · [Qwen3-TTS](https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide)

媒体模型类型受 `LITEKB_MEDIA_NODES` 控制。核心四类以及新一代原生媒体 HTTP 实现复用现有 OpenAI/LangChain 或 HTTP 客户端。旧 Paraformer 和 Sambert 在实际执行时加载可选 DashScope SDK，Paraformer 音频转换还使用 pydub 和 FFmpeg。旧 CosyVoice 使用可选媒体组的 WebSocket 客户端。

## 验证

保存文本、视觉、向量、重排配置时，会使用提交的参数向目标模型发送一次小请求，可能产生该账户的推理费用。新一代媒体配置通过 API Key 查询该工作空间的精确模型条目；可见性检查不包含生成权限、余额或推理质量验证。旧 Paraformer 仍用仓库样本检查录音识别。[百炼模型列表接口](https://help.aliyun.com/zh/model-studio/list-models)

在仓库根目录将 `PYTHONPATH` 设为 `apps`，运行 `python -m unittest models_provider.impl.aliyun_bai_lian_model_provider.test_provider`。回归使用模拟 HTTP 响应，检查 SDK 序列化后的请求、鉴权头、输出映射、批次顺序、参数和任务轮询，无需密钥。
