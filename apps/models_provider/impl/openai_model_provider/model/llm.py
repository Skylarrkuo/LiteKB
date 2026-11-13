# coding=utf-8
"""
    @project: maxkb
    @Author：虎
    @file： llm.py
    @date：2024/4/18 15:28
    @desc:
"""
from typing import List, Dict

from langchain_core.messages import AIMessage, BaseMessage, get_buffer_string

from common.config.tokenizer_manage_config import TokenizerManage
from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_chat_open_ai import BaseChatOpenAI
from models_provider.impl.openai_model_provider.profiles import REASONING, chat_options, family


def custom_get_token_ids(text: str):
    tokenizer = TokenizerManage.get_tokenizer()
    return tokenizer.encode(text)


class OpenAIChatModel(MaxKBBaseModel, BaseChatOpenAI):

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = chat_options(model_name, MaxKBBaseModel.filter_optional_params(model_kwargs))
        streaming = model_kwargs.get('streaming', True)
        if model_name.startswith('o1'):
            streaming = False
        chat_open_ai = OpenAIChatModel(
            model=model_name,
            openai_api_base=model_credential.get('api_base'),
            openai_api_key=model_credential.get('api_key'),
            streaming=streaming,
            custom_get_token_ids=custom_get_token_ids,
            **optional_params,
        )
        return chat_open_ai

    def _as_workflow_text(self, message):
        if self.use_responses_api and isinstance(message.content, list):
            blocks = message.content
            text = message.text or "".join(b.get("refusal", "") for b in blocks if isinstance(b, dict))
            # Workflows consume strings. On the next turn the Responses API also needs
            # the original ordered reasoning, phase, function-call and message items.
            return message.model_copy(update={"content": str(text), "additional_kwargs": {
                **message.additional_kwargs, "openai_response_items": blocks,
            }})
        return message

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        if not self.use_responses_api:
            return super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        restored = [m.model_copy(update={"content": m.additional_kwargs["openai_response_items"]})
                    if isinstance(m, AIMessage) and "openai_response_items" in m.additional_kwargs else m for m in messages]
        payload = super()._get_request_payload(restored, stop=stop, **kwargs)
        profile = REASONING.get(family(self.model_name))
        if profile:
            default, supported = profile
            reasoning = payload.setdefault("reasoning", {})
            flat_effort = payload.pop("reasoning_effort", None)
            effort = kwargs.get("reasoning_effort") or (kwargs.get("reasoning") or {}).get("effort")
            effort = effort or reasoning.get("effort") or flat_effort or default
            if effort not in supported:
                raise ValueError(f"Unsupported reasoning effort for {self.model_name}: {effort}")
            reasoning["effort"] = effort
            if effort != "none":
                for key in ("temperature", "top_p", "logprobs", "top_logprobs"):
                    payload.pop(key, None)
                if "include" in payload:
                    payload["include"] = [item for item in payload["include"] if item != "message.output_text.logprobs"]
        return payload

    def invoke(self, *args, **kwargs):
        return self._as_workflow_text(super().invoke(*args, **kwargs))

    async def ainvoke(self, *args, **kwargs):
        return self._as_workflow_text(await super().ainvoke(*args, **kwargs))

    def stream(self, *args, **kwargs):
        for message in super().stream(*args, **kwargs):
            yield self._as_workflow_text(message)

    async def astream(self, *args, **kwargs):
        async for message in super().astream(*args, **kwargs):
            yield self._as_workflow_text(message)

    def get_num_tokens_from_messages(self, messages: List[BaseMessage]) -> int:
        try:
            return super().get_num_tokens_from_messages(messages)
        except Exception:
            tokenizer = TokenizerManage.get_tokenizer()
            return sum(len(tokenizer.encode(get_buffer_string([m]))) for m in messages)

    def get_num_tokens(self, text: str) -> int:
        try:
            return super().get_num_tokens(text)
        except Exception:
            tokenizer = TokenizerManage.get_tokenizer()
            return len(tokenizer.encode(text))
