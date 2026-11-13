import base64
from pathlib import Path

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_stt import BaseSpeechToText
from ...transport import check_catalog, endpoint, request


class AliyunBaiLianAsrSpeechToText(MaxKBBaseModel, BaseSpeechToText):
    api_key: str
    api_url: str
    model: str
    params: dict

    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **model_kwargs):
        return cls(model=model_name, api_key=model_credential["api_key"],
                   api_url=endpoint(model_credential.get("api_base") or model_credential.get("api_url")),
                   params={k: v for k, v in cls.filter_optional_params(model_kwargs).items() if v is not None and v != ""})

    def check_auth(self):
        check_catalog(self.api_url, self.api_key, self.model)
        return True

    def speech_to_text(self, audio_file):
        name = getattr(audio_file, "name", "") or ""
        blob = audio_file.read()
        fmt = Path(name).suffix.lower().lstrip(".") or ("wav" if blob.startswith(b"RIFF") else "mp3")
        data = f"data:audio/{fmt};base64," + base64.b64encode(blob).decode("ascii")
        modern = self.model.startswith("qwen-audio-3.")
        content = {"type": "input_audio", "input_audio": {"data": data}} if modern else {"audio": data}
        params = dict(self.params)
        if modern:
            params["format"] = fmt
            if "sample_rate" in params:
                params["sample_rate"] = str(params["sample_rate"])
        elif self.model.startswith("qwen3-asr"):
            params = {"asr_options": params}
        payload = {"model": self.model, "input": {"messages": [{"role": "user", "content": [content]}]},
                   "parameters": params}
        output = request(self.api_url, self.api_key, "services/aigc/multimodal-generation/generation", payload)
        if modern:
            return output["text"]
        return "".join(item.get("text", "") for item in output["choices"][0]["message"]["content"])
