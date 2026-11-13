import json
from contextlib import closing
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from common.utils.common import _remove_empty_lines
from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_tts import BaseTextToSpeech
from oss.url_fetch import fetch_public_bytes
from ..transport import check_catalog, endpoint, request


class AliyunBaiLianTextToSpeech(MaxKBBaseModel, BaseTextToSpeech):
    api_key: str
    base_url: str
    model: str
    params: dict

    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **model_kwargs):
        return cls(model=model_name, api_key=model_credential["api_key"], base_url=endpoint(model_credential.get("api_base")),
                   params={k: v for k, v in cls.filter_optional_params(model_kwargs).items() if v is not None and v != ""})

    def check_auth(self):
        check_catalog(self.base_url, self.api_key, self.model)
        return True

    def text_to_speech(self, text):
        text = _remove_empty_lines(text)
        params = dict(self.params)
        if self.model.startswith(("qwen-audio-", "cosyvoice-v3")):
            output = request(self.base_url, self.api_key, "services/audio/tts/SpeechSynthesizer",
                             {"model": self.model, "input": {"text": text, **params}})
        elif self.model.startswith("qwen"):
            params.pop("speech_rate", None)  # Old forms exposed this unsupported parameter for Qwen3-TTS.
            output = request(self.base_url, self.api_key, "services/aigc/multimodal-generation/generation",
                             {"model": self.model, "input": {"text": text, **params}})
        elif "MiniMax" in self.model:
            output = request(self.base_url, self.api_key, "services/aigc/multimodal-generation/generation",
                             {"model": self.model, "input": {"text": text, **params}})
            return bytes.fromhex(output["data"]["audio"])
        elif "sambert" in self.model:
            from dashscope.audio.tts import SpeechSynthesizer
            return SpeechSynthesizer.call(model=self.model, text=text, api_key=self.api_key, **params).get_audio_data()
        else:
            return self._cosyvoice_audio(text)
        return fetch_public_bytes(output["audio"]["url"])

    def _cosyvoice_audio(self, text):
        from websocket import create_connection

        parts = urlsplit(self.base_url)
        url = urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc,
                          parts.path.removesuffix("/api/v1") + "/api-ws/v1/inference", "", ""))
        task = uuid4().hex
        with closing(create_connection(url, header={"Authorization": "Bearer " + self.api_key}, timeout=60,
                                       redirect_limit=0)) as socket:
            def send(action, payload):
                socket.send(json.dumps({"header": {"action": action, "task_id": task, "streaming": "duplex"},
                                        "payload": payload}, ensure_ascii=False))
            send("run-task", {"task_group": "audio", "task": "tts", "function": "SpeechSynthesizer",
                              "model": self.model, "parameters": {"format": "mp3", "voice": "longxiaochun",
                                                                  **self.params}, "input": {}})
            audio = bytearray()
            while True:
                frame = socket.recv()
                if isinstance(frame, bytes):
                    audio.extend(frame)
                    continue
                event = json.loads(frame)["header"]["event"]
                if event == "task-started":
                    send("continue-task", {"input": {"text": text}})
                    send("finish-task", {"input": {}})
                elif event == "task-finished":
                    return bytes(audio)
                elif event == "task-failed":
                    raise ValueError("DashScope speech synthesis task failed")
