#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project ：MaxKB 
@File    ：llm.py
@Author  ：Brian Yang
@Date    ：5/12/24 7:44 AM 
"""
import json
from typing import Dict, Any

from langchain_core.language_models import LanguageModelInput

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.reasoning_chat import ReasoningChat


def _move_tool_images_to_user_messages(messages):
    """Keep tool outputs textual while delivering images as vision input."""
    result = []
    pending_images = []
    for message in messages:
        # All responses to parallel tool calls must precede the extra user message.
        if message["role"] != "tool" and pending_images:
            result.append({"role": "user", "content": pending_images})
            pending_images = []
        content = message.get("content")
        if message["role"] == "tool" and isinstance(content, list):
            images = [block for block in content if isinstance(block, dict) and block.get("type") == "image_url"]
            if images:
                reference = f"Images returned by tool call {message['tool_call_id']} (in original order):"
                pending_images.extend([{"type": "text", "text": reference}, *images])
                text_content = [block for block in content if not (
                    isinstance(block, dict) and block.get("type") == "image_url"
                )]
                message = {**message, "content": [*text_content, {
                    "type": "text",
                    "text": f"{len(images)} tool image(s) are attached in the following user message.",
                }]}
        result.append(message)
    if pending_images:
        result.append({"role": "user", "content": pending_images})
    return result


class DeepSeekChatModel(MaxKBBaseModel, ReasoningChat):

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = MaxKBBaseModel.filter_optional_params(model_kwargs)
        extra = dict(optional_params.pop("extra_body", {}) or {})
        mode = optional_params.pop("thinking_mode", None)
        if mode in ("enabled", "disabled"):
            extra["thinking"] = {"type": mode}
        thinking = extra.get("thinking", {}).get("type", "enabled") == "enabled"
        if thinking:
            for key in ("temperature", "presence_penalty", "frequency_penalty"):
                optional_params.pop(key, None)
        else:
            optional_params.pop("reasoning_effort", None)
        if (model_name == "deepseek-v4-pro" and thinking) or (model_name != "deepseek-v4-pro" and not thinking):
            optional_params.pop("top_p", None)
        return DeepSeekChatModel(
            model=model_name,
            openai_api_base=model_credential.get('api_base') or 'https://api.deepseek.com',
            openai_api_key=model_credential.get('api_key'),
            extra_body=extra or None,
            use_responses_api=False,
            **optional_params,
        )

    def _get_request_payload(
            self,
            input_: LanguageModelInput,
            *,
            stop: list[str] | None = None,
            **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")

        # Move images before JSON encoding tool content, otherwise vision-capable
        # gateways receive base64 as ordinary text. Only the request is changed;
        # the agent state and execution records retain the original ToolMessage.
        payload["messages"] = _move_tool_images_to_user_messages(payload["messages"])

        # Apply DeepSeek-specific message formatting
        for message in payload["messages"]:
            if message["role"] == "tool" and isinstance(message["content"], list):
                message["content"] = json.dumps(message["content"])
            elif message["role"] == "assistant" and isinstance(
                    message["content"], list
            ):
                # DeepSeek API expects assistant content to be a string, not a list.
                # Extract text blocks and join them, or use empty string if none exist.
                text_parts = [
                    block.get("text", "")
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                message["content"] = "".join(text_parts) if text_parts else ""
        return payload
