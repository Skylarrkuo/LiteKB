"""Exercise published model forms and the actual OpenAI-compatible JSON transport."""
import base64
import io
import json
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI

from models_provider.constants.model_provider_constants import get_provider
from models_provider.serializers.model_serializer import ModelSerializer, get_default_model_params_setting


MIMO = "model_xiaomi_mimo_provider"
DEEPSEEK = "model_deepseek_provider"
CREDENTIAL = {"api_base": "https://example.invalid/v1", "api_key": "fixture"}


class ProviderWorkflowTests(SimpleTestCase):
    def test_add_model_applies_defaults_but_preserves_explicit_values(self):
        for provider, model, endpoint in [
            (MIMO, "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1"),
            (DEEPSEEK, "deepseek-flash", "https://api.deepseek.com"),
        ]:
            with self.subTest(provider=provider):
                fields = dict(provider=provider, model_type="LLM", model_name=model, credential={"api_key": "fixture"})
                result = ModelSerializer.Create(data=fields).validate(fields.copy())
                self.assertEqual(result["credential"]["api_base"], endpoint)
                self.assertIn("thinking_mode", {f["field"] for f in result["model_params_form"]})
                self.assertEqual(json.loads(json.dumps(result["model_params_form"])), result["model_params_form"])
                explicit = {**fields, "credential": CREDENTIAL, "model_params_form": []}
                self.assertEqual(ModelSerializer.Create(data=explicit).validate(explicit.copy()), explicit)

    def test_catalog_vision_and_media_flags(self):
        ds = get_provider(DEEPSEEK)
        self.assertEqual([m["name"] for m in ds.get_model_list("IMAGE")], ["deepseek-flash"])
        mimo = get_provider(MIMO)
        with patch("maxkb.capabilities.MEDIA_NODES", False):
            self.assertEqual({t["value"] for t in mimo.get_model_type_list()}, {"LLM", "IMAGE"})
        with patch("maxkb.capabilities.MEDIA_NODES", True):
            self.assertEqual({t["value"] for t in mimo.get_model_type_list()}, {"LLM", "IMAGE", "STT", "TTS"})

    def test_chat_wire_parameters_and_reasoning_history(self):
        response = {"id": "test", "object": "chat.completion", "created": 0, "model": "test", "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok",
                                                              "reasoning_content": "previous context"}}]}
        for provider, model, limit_name in [(MIMO, "mimo-v2.6-pro", "max_completion_tokens"),
                                           (DEEPSEEK, "deepseek-flash", "max_tokens")]:
            sent = []

            def respond(req):
                self.assertEqual(req.url.path, "/v1/chat/completions")
                sent.append(json.loads(req.content))
                return httpx.Response(200, json=response)

            with self.subTest(provider=provider), httpx.Client(transport=httpx.MockTransport(respond)) as client:
                defaults = {f["field"]: f["default_value"] for f in get_default_model_params_setting(
                    provider, "IMAGE", model)}
                adapter = get_provider(provider).get_model("IMAGE", model, CREDENTIAL, **defaults, http_client=client)
                question = HumanMessage(content=[{"type": "image_url", "image_url": {"url": "https://example.invalid/a"}}])
                answer = adapter.invoke([question])
                self.assertIsInstance(answer, AIMessage)
                adapter.bind_tools([{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]).invoke(
                    [question, answer, HumanMessage(content="next")])
                self.assertEqual(sent[1]["messages"][1]["reasoning_content"], "previous context")
                self.assertEqual(sent[0]["messages"][0]["content"][0]["type"], "image_url")
                self.assertEqual(sent[0][limit_name], 8192)
                self.assertEqual(sent[0]["thinking"]["type"], "enabled")
                self.assertNotIn("temperature", sent[0])
                self.assertNotIn("max_tokens" if provider == MIMO else "max_completion_tokens", sent[0])
                adapter = get_provider(provider).get_model("LLM", model, CREDENTIAL, thinking_mode="disabled",
                                                           temperature=0.3, http_client=client)
                adapter.invoke("next")
                self.assertEqual(sent[-1]["thinking"]["type"], "disabled")
                self.assertEqual(sent[-1]["temperature"], 0.3)
                self.assertNotIn("reasoning_effort", sent[-1])

    def test_mimo_audio_uses_chat_protocol(self):
        from models_provider.impl.xiaomi_mimo_model_provider.models import MiMoAudio
        sent = []

        def respond(req):
            self.assertEqual(req.url.path, "/v1/chat/completions")
            sent.append(json.loads(req.content))
            message = {"role": "assistant", "content": "hello",
                       "audio": {"id": "a", "expires_at": 0, "transcript": "hello", "data": "SUQz"}}
            return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0, "model": "test",
                                             "choices": [{"index": 0, "finish_reason": "stop", "message": message}]})

        def client(_self):
            return OpenAI(base_url=CREDENTIAL["api_base"], api_key="fixture",
                          http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        provider = get_provider(MIMO)
        with patch("maxkb.capabilities.MEDIA_NODES", True), patch.object(MiMoAudio, "client", client):
            speech = provider.get_model("TTS", "mimo-v2.5-tts", CREDENTIAL, voice="Mia")
            self.assertEqual(speech.text_to_speech("hello"), b"ID3")
            self.assertEqual(sent[-1]["messages"], [{"role": "assistant", "content": "hello"}])
            self.assertEqual(sent[-1]["audio"], {"format": "mp3", "voice": "Mia"})
            recognition = provider.get_model("STT", "mimo-v2.5-asr", CREDENTIAL, language="en")
            self.assertEqual(recognition.speech_to_text(io.BytesIO(b"ID3abc")), "hello")
            self.assertEqual(sent[-1]["asr_options"], {"language": "en"})
            data = sent[-1]["messages"][0]["content"][0]["input_audio"]["data"]
            self.assertEqual(base64.b64decode(data.split(",")[1]), b"ID3abc")
            with self.assertRaisesRegex(ValueError, "WAV or MP3"):
                recognition.speech_to_text(io.BytesIO(b"test"))
