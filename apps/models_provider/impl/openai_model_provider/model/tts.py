from openai import OpenAI

from common.utils.common import _remove_empty_lines
from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_tts import BaseTextToSpeech
from ..profiles import family


class OpenAITextToSpeech(MaxKBBaseModel, BaseTextToSpeech):
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
        modern = family(model_name) == "gpt-4o-mini-tts"
        options.setdefault("voice", "marin" if modern else "alloy")
        if not modern or not options.get("instructions"):
            options.pop("instructions", None)
        return OpenAITextToSpeech(api_base=model_credential["api_base"], api_key=model_credential["api_key"],
                                  model=model_name, params=options)

    def check_auth(self):
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            client.models.retrieve(self.model)

    def text_to_speech(self, text):
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            with client.audio.speech.with_streaming_response.create(
                model=self.model, input=_remove_empty_lines(text), **self.params
            ) as response:
                return response.read()
