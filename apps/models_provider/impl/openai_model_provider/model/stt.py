from pathlib import Path

from openai import OpenAI

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_stt import BaseSpeechToText
from ..profiles import family


class OpenAISpeechToText(MaxKBBaseModel, BaseSpeechToText):
    api_base: str
    api_key: str
    model: str
    params: dict

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential, **model_kwargs):
        options = MaxKBBaseModel.filter_optional_params(model_kwargs)
        return OpenAISpeechToText(api_base=model_credential["api_base"], api_key=model_credential["api_key"],
                                  model=model_name, params=options)

    def check_auth(self):
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            client.models.retrieve(self.model)

    def speech_to_text(self, audio_file):
        name = Path(getattr(audio_file, "name", None) or "audio.mp3").name
        options = {k: v for k, v in self.params.items() if k in ("language", "prompt", "temperature") and v is not None and v != ""}
        extra = {}
        if family(self.model) == "gpt-transcribe":
            if "languages" not in self.params and options.get("language"):
                extra["languages"] = [options["language"]]
            options.pop("language", None)
            for key in ("languages", "keywords"):
                value = self.params.get(key)
                if value:
                    extra[key] = [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value
            if any(any(char in term for char in "<>\r\n") for term in extra.get("keywords", [])):
                raise ValueError("Transcription keywords must be single-line terms without < or >")
        elif family(self.model) == "gpt-4o-transcribe-diarize":
            options.pop("prompt", None)
            options["chunking_strategy"] = "auto"
            options["response_format"] = "diarized_json"
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            result = client.audio.transcriptions.create(model=self.model, file=(name, audio_file.read()),
                                                        extra_body=extra or None, **options)
        return result.text

