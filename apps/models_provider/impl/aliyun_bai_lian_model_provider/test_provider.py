"""Exercise provider lookup, parameter forms and the actual HTTP payloads without a vendor account."""
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from openai import OpenAI


PACKAGE = "models_provider.impl.aliyun_bai_lian_model_provider"
BASE = "https://workspace.cn-beijing.maas.aliyuncs.com"
KEYS = {"api_base": BASE + "/api/v1", "api_key": "unit-key"}
VECTOR_KEYS = {"api_base": BASE + "/compatible-mode/v1", "dashscope_api_key": "unit-key"}


class BailianTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from django.conf import settings
        if not settings.configured:
            settings.configure(USE_I18N=False)
        services = patch.dict("sys.modules", {
            "common.utils.common": SimpleNamespace(encryption=Mock(), get_file_content=Mock(), _remove_empty_lines=str.strip),
            "maxkb.conf": SimpleNamespace(PROJECT_DIR=str(Path(__file__).resolve().parents[4])),
        })
        services.start()
        cls.addClassCleanup(services.stop)
        from .aliyun_bai_lian_model_provider import AliyunBaiLianModelProvider
        cls.provider = AliyunBaiLianModelProvider()

    def media(self):
        flag = patch("maxkb.capabilities.MEDIA_NODES", True)
        flag.start()
        self.addCleanup(flag.stop)

    def form(self, kind, name):
        return self.provider.get_model_credential(kind, name).get_model_params_setting_form(name)

    def native(self, *outputs):
        transport = patch(PACKAGE + ".transport.provider_request", side_effect=[
            Mock(json=Mock(return_value={"output": output})) for output in outputs
        ])
        mock = transport.start()
        self.addCleanup(transport.stop)
        return mock

    def test_discovery_catalog_docs_and_forms(self):
        self.media()
        for kind, names in {
            "LLM": ("qwen3.8-max", "qwen-plus"), "IMAGE": ("qwen3.8-flash", "qwen-vl-max-0809"),
            "EMBEDDING": ("qwen3.7-text-embedding", "text-embedding-v1"),
            "RERANKER": ("qwen3.7-text-rerank", "gte-rerank-v2"),
            "TTI": ("qwen-image-3.0", "wanx-v1"), "ITV": ("wan3.0-video", "wan2.2-i2v-flash"),
            "TTV": ("wan2.7-t2v", "wanx2.1-t2v-plus"), "STT": ("qwen3-asr-flash", "paraformer-realtime-v2"),
            "TTS": ("qwen-audio-3.1-tts-flash", "cosyvoice-v1"),
        }.items():
            with self.subTest(kind=kind):
                rows = self.provider.get_model_list(kind)
                self.assertTrue(set(names).issubset(row["name"] for row in rows))
                self.assertTrue(all(row["desc"] and row["docs_url"].startswith("https://help.aliyun.com/") for row in rows))
        self.assertIn("<svg", self.provider.get_model_provide_info().icon)
        self.assertNotIn("qwen4-max-preview", [r["name"] for r in self.provider.get_model_list("LLM")])
        fields = {f["field"] for f in self.form("LLM", "qwen3.7-plus").to_form_list()}
        self.assertTrue({"max_tokens", "top_p", "top_k", "seed", "enable_thinking", "thinking_budget"} <= fields)
        self.assertNotIn("enable_thinking", {f["field"] for f in self.form("LLM", "qwen3.6-max-preview").to_form_list()})
        self.assertNotIn("dimensions", self.form("EMBEDDING", "text-embedding-v1").get_default_form_data())
        self.assertNotIn("instruct", self.form("RERANKER", "gte-rerank-v2").get_default_form_data())

    def test_actual_sdk_chat_and_vision_requests(self):
        captured = []

        def respond(req):
            body = json.loads(req.content)
            captured.append((str(req.url), req.headers["authorization"], body))
            chunk = {"id": "id", "created": 1, "model": body["model"], "object": "chat.completion.chunk",
                     "choices": [{"index": 0, "delta": {"content": "OK"}, "finish_reason": None}]}
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")

        image = [{"type": "text", "text": "describe"},
                 {"type": "image_url", "image_url": {"url": "https://image.example/frame.png"}}]
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            for kind, name, content, thinking in (
                ("LLM", "qwen3.7-plus", "Hello", True), ("IMAGE", "qwen3.8-flash", image, False),
            ):
                model = self.provider.get_model(kind, name, KEYS, http_client=client, max_retries=0, max_tokens=177,
                                                top_k=20, enable_thinking=thinking, thinking_budget=123, model_id="local")
                self.assertEqual("".join(c.content for c in model.stream([HumanMessage(content=content)])), "OK")
                url, key, body = captured[-1]
                self.assertEqual(url, BASE + "/compatible-mode/v1/chat/completions")
                self.assertEqual(key, "Bearer unit-key")
                self.assertEqual(body["messages"][0]["content"], content)
                self.assertEqual(body["max_tokens"], 177)
                self.assertEqual(body["top_k"], 20)
                self.assertEqual(body["enable_thinking"], thinking)
                self.assertEqual("thinking_budget" in body, thinking)
                self.assertNotIn("model_id", body)

    def test_embeddings_wire_order_batches_fixed_dimensions(self):
        captured = []

        def respond(req):
            body = json.loads(req.content)
            captured.append(body)
            self.assertEqual(str(req.url), BASE + "/compatible-mode/v1/embeddings")
            return httpx.Response(200, json={"object": "list", "model": body["model"],
                                 "usage": {"prompt_tokens": 1, "total_tokens": 1}, "data": [
                {"index": i, "object": "embedding", "embedding": [float(body["input"][i])]}
                for i in reversed(range(len(body["input"])))
            ]})

        with httpx.Client(transport=httpx.MockTransport(respond)) as client, patch(
            PACKAGE + ".model.embedding.OpenAI", side_effect=lambda **kw: OpenAI(http_client=client, **kw)
        ):
            model = self.provider.get_model("EMBEDDING", "text-embedding-v4", VECTOR_KEYS, dimensions="768")
            self.assertEqual(model.embed_documents([str(i) for i in range(12)], chunk_size=64),
                             [[float(i)] for i in range(12)])
            self.assertEqual([len(b["input"]) for b in captured], [10, 2])
            self.assertEqual(captured[-1]["dimensions"], 768)
            model = self.provider.get_model("EMBEDDING", "text-embedding-v1", VECTOR_KEYS, dimensions=1024)
            self.assertEqual(model.embed_query("7"), [7.0])
            self.assertNotIn("dimensions", captured[-1])
            with self.assertRaisesRegex(ValueError, "Unsupported dimension"):
                self.provider.get_model("EMBEDDING", "text-embedding-v3", VECTOR_KEYS, dimensions=2048)

    def test_rerank_preserves_citations_and_family_protocol(self):
        for name in ("qwen3.7-text-rerank", "gte-rerank-v2", "qwen3-vl-rerank"):
            with self.subTest(name=name):
                wire = self.native({"results": [{"index": 1, "relevance_score": .87}]})
                model = self.provider.get_model("RERANKER", name, VECTOR_KEYS, top_n=9, instruct="Prioritize facts")
                docs = [Document(page_content="A"), Document(page_content="B", metadata={"paragraph_id": 123})]
                result = model.compress_documents(docs, "what?")
                verb, url = wire.call_args.args
                body = wire.call_args.kwargs["json"]
                self.assertEqual((verb, url), ("POST", BASE + "/api/v1/services/rerank/text-rerank/text-rerank"))
                self.assertEqual(body["parameters"]["top_n"], 2)
                self.assertEqual("instruct" in body["parameters"], name == "qwen3.7-text-rerank")
                self.assertEqual(body["input"]["documents"][1], {"text": "B"} if "-vl-" in name else "B")
                self.assertEqual(result[0].metadata, {"paragraph_id": 123, "relevance_score": .87})
                self.assertEqual(docs[1].metadata, {"paragraph_id": 123})

    def test_query_role_and_instruction_only_reach_native_query(self):
        wire = self.native({"embeddings": [{"embedding": [0.25], "text_index": 0}]})
        model = self.provider.get_model("EMBEDDING", "text-embedding-v4", VECTOR_KEYS, dimensions="768",
                                        use_query_type=True, instruct="Retrieve relevant passages.")
        self.assertEqual(model.embed_query("example?"), [0.25])
        self.assertEqual(wire.call_args.args,
                         ("POST", BASE + "/api/v1/services/embeddings/text-embedding/text-embedding"))
        body = wire.call_args.kwargs["json"]
        self.assertEqual(body["input"], {"texts": ["example?"]})
        self.assertEqual(body["parameters"], {"text_type": "query", "dimension": 768,
                                               "instruct": "Retrieve relevant passages."})
        with patch.object(model.client, "create", return_value=SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.50])]
        )) as documents:
            self.assertEqual(model.embed_documents(["reference"]), [[0.50]])
            documents.assert_called_once_with(input=["reference"], model="text-embedding-v4",
                                              encoding_format="float", dimensions=768)

    def test_save_validates_selected_parameters_and_catalog(self):
        model = Mock()
        credential = self.provider.get_model_credential("EMBEDDING", "text-embedding-v4")
        with patch.object(self.provider, "get_model", return_value=model) as get:
            self.assertTrue(credential.is_valid("EMBEDDING", "text-embedding-v4", VECTOR_KEYS, {"dimensions": 768},
                                                self.provider))
            get.assert_called_once_with("EMBEDDING", "text-embedding-v4", VECTOR_KEYS, dimensions=768)
            model.embed_query.assert_called_once()
            model.embed_query.side_effect = ValueError("upstream")
            self.assertFalse(credential.is_valid("EMBEDDING", "text-embedding-v4", VECTOR_KEYS, {}, self.provider))
            self.assertFalse(credential.is_valid("EMBEDDING", "text-embedding-v4", {}, {}, self.provider))
        self.media()
        image = self.provider.get_model_credential("TTI", "qwen-image-3.0")
        wire = self.native({"models": [{"model": "qwen-image-3.0"}]}, {"models": []})
        self.assertTrue(image.is_valid("TTI", "qwen-image-3.0", KEYS, {}, self.provider))
        self.assertFalse(image.is_valid("TTI", "qwen-image-3.0", KEYS, {}, self.provider))
        self.assertEqual(wire.call_args.args, ("GET", BASE + "/api/v1/models"))
        self.assertEqual(wire.call_args.kwargs["params"]["model"], "qwen-image-3.0")

    def test_image_generation_and_async_video_polling(self):
        self.media()
        wire = self.native({"choices": [{"message": {"content": [{"image": "img"}]}}]},
                           {"task_id": "id-1"}, {"task_status": "RUNNING"},
                           {"task_status": "SUCCEEDED", "video_url": "video"})
        image = self.provider.get_model("TTI", "qwen-image-3.0", KEYS, size="1024*1024", watermark=False)
        self.assertEqual(image.generate_image("ink", "noise"), ["img"])
        post = wire.call_args
        self.assertEqual(post.kwargs["json"]["input"]["messages"][0]["content"], [{"text": "ink"}])
        self.assertEqual(post.kwargs["json"]["parameters"]["negative_prompt"], "noise")
        video = self.provider.get_model("ITV", "wan2.7-i2v", KEYS, resolution="720P", duration=5)
        with patch(PACKAGE + ".transport.time.sleep"):
            self.assertEqual(video.generate_video("ink", first_frame_url="one", last_frame_url="two"), "video")
        create, first_poll, last_poll = wire.call_args_list[1:]
        self.assertEqual(create.kwargs["headers"]["X-DashScope-Async"], "enable")
        self.assertEqual(create.kwargs["json"]["input"]["media"],
                         [{"type": "first_frame", "url": "one"}, {"type": "last_frame", "url": "two"}])
        self.assertEqual(first_poll.args, ("GET", BASE + "/api/v1/tasks/id-1"))
        self.assertEqual(first_poll.args, last_poll.args)

    def test_old_image_task_and_stt_credential_routes(self):
        self.media()
        wire = self.native({"task_id": "legacy"}, {"task_status": "SUCCEEDED", "results": [{"url": "img"}]})
        legacy = self.provider.get_model("TTI", "qwen-image-plus", KEYS, model_id="local", size="1024*1024")
        self.assertEqual(legacy.generate_image("ink"), ["img"])
        create = wire.call_args_list[0]
        self.assertIn("/services/aigc/text2image/image-synthesis", create.args[1])
        self.assertEqual(create.kwargs["json"]["input"], {"prompt": "ink"})
        self.assertNotIn("model_id", create.kwargs["json"]["parameters"])
        model = self.provider.get_model("STT", "custom-stt", {"api_url": BASE + "/api/v1", "api_key": "custom",
                                                              "type": "omni"}, model_id="local", CueWord="transcribe")
        self.assertEqual(model.params, {"CueWord": "transcribe"})
        self.assertEqual(model.api_url, BASE + "/compatible-mode/v1")

    def test_native_keys_are_isolated_and_failed_video_is_not_resubmitted(self):
        self.media()
        model_a = self.provider.get_model("TTV", "wan3.0-video", KEYS)
        model_b = self.provider.get_model("TTV", "wan3.0-video", {"api_base": "https://region-b.example/api/v1",
                                                                 "api_key": "key-b"})
        wire = self.native({"task_id": "a"}, {"task_status": "FAILED", "code": "bad_input"},
                           {"task_id": "b"}, {"task_status": "SUCCEEDED", "video_url": "b.mp4"})
        with self.assertRaisesRegex(ValueError, "FAILED"):
            model_a.generate_video("scene")
        self.assertEqual(model_b.generate_video("scene"), "b.mp4")
        self.assertEqual([c.args[0] for c in wire.call_args_list], ["POST", "GET", "POST", "GET"])
        for req in wire.call_args_list[:2]:
            self.assertTrue(req.args[1].startswith(BASE + "/api/v1/"))
            self.assertEqual(req.kwargs["headers"]["Authorization"], "Bearer unit-key")
        for req in wire.call_args_list[2:]:
            self.assertTrue(req.args[1].startswith("https://region-b.example/api/v1/"))
            self.assertEqual(req.kwargs["headers"]["Authorization"], "Bearer key-b")

    def test_asr_audio_protocol_and_tts_download(self):
        self.media()
        wire = self.native({"text": "一二"}, {"choices": [{"message": {"content": [{"text": "three"}]}}]},
                           {"audio": {"url": "https://cdn.example/generated.wav"}})
        for name, options, expected in (
            ("qwen-audio-3.1-asr-flash", {"keep_dialect": True}, "一二"),
            ("qwen3-asr-flash", {"enable_itn": True}, "three"),
        ):
            audio = io.BytesIO(b"RIFF-mock")
            audio.name = "recording.wav"
            model = self.provider.get_model("STT", name, KEYS, **options)
            self.assertEqual(model.speech_to_text(audio), expected)
            body = wire.call_args.kwargs["json"]
            content = body["input"]["messages"][0]["content"][0]
            if name.startswith("qwen-audio"):
                self.assertEqual(content["type"], "input_audio")
                self.assertEqual(body["parameters"], {"format": "wav", "keep_dialect": True})
            else:
                self.assertTrue(content["audio"].startswith("data:audio/"))
                self.assertEqual(body["parameters"], {"asr_options": {"enable_itn": True}})
        voice = self.provider.get_model("TTS", "qwen-audio-3.0-tts-flash", KEYS, voice="custom", sample_rate=24000)
        with patch(PACKAGE + ".model.tts.fetch_public_bytes", return_value=b"audio") as fetch:
            self.assertEqual(voice.text_to_speech("hello"), b"audio")
            fetch.assert_called_once_with("https://cdn.example/generated.wav")
        self.assertEqual(wire.call_args.args, ("POST", BASE + "/api/v1/services/audio/tts/SpeechSynthesizer"))
        self.assertEqual(wire.call_args.kwargs["json"]["input"], {"text": "hello", "voice": "custom", "sample_rate": 24000})
