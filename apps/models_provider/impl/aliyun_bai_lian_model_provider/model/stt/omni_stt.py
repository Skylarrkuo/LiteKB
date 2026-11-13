import base64
from pathlib import Path

from openai import OpenAI

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_stt import BaseSpeechToText
from ...transport import check_catalog, endpoint


class AliyunBaiLianOmiSpeechToText(MaxKBBaseModel, BaseSpeechToText):
    api_key: str
    api_url: str
    model: str
    params: dict

    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **model_kwargs):
        base = model_credential.get("api_url") or model_credential.get("api_base")
        return cls(model=model_name, api_key=model_credential["api_key"], api_url=endpoint(base, compatible=True),
                   params=cls.filter_optional_params(model_kwargs))

    def check_auth(self):
        check_catalog(self.api_url, self.api_key, self.model)
        return True

    def speech_to_text(self, audio_file):
        raw = audio_file.read()
        fmt = Path(getattr(audio_file, "name", "") or "").suffix.lstrip(".").lower()
        fmt = fmt or ("wav" if raw.startswith(b"RIFF") else "mp3")
        data = f"data:audio/{fmt};base64," + base64.b64encode(raw).decode("ascii")
        content = [{"type": "input_audio", "input_audio": {"data": data, "format": fmt}},
                   {"type": "text", "text": self.params.get("CueWord") or "这段音频在说什么，只回答音频的内容"}]
        params = {k: v for k, v in self.params.items() if k != "CueWord" and v is not None}
        with OpenAI(api_key=self.api_key, base_url=self.api_url) as client:
            chunks = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": content}],
                                                    modalities=["text"], stream=True, stream_options={"include_usage": True},
                                                    extra_body=params)
            return "".join(chunk.choices[0].delta.content or "" for chunk in chunks if chunk.choices)
