import io
import json
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase
from langchain_core.messages import HumanMessage, ToolMessage
from openai import OpenAI

from .model.embedding import OpenAIEmbeddingModel
from .model.image import OpenAIImage
from .model.llm import OpenAIChatModel
from .model.stt import OpenAISpeechToText
from .model.tti import OpenAITextToImage
from .model.tts import OpenAITextToSpeech
from .openai_model_provider import OpenAIModelProvider

CREDENTIALS = {"api_base": "https://provider.invalid/v1", "api_key": "unit-test-only"}


class OpenAIAdapterTests(SimpleTestCase):
    def test_catalog_and_per_model_forms(self):
        provider = OpenAIModelProvider()
        for kind, expected in (("LLM", "gpt-6.1-sol"), ("IMAGE", "gpt-6.1-terra"), ("EMBEDDING", "text-embedding-3-small")):
            models = provider.get_model_list(kind)
            self.assertIn(expected, [item["name"] for item in models])
            self.assertTrue(all(item["docs_url"].startswith("https://developers.openai.com/") for item in models))
        for name, includes_none in (("gpt-6.1-sol", False), ("gpt-6.1-terra", True)):
            credential = provider.get_model_params("LLM", name)
            form = credential.get_model_params_setting_form(name)
            self.assertEqual(form.get_default_form_data(), {"reasoning_effort": "medium", "max_tokens": 8192})
            values = [option["value"] for option in form.to_form_list()[0]["option_list"]]
            self.assertEqual("none" in values, includes_none)
        self.assertEqual(provider.get_model_params("EMBEDDING", "text-embedding-ada-002")
                         .get_model_params_setting_form("text-embedding-ada-002").to_form_list(), [])
        models = provider.get_model_list("LLM")
        self.assertFalse(any(m["name"] in ("gpt-4", "gpt-4.1-nano", "gpt-4-turbo-preview") for m in models))
        self.assertEqual(provider.get_model_info_manage().get_model_info("LLM", "gpt-4").status, "retired")
        self.assertEqual([m["name"] for m in models if m["is_default"]], ["gpt-6.1-sol"])

    def test_responses_adapter_normalizes_text_and_preserves_tool_calls(self):
        requests = []
        output = [
            {"id": "rs_1", "type": "reasoning", "summary": [], "encrypted_content": "opaque"},
            {"id": "msg_1", "type": "message", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": "hello", "annotations": []}]},
            {"id": "fc_1", "type": "function_call", "call_id": "call_1", "name": "lookup", "arguments": '{"q":"doc"}'},
        ]

        def handle(request):
            requests.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"id": "resp_1", "object": "response", "created_at": 1,
                                  "model": "gpt-6.1-sol", "status": "completed", "output": output,
                                  "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            model = OpenAIChatModel.new_instance("LLM", "gpt-6.1-sol", CREDENTIALS, http_client=client,
                                                 temperature=0.7, streaming=False, max_tokens=4096, reasoning_effort="max")
            message = model.bind_tools([{"type": "function", "function": {"name": "lookup", "description": "find",
                                       "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}}]).invoke("hello")
            model.invoke([HumanMessage("hello"), message, ToolMessage("found", tool_call_id="call_1")])
        path, payload = requests[0]
        self.assertEqual(path, "/v1/responses")
        self.assertIs(payload["store"], False)
        self.assertEqual(payload["reasoning"], {"effort": "max"})
        self.assertEqual(payload["max_output_tokens"], 4096)
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["tools"][0]["name"], "lookup")
        self.assertEqual(message.content, "hello")
        self.assertEqual(message.tool_calls[0]["args"], {"q": "doc"})
        self.assertEqual(message.usage_metadata["total_tokens"], 5)
        next_turn = requests[1][1]["input"]
        self.assertEqual([item["id"] for item in next_turn if item.get("type") == "reasoning"], ["rs_1"])
        self.assertEqual(next(item for item in next_turn if item.get("type") == "reasoning")["encrypted_content"], "opaque")
        self.assertEqual([item["id"] for item in next_turn if item.get("type") == "function_call"], ["fc_1"])
        self.assertEqual(next_turn[-1], {"type": "function_call_output", "call_id": "call_1", "output": "found"})

    def test_vision_stream_emits_text_and_uses_image_input(self):
        requests = []
        event = {"type": "response.output_text.delta", "sequence_number": 1, "output_index": 0,
                 "content_index": 0, "item_id": "msg_test", "delta": "图"}

        def handle(request):
            requests.append(json.loads(request.content))
            body = "event: response.output_text.delta\ndata: " + json.dumps(event) + "\n\n"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            model = OpenAIImage.new_instance("IMAGE", "gpt-6.1-terra", CREDENTIALS, http_client=client,
                                             reasoning_effort="none", temperature=0.2)
            chunks = list(model.stream([HumanMessage(content=[{"type": "text", "text": "read"},
                                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}])]))
        self.assertEqual("".join(chunk.content for chunk in chunks), "图")
        self.assertEqual(requests[0]["input"][0]["content"][1]["type"], "input_image")
        self.assertEqual(requests[0]["temperature"], 0.2)
        self.assertNotIn("stream_options", requests[0])

    async def test_async_responses_and_vision_stream(self):
        payloads = []

        async def handle(request):
            data = json.loads(request.content)
            payloads.append(data)
            if data.get("stream"):
                event = {"type": "response.output_text.delta", "sequence_number": 1, "output_index": 0,
                         "content_index": 0, "item_id": "msg_test", "delta": "async"}
                body = "event: response.output_text.delta\ndata: " + json.dumps(event) + "\n\n"
                return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
            output = [{"id": "msg_1", "type": "message", "role": "assistant", "status": "completed",
                       "content": [{"type": "output_text", "text": "async", "annotations": []}]}]
            return httpx.Response(200, json={"id": "resp_async", "object": "response", "created_at": 1,
                                             "model": data["model"], "status": "completed", "output": output})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            model = OpenAIImage.new_instance("IMAGE", "gpt-6.1-terra", CREDENTIALS, http_async_client=client,
                                             streaming=False, temperature=0.7)
            reply = await model.ainvoke("hello", reasoning={"effort": "low"}, temperature=0.9)
            self.assertEqual(reply.content, "async")
            self.assertEqual(payloads[0]["reasoning"]["effort"], "low")
            self.assertNotIn("temperature", payloads[0])
            chunks = [chunk.content async for chunk in model.astream("hello")]
            self.assertEqual("".join(chunks), "async")

    def test_custom_compatible_model_keeps_chat_completions(self):
        model = OpenAIChatModel.new_instance("LLM", "my-model", CREDENTIALS, temperature=0.5, streaming=False)
        payload = model._get_request_payload("test")
        self.assertIn("messages", payload)
        self.assertEqual(payload["temperature"], 0.5)
        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            OpenAIChatModel.new_instance("LLM", "gpt-6-astra", CREDENTIALS, reasoning_effort="none")

    def test_embedding_dimensions_batch_order_and_legacy_ada(self):
        model = OpenAIEmbeddingModel.new_instance("EMBEDDING", "text-embedding-3-large", CREDENTIALS, dimensions="1024")
        requests = []

        def handle(request):
            data = json.loads(request.content)
            requests.append(data)
            items = [{"object": "embedding", "index": i, "embedding": [float(v)]} for i, v in enumerate(data["input"])]
            return httpx.Response(200, json={"object": "list", "data": list(reversed(items)),
                                  "model": data["model"], "usage": {"prompt_tokens": 1, "total_tokens": 1}})

        with OpenAI(base_url=CREDENTIALS["api_base"], api_key=CREDENTIALS["api_key"],
                    http_client=httpx.Client(transport=httpx.MockTransport(handle))) as client:
            model.client = client.embeddings
            self.assertEqual(model.embed_documents(["0", "1", "2"], chunk_size=2), [[0.0], [1.0], [2.0]])
            ada = OpenAIEmbeddingModel.new_instance("EMBEDDING", "text-embedding-ada-002", CREDENTIALS, dimensions="1024")
            ada.client = client.embeddings
            ada.embed_query("0")
        self.assertEqual(requests[0]["dimensions"], 1024)
        self.assertNotIn("dimensions", requests[-1])
        with self.assertRaisesRegex(ValueError, "chunk_size"):
            model.embed_documents([], chunk_size=0)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            OpenAIEmbeddingModel.new_instance("EMBEDDING", "text-embedding-3-small", CREDENTIALS, dimensions=1536.5)

    def test_media_requests_use_matching_sdk_endpoints_and_formats(self):
        requests = {}

        def handle(request):
            path = request.url.path
            requests[path] = request.content
            if path.endswith("transcriptions"):
                return httpx.Response(200, json={"text": "transcript"})
            if path.endswith("speech"):
                return httpx.Response(200, content=b"mp3")
            return httpx.Response(200, json={"created": 1, "data": [{"b64_json": "QUJD"}]})

        def test_client(**kwargs):
            return OpenAI(base_url=kwargs["base_url"], api_key=kwargs["api_key"],
                          http_client=httpx.Client(transport=httpx.MockTransport(handle)))

        base = __package__ + ".model."
        audio = io.BytesIO(b"RIFF")
        audio.name = "clip.wav"
        with patch(base + "stt.OpenAI", test_client):
            stt = OpenAISpeechToText.new_instance("STT", "gpt-transcribe", CREDENTIALS, languages="zh,en", keywords="LiteKB")
            self.assertEqual(stt.speech_to_text(audio), "transcript")
        multipart = requests["/v1/audio/transcriptions"]
        for value in (b"clip.wav", b"languages[]", b"keywords[]", b"LiteKB"):
            self.assertIn(value, multipart)
        with patch(base + "tts.OpenAI", test_client):
            tts = OpenAITextToSpeech.new_instance("TTS", "gpt-4o-mini-tts", CREDENTIALS, instructions="neutral")
            self.assertEqual(tts.text_to_speech("test"), b"mp3")
        self.assertEqual(json.loads(requests["/v1/audio/speech"])["voice"], "marin")
        with patch(base + "tti.OpenAI", test_client):
            image = OpenAITextToImage.new_instance("TTI", "gpt-image-2.6-flare", CREDENTIALS,
                                                   quality="xhigh", complexity="low", show_ref_label=True)
            self.assertEqual(image.generate_image("test"), ["QUJD"])
        payload = json.loads(requests["/v1/images/generations"])
        self.assertEqual(payload["complexity"], "low")
        self.assertEqual(payload["quality"], "xhigh")
        self.assertNotIn("show_ref_label", payload)
        previous = OpenAITextToImage.new_instance("TTI", "gpt-image-2.5-flare", CREDENTIALS, complexity="low")
        self.assertNotIn("complexity", previous.params)
        self.assertNotIn("extra_body", previous.params)
