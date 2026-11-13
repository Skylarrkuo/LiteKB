"""Chat Completions adapters whose tool history includes provider reasoning fields."""
from langchain_core.messages import AIMessage

from models_provider.impl.base_chat_open_ai import BaseChatOpenAI


class ReasoningChat(BaseChatOpenAI):
    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        choices = response["choices"] if isinstance(response, dict) else response.choices
        for generation, choice in zip(result.generations, choices):
            message = choice["message"] if isinstance(choice, dict) else choice.message.model_dump()
            if message.get("reasoning_content") is not None:
                generation.message.additional_kwargs["reasoning_content"] = message["reasoning_content"]
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        messages = self._convert_input(input_).to_messages()
        payload = super()._get_request_payload(messages, stop=stop, **kwargs)
        for original, wire in zip(messages, payload["messages"]):
            if isinstance(original, AIMessage) and "reasoning_content" in original.additional_kwargs:
                wire["reasoning_content"] = original.additional_kwargs["reasoning_content"]
        return payload
