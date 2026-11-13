from django.utils.translation import gettext_lazy as _
from langchain_core.messages import HumanMessage

from common import forms
from common.exception.app_exception import AppApiException
from models_provider.base_model_provider import (
    BaseModelCredential, IModelProvider, ModelInfo, ModelInfoManage, ModelProvideInfo, ModelTypeConst,
)
from models_provider.impl.xiaomi_mimo_model_provider.models import BASE_URL, MiMoChat, MiMoSpeech, MiMoTranscription


def choices(label, values, default):
    return forms.SingleSelect(label, "value", "value", [{"value": value} for value in values], default_value=default)


class ChatParams(forms.BaseForm):
    thinking_mode = choices("Thinking", ("enabled", "disabled"), "enabled")
    max_completion_tokens = forms.SliderField(_("Output the maximum Tokens"), 1, 131072, 1, 0, default_value=8192)
    temperature = forms.SliderField(_("Temperature"), 0, 1.5, 0.01, 2, default_value=1,
                                    relation_show_field_dict={"thinking_mode": ["disabled"]})
    top_p = forms.SliderField("Top P", 0.01, 1, 0.01, 2, default_value=0.95,
                              relation_show_field_dict={"thinking_mode": ["disabled"]})


class TranscriptionParams(forms.BaseForm):
    language = choices(_("Language"), ("auto", "zh", "en"), "auto")


class SpeechParams(forms.BaseForm):
    voice = choices("Voice", ("mimo_default", "冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean"),
                    "mimo_default")


class VoiceDesignParams(forms.BaseForm):
    voice_description = forms.TextInputField("Voice description", required=True, default_value="自然、清晰的中文旁白")


class MiMoCredential(forms.BaseForm, BaseModelCredential):
    api_base = forms.TextInputField(_("API URL"), required=True, default_value=BASE_URL)
    api_key = forms.PasswordInputField("API Key", required=True)

    def __init__(self, params):
        self.params = params

    def get_model_params_setting_form(self, model_name):
        return self.params()

    def encryption_dict(self, values):
        return {**values, "api_key": self.encryption(values.get("api_key", ""))}

    def is_valid(self, model_type, model_name, model_credential, model_params, provider, raise_exception=False):
        try:
            model = provider.get_model(model_type, model_name, model_credential, **model_params)
            if model_type in {"STT", "TTS"}:
                model.check_auth()
            else:
                model.invoke([HumanMessage(content="Hi")], max_completion_tokens=16)
            return True
        except Exception as exc:
            if raise_exception:
                raise AppApiException(500, str(exc)) from exc
            return False


catalog = ModelInfoManage()
chat = MiMoCredential(ChatParams)
for kind in (ModelTypeConst.LLM, ModelTypeConst.IMAGE):
    for name, desc in (("mimo-v2.6-flash", "MiMo V2.6 Flash · 1M context · multimodal"),
                       ("mimo-v2.6-pro", "MiMo V2.6 Pro · 1M context · multimodal"),
                       ("mimo-v2.6-pro-ultraspeed", "MiMo V2.6 Pro UltraSpeed · requires account access")):
        entry = ModelInfo(name, desc, kind, chat, MiMoChat, docs_url="https://mimo.mi.com/docs/quick-start/model")
        catalog.append_model_info(entry)
        if name == "mimo-v2.6-flash":
            catalog.append_default_model_info(entry)

for name, desc, kind, params, model, page in (
    ("mimo-v2.5-asr", "Chinese and English · WAV / MP3", ModelTypeConst.STT, TranscriptionParams,
     MiMoTranscription, "Speech-Recognition"),
    ("mimo-v2.5-tts", "Speech synthesis · built-in voices", ModelTypeConst.TTS, SpeechParams, MiMoSpeech, "tts-post"),
    ("mimo-v2.5-tts-voicedesign", "Speech synthesis · voice description", ModelTypeConst.TTS, VoiceDesignParams,
     MiMoSpeech, "tts-post"),
):
    entry = ModelInfo(name, desc, kind, MiMoCredential(params), model,
                      docs_url=f"https://mimo.mi.com/docs/en-US/api/audio/{page}")
    catalog.append_model_info(entry)


class MiMoProvider(IModelProvider):
    def get_model_info_manage(self):
        return catalog

    def get_model_provide_info(self):
        mark = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
                '<rect width="48" height="48" rx="13" fill="#ff6900"/>'
                '<path d="M10 33V15h10l5 9 5-9h8v18h-6V22l-7 12-8-13v12z" fill="#fff"/></svg>')
        return ModelProvideInfo(provider="model_xiaomi_mimo_provider", name="Xiaomi MiMo", icon=mark)
