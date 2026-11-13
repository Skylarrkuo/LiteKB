from typing import Dict

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.openai_model_provider.model.llm import OpenAIChatModel
from models_provider.impl.openai_model_provider.profiles import chat_options


class OpenAIImage(OpenAIChatModel):

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = chat_options(model_name, MaxKBBaseModel.filter_optional_params(model_kwargs))
        return OpenAIImage(
            model_name=model_name,
            openai_api_base=model_credential.get('api_base'),
            openai_api_key=model_credential.get('api_key'),
            streaming=model_kwargs.get('streaming', True),
            stream_usage=not optional_params.get("use_responses_api", False),
            **optional_params,
        )
