from models_provider.base_model_provider import MaxKBBaseModel
from .asr_stt import AliyunBaiLianAsrSpeechToText
from .omni_stt import AliyunBaiLianOmiSpeechToText
from .stt import AliyunBaiLianSpeechToText


class AliyunBaiLianDefaultSpeechToText(MaxKBBaseModel):
    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential, **model_kwargs):
        adapter = {"qwen": AliyunBaiLianAsrSpeechToText, "omni": AliyunBaiLianOmiSpeechToText}.get(
            model_credential.get("type"), AliyunBaiLianSpeechToText)
        return adapter.new_instance(model_type, model_name, model_credential, **model_kwargs)
