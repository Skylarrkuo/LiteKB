from pathlib import Path

from django.utils.translation import gettext as _
from models_provider.base_model_provider import IModelProvider, ModelInfo, ModelInfoManage, ModelProvideInfo, ModelTypeConst
from .credential.embedding import AliyunBaiLianEmbeddingCredential
from .credential.image import QwenVLModelCredential
from .credential.itv import ImageToVideoModelCredential
from .credential.llm import BaiLianLLMModelCredential
from .credential.media import MediaCredential
from .credential.reranker import AliyunBaiLianRerankerCredential
from .credential.stt import AliyunBaiLianDefaultSTTModelCredential, AliyunBaiLianSTTModelCredential
from .credential.stt.asr_stt import AliyunBaiLianAsrSTTModelCredential
from .credential.stt.omni_stt import AliyunBaiLianOmiSTTModelCredential
from .credential.tti import QwenTextToImageModelCredential
from .credential.tts import AliyunBaiLianTTSModelCredential
from .credential.ttv import TextToVideoModelCredential
from .model.embedding import AliyunBaiLianEmbedding
from .model.image import QwenVLChatModel
from .model.llm import BaiLianChatModel
from .model.reranker import AliyunBaiLianReranker
from .model.stt import AliyunBaiLianAsrSpeechToText, AliyunBaiLianDefaultSpeechToText, AliyunBaiLianOmiSpeechToText
from .model.stt import AliyunBaiLianSpeechToText
from .model.tti import QwenTextToImageModel
from .model.tts import AliyunBaiLianTextToSpeech
from .model.ttv import GenerationVideoModel
from .parameters import DIMENSIONS


DOCS = "https://help.aliyun.com/zh/model-studio/"
model_info_manage = ModelInfoManage()


def register(names, kind, credential, model_class, description, page):
    for name in names:
        info = ModelInfo(name, description, kind, credential, model_class, docs_url=DOCS + page)
        model_info_manage.append_model_info(info)
        if kind.name not in model_info_manage.default_model_dict:
            model_info_manage.append_default_model_info(info)


modern_chat = ("qwen3.8-max", "qwen3.7-plus", "qwen3.8-flash", "qwen3.7-max", "qwen3.7-flash",
               "qwen3.6-plus", "qwen3.6-flash", "qwen3.5-plus", "qwen3.5-flash")
register((*modern_chat, "qwen3.6-max-preview", "qwen-plus", "qwen-flash", "qwen-max", "qwen-turbo"),
         ModelTypeConst.LLM, BaiLianLLMModelCredential(), BaiLianChatModel,
         "对话生成、流式输出和工具调用。思考模式按具体型号提供。", "qwen-api-via-openai-chat-completions")
register((*modern_chat, "qwen3-vl-plus", "qwen3-vl-flash", "qwen-vl-max", "qwen-vl-plus",
          "qwen-vl-max-0809", "qwen-vl-plus-0809"), ModelTypeConst.IMAGE, QwenVLModelCredential(), QwenVLChatModel,
         "输入图像和文字，返回文本描述或问题答案。", "vision-model/")
register(("text-embedding-v4", *[n for n in DIMENSIONS if n != "text-embedding-v4"]), ModelTypeConst.EMBEDDING,
         AliyunBaiLianEmbeddingCredential(), AliyunBaiLianEmbedding,
         "用于知识库索引和检索的文本向量，支持的输出维度与每批上限按型号设置。", "embedding")
register(("qwen3.7-text-rerank", "qwen3-rerank", "gte-rerank-v2", "qwen3-vl-rerank"), ModelTypeConst.RERANKER,
         AliyunBaiLianRerankerCredential(), AliyunBaiLianReranker,
         "对查询与候选段落重新排序，保留来源元数据；在 LiteKB 中输入为文本。", "text-rerank-api")

register(("qwen-image-3.0-pro", "qwen-image-3.0"), ModelTypeConst.TTI, MediaCredential("TTI"), QwenTextToImageModel,
         "千问图像 3.0 文生图，返回生成图片地址。", "qwen-image-generation-and-editing-api-reference")
register(("qwen-image-2.0-pro", "qwen-image-2.0"), ModelTypeConst.TTI, MediaCredential("TTI"), QwenTextToImageModel,
         "千问图像 2.0 文生图，支持多图、分辨率和随机种子。", "qwen-image-api")
register(("wanx-v1",), ModelTypeConst.TTI, QwenTextToImageModelCredential(), QwenTextToImageModel,
         "万相经典文生图，使用异步图像合成接口。", "text-to-image")
