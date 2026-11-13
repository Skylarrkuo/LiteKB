import base64

from openai import OpenAI
from pydantic import BaseModel, Field, SecretStr

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_stt import BaseSpeechToText
from models_provider.impl.base_tts import BaseTextToSpeech
from models_provider.impl.reasoning_chat import ReasoningChat


BASE_URL = "https://api.xiaomimimo.com/v1"


class MiMoChat(MaxKBBaseModel, ReasoningChat):
    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **kwargs):
        params = cls.filter_optional_params(kwargs)
        extra = dict(params.pop("extra_body", {}) or {})
        mode = params.pop("thinking_mode", None)
        if mode in ("enabled", "disabled"):
            extra["thinking"] = {"type": mode}
        if extra.get("thinking", {}).get("type", "enabled") == "enabled":
            params.pop("temperature", None)
            params.pop("top_p", None)
        return cls(model=model_name, api_key=model_credential["api_key"], base_url=model_credential["api_base"],
                   use_responses_api=False, extra_body=extra or None, **params)


class MiMoAudio(MaxKBBaseModel, BaseModel):
    model: str
    api_base: str
    api_key: SecretStr
    params: dict = Field(default_factory=dict)

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **kwargs):
        return cls(model=model_name, api_base=model_credential["api_base"], api_key=model_credential["api_key"],
                   params=cls.filter_optional_params(kwargs))

    @staticmethod
    def is_cache_model():
        return False

    def client(self):
        return OpenAI(api_key=self.api_key.get_secret_value(), base_url=self.api_base)

    def check_auth(self):
        with self.client() as client:
            if self.model not in {model.id for model in client.models.list().data}:
                raise ValueError(f"Model {self.model} is unavailable for this API key.")


class MiMoTranscription(MiMoAudio, BaseSpeechToText):
    def speech_to_text(self, audio_file):
        # MiMo caps the base64 payload at 10 MiB.
        raw_limit = 10 * 1024 * 1024 * 3 // 4
        audio = audio_file.read(raw_limit + 1)
        if len(audio) > raw_limit:
            raise ValueError("MiMo ASR accepts up to 10 MiB of base64-encoded audio.")
        if audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
            mime = "audio/wav"
        elif audio.startswith(b"ID3") or (len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224):
            mime = "audio/mpeg"
        else:
            raise ValueError("MiMo ASR requires WAV or MP3 audio.")
        data = f"data:{mime};base64," + base64.b64encode(audio).decode("ascii")
        with self.client() as client:
            response = client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": [
                    {"type": "input_audio", "input_audio": {"data": data}}]}],
                extra_body={"asr_options": {"language": self.params.get("language", "auto")}})
        return response.choices[0].message.content


class MiMoSpeech(MiMoAudio, BaseTextToSpeech):
    def text_to_speech(self, text):
        messages = []
        audio = {"format": "mp3"}
        if self.model.endswith("-voicedesign"):
            messages.append({"role": "user", "content": self.params["voice_description"]})
        else:
            audio["voice"] = self.params.get("voice", "mimo_default")
        messages.append({"role": "assistant", "content": text})
        with self.client() as client:
            response = client.chat.completions.create(model=self.model, messages=messages, audio=audio)
        return base64.b64decode(response.choices[0].message.audio.data, validate=True)
