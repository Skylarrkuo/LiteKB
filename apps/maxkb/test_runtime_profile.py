import os
import unittest
from unittest.mock import patch

from maxkb import capabilities


class RuntimeProfileTests(unittest.TestCase):
    def test_flag_syntax_is_explicit(self):
        for value, expected in (("True", True), ("1", True), ("false", False), ("0", False)):
            with self.subTest(value=value), patch.dict(os.environ, {"LITEKB_TEST_FEATURE": value}):
                self.assertEqual(capabilities.enabled("LITEKB_TEST_FEATURE"), expected)
        with patch.dict(os.environ, {"LITEKB_TEST_FEATURE": "typo"}), self.assertRaises(ValueError):
            capabilities.enabled("LITEKB_TEST_FEATURE")

    def test_disabled_media_in_nested_loops_is_reported(self):
        graph = {"nodes": [{"type": "text-to-speech-node"}]}
        for _ in range(2):
            graph = {"nodes": [{"type": "loop-node", "properties": {"node_data": {"loop_body": graph}}}]}
        with patch.object(capabilities, "DISABLED_NODES", capabilities.MEDIA_NODE_TYPES):
            self.assertEqual(capabilities.disabled_workflow_node(graph), "text-to-speech-node")

    def test_embedded_graph_rejects_retired_web_source_even_with_media_enabled(self):
        graph = {"nodes": [{"type": "tool-node", "properties": {"workflow": {
            "nodes": [{"type": "image-generate-node"}, {"type": "data-source-web-node"}]
        }}}]}
        with patch.object(capabilities, "DISABLED_NODES", {"data-source-web-node"}):
            self.assertEqual(capabilities.disabled_workflow_node(graph), "data-source-web-node")

    def test_vision_rag_and_control_flow_remain_available(self):
        graph = {"nodes": [{"type": name} for name in (
            "image-understand-node", "loop-node", "search-knowledge-node", "condition-node", "mcp-node",
        )]}
        self.assertIsNone(capabilities.disabled_workflow_node(graph))
        with patch.object(capabilities, "MEDIA_NODES", False):
            for model_type in ("IMAGE", "LLM", "EMBEDDING", "RERANKER"):
                self.assertTrue(capabilities.model_type_enabled(model_type))
            for model_type in ("STT", "TTS", "TTI", "TTV", "ITV"):
                self.assertFalse(capabilities.model_type_enabled(model_type))

    def test_installed_media_models_become_available(self):
        with patch.object(capabilities, "MEDIA_NODES", True):
            for model_type in capabilities.MEDIA_MODEL_TYPES:
                self.assertTrue(capabilities.model_type_enabled(model_type))
