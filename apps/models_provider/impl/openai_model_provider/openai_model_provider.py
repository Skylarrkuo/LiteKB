"""OpenAI API models available to the workflow runtime."""
import os

from django.utils.translation import gettext_lazy as _

from common.utils.common import get_file_content
from maxkb.conf import PROJECT_DIR
from models_provider.base_model_provider import IModelProvider, ModelInfo, ModelInfoManage, ModelProvideInfo, ModelTypeConst
from .credential.embedding import OpenAIEmbeddingCredential
from .credential.image import OpenAIImageModelCredential
from .credential.llm import OfficialOpenAILLMCredential
from .credential.stt import OpenAISTTModelCredential
from .credential.tti import OpenAITextToImageModelCredential
from .credential.tts import OpenAITTSModelCredential
from .model.embedding import OpenAIEmbeddingModel
from .model.image import OpenAIImage
from .model.llm import OpenAIChatModel
from .model.stt import OpenAISpeechToText
from .model.tti import OpenAITextToImage
from .model.tts import OpenAITextToSpeech
from .profiles import IMAGE_MODELS


_ADAPTERS = {
    ModelTypeConst.LLM: (OfficialOpenAILLMCredential(), OpenAIChatModel),
    ModelTypeConst.IMAGE: (OpenAIImageModelCredential(), OpenAIImage),
    ModelTypeConst.EMBEDDING: (OpenAIEmbeddingCredential(), OpenAIEmbeddingModel),
    ModelTypeConst.STT: (OpenAISTTModelCredential(), OpenAISpeechToText),
    ModelTypeConst.TTS: (OpenAITTSModelCredential(), OpenAITextToSpeech),
    ModelTypeConst.TTI: (OpenAITextToImageModelCredential(), OpenAITextToImage),
}
_MODEL_DOCS = "https://developers.openai.com/api/docs/models/"
_DEPRECATIONS = "https://developers.openai.com/api/docs/deprecations"
_CATALOG = ModelInfoManage.builder()


def register(kind, name, description, *, default=False, status="available", docs_url=None):
    entry = ModelInfo(name, description, kind, *_ADAPTERS[kind], docs_url=docs_url or _MODEL_DOCS + name, status=status)
    _CATALOG.append_model_info(entry)
    if default:
        _CATALOG.append_default_model_info(entry)


for name, description in (
    ("gpt-6.1-sol", _("General-purpose reasoning and tool use")),
    ("gpt-6.1-terra", _("Visual reasoning and document understanding")),
    ("gpt-6-luna", _("Efficient model for high-volume tasks")),
    ("gpt-6-astra", _("Complex reasoning and long-running tool workflows")),
    ("gpt-6-sol", _("Reasoning and tool use")),
    ("gpt-5.6-terra", _("Text and image reasoning")),
    ("gpt-5.6-sol", _("General-purpose text and image reasoning")),
    ("gpt-5.6-luna", _("Efficient text and image reasoning")),
    ("gpt-5.5", _("Complex text and image workflows")),
    ("gpt-5.4", _("Reasoning and tool use")),
    ("gpt-5.4-mini", _("Efficient text and image reasoning")),
    ("gpt-5.4-nano", _("Classification, ranking and data extraction")),
):
    status = "deprecated" if name == "gpt-5.4-nano" else "available"
    register(ModelTypeConst.LLM, name, description, default=name == "gpt-6.1-sol", status=status)
    register(ModelTypeConst.IMAGE, name, description, default=name == "gpt-6.1-terra", status=status)

for name in ("gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"):
    for kind in (ModelTypeConst.LLM, ModelTypeConst.IMAGE):
        register(kind, name, _("GPT-4 series chat and vision model"),
                 status="retired" if name == "gpt-4.1-nano" else "deprecated")
for name in ("gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo-0125", "gpt-3.5-turbo-0613",
             "gpt-4o-2024-05-13", "gpt-4-turbo-2024-04-09", "gpt-4-1106-preview"):
    register(ModelTypeConst.LLM, name, _("Retired Chat Completions model"), status="retired", docs_url=_DEPRECATIONS)
for name in ("gpt-4-turbo-preview", "gpt-3.5-turbo-1106", "gpt-4-0125-preview"):
    register(ModelTypeConst.LLM, name, _("Historic snapshot retained for saved configurations"),
             status="legacy", docs_url=_DEPRECATIONS)

register(ModelTypeConst.EMBEDDING, "text-embedding-3-small", _("1536 dimensions, supports shortening"), default=True)
register(ModelTypeConst.EMBEDDING, "text-embedding-3-large", _("3072 dimensions, supports shortening"))
register(ModelTypeConst.EMBEDDING, "text-embedding-ada-002", _("Fixed 1536-dimensional embeddings"))

register(ModelTypeConst.STT, "gpt-transcribe", _("File transcription with language and keyword hints"), default=True)
for name in ("gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-transcribe-diarize", "whisper-1"):
    register(ModelTypeConst.STT, name, _("File transcription; scheduled for retirement in February 2027"),
             status="deprecated")

for name in ("gpt-4o-mini-tts", "tts-1", "tts-1-hd"):
    register(ModelTypeConst.TTS, name, _("Speech API synthesis; scheduled for retirement in January 2027"),
             default=name == "gpt-4o-mini-tts", status="deprecated")

for name in IMAGE_MODELS:
    register(ModelTypeConst.TTI, name, _("Text-to-image generation via the Images API"),
             default=name == "gpt-image-2.6-flare", status="deprecated" if name in ("gpt-image-2", "gpt-image-1.5") else "available")
register(ModelTypeConst.TTI, "dall-e-3", _("Retired on the official API; retained for existing configurations"),
         status="retired", docs_url=_DEPRECATIONS)

model_info_manage = _CATALOG.build()


class OpenAIModelProvider(IModelProvider):
    def get_model_info_manage(self):
        return model_info_manage

    def get_model_list(self, model_type):
        return [entry for entry in super().get_model_list(model_type) if entry["status"] not in ("retired", "legacy")]

    def get_model_provide_info(self):
        return ModelProvideInfo(provider="model_openai_provider", name="OpenAI", icon=get_file_content(
            os.path.join(PROJECT_DIR, "apps", "models_provider", "impl", "openai_model_provider", "icon", "openai_icon_svg")))