for kind in (ModelTypeConst.TTV, ModelTypeConst.ITV):
    register(("wan3.0-video", "wan3.0-video-prime"), kind, MediaCredential(kind.name), GenerationVideoModel,
             "万相 3.0 异步视频生成，按节点输入使用文本或首尾帧。", "wan3-video-generation-api-reference")
register(("wan2.7-t2v",), ModelTypeConst.TTV, MediaCredential("TTV"), GenerationVideoModel,
         "以文本生成视频，可选分辨率、宽高比和时长。", "text-to-video-api-reference")
register(("wan2.7-i2v",), ModelTypeConst.ITV, MediaCredential("ITV"), GenerationVideoModel,
         "以首帧或首尾帧生成视频，返回 MP4 地址。", "image-to-video-general-api-reference")
register(("wan2.2-t2v-plus", "wanx2.1-t2v-turbo", "wanx2.1-t2v-plus"), ModelTypeConst.TTV,
         TextToVideoModelCredential(), GenerationVideoModel, "万相文生视频，使用像素尺寸参数。", "text-to-video-guide")
register(("wan2.2-i2v-flash", "wan2.2-i2v-plus", "wanx2.1-i2v-plus", "wanx2.1-i2v-turbo"), ModelTypeConst.ITV,
         ImageToVideoModelCredential(), GenerationVideoModel, "万相图生视频，首帧使用 img_url。", "wan-image-to-video-guide")

register(("qwen-audio-3.1-asr-flash", "qwen-audio-3.0-asr-flash"), ModelTypeConst.STT,
         MediaCredential("STT"), AliyunBaiLianAsrSpeechToText, "音频文件转写，返回完整文本。", "qwen-audio-asr-http-api")
register(("qwen3-asr-flash",), ModelTypeConst.STT, MediaCredential("STT"), AliyunBaiLianAsrSpeechToText,
         "短音频同步转写。", "qwen-asr-api-reference")
register(("qwen-audio-asr",), ModelTypeConst.STT, AliyunBaiLianAsrSTTModelCredential(), AliyunBaiLianAsrSpeechToText,
         "千问音频模型录音转写。", "audio-language-model")
register(("qwen-omni-turbo", "qwen2.5-omni-7b"), ModelTypeConst.STT, AliyunBaiLianOmiSTTModelCredential(),
         AliyunBaiLianOmiSpeechToText, "使用 Omni 音频输入、流式文本输出执行转写。", "qwen-omni")
register(("paraformer-realtime-v2",), ModelTypeConst.STT, AliyunBaiLianSTTModelCredential(), AliyunBaiLianSpeechToText,
         "通过可选 DashScope SDK 识别音频。", "asr-model")
register(("qwen-audio-3.0-tts-flash", "qwen-audio-3.0-tts-plus", "qwen-audio-3.1-tts-flash", "qwen-audio-3.1-tts-plus"),
         ModelTypeConst.TTS, MediaCredential("TTS"), AliyunBaiLianTextToSpeech,
         "非实时语音合成，使用音色 ID 与采样率生成音频。", "qwen-audio-tts-http-api")
register(("qwen3-tts-flash", "qwen3-tts-instruct-flash"), ModelTypeConst.TTS, MediaCredential("TTS"),
         AliyunBaiLianTextToSpeech, "使用千问系统音色合成语音。", "tts-model/")
register(("cosyvoice-v1",), ModelTypeConst.TTS, AliyunBaiLianTTSModelCredential(), AliyunBaiLianTextToSpeech,
         "CosyVoice 实时语音合成协议。", "cosyvoice-websocket-api/")

# Keep custom STT model credential routing and legacy, family-specific image/video forms.
for kind, credential, cls in (
    (ModelTypeConst.STT, AliyunBaiLianDefaultSTTModelCredential(), AliyunBaiLianDefaultSpeechToText),
    (ModelTypeConst.TTI, QwenTextToImageModelCredential(), QwenTextToImageModel),
    (ModelTypeConst.TTV, TextToVideoModelCredential(), GenerationVideoModel),
    (ModelTypeConst.ITV, ImageToVideoModelCredential(), GenerationVideoModel),
    (ModelTypeConst.TTS, AliyunBaiLianTTSModelCredential(), AliyunBaiLianTextToSpeech),
):
    model_info_manage.append_default_model_info(ModelInfo("default", "", kind, credential, cls))


class AliyunBaiLianModelProvider(IModelProvider):
    def get_model_info_manage(self):
        return model_info_manage

    def get_model_provide_info(self):
        return ModelProvideInfo(provider="aliyun_bai_lian_model_provider", name=_("Alibaba Cloud Bailian"),
                                icon=(Path(__file__).parent / "icon" / "aliyun_bai_lian_icon_svg").read_text("utf-8"))
