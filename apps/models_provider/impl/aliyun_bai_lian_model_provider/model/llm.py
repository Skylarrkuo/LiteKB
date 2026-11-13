#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Dict, Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_chat_open_ai import BaseChatOpenAI
from ..transport import endpoint


class BaiLianChatModel(MaxKBBaseModel, BaseChatOpenAI):
    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = {k: v for k, v in MaxKBBaseModel.filter_optional_params(model_kwargs).items()
                           if v is not None and v != ""}
        extra = dict(optional_params.pop("extra_body", {}) or {})
        for key in ("top_k", "enable_thinking", "thinking_budget", "enable_search", "vl_high_resolution_images"):
            if key in optional_params:
                extra[key] = optional_params.pop(key)
        if extra.get("enable_thinking") is False:
            extra.pop("thinking_budget", None)
        return cls(
            model=model_name,
            openai_api_base=endpoint(model_credential.get('api_base'), compatible=True),
            openai_api_key=model_credential.get('api_key'),
            streaming=True,
            stream_usage=True,
            extra_body=extra or None,
            **optional_params,
        )

    def _get_request_payload(
            self,
            input_: LanguageModelInput,
            *,
            stop: list[str] | None = None,
            **kwargs: Any,
    ) -> dict:
        # Collect reasoning_content from AIMessages with tool_calls before base conversion.
        # When enable_thinking=true, Bailian API requires reasoning_content on any assistant
        # message that contains tool_calls (defaults to "" when not present).
        messages = self._convert_input(input_).to_messages()
        reasoning_content_map = {}
        for i, msg in enumerate(messages):
            if (
                    isinstance(msg, AIMessage)
                    and (msg.tool_calls or msg.invalid_tool_calls)
            ):
                reasoning_content_map[i] = msg.additional_kwargs.get(
                    "reasoning_content") or ""

        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "max_completion_tokens" in payload:
            # The saved max_tokens field is an answer budget, also understood by older models.
            payload["max_tokens"] = payload.pop("max_completion_tokens")

        # Inject reasoning_content into assistant messages with tool_calls so that
        # Bailian deepseek thinking mode does not reject the request with a 400 error.
        if "messages" in payload and reasoning_content_map:
            for i, message in enumerate(payload["messages"]):
                if (
                        i in reasoning_content_map
                        and message.get("role") == "assistant"
                        and message.get("tool_calls")
                ):
                    message["reasoning_content"] = reasoning_content_map[i]

        return payload
