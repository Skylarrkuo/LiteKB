"""Regression coverage for configuration and debug of imported workspace tools."""
import json
import pickle
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import resolve
from rest_framework.exceptions import ValidationError

from application.serializers.common import ToolExecute
from common.exception.app_exception import AppApiException
from common.mcp.sandbox import prepare_tool_execution
from common.utils.rsa_util import rsa_long_decrypt
from tools.models import Tool, ToolFolder
from tools.serializers.tool import ToolExportModelSerializer, ToolInstance, ToolSerializer, tool_execution
from tools.serializers.tool_workflow import ToolWorkflowSerializer
from users.models import User


def echo_workflow_package():
    """A local .tool fixture. Its only executable nodes read input and assign output."""
    start, base, assign = "tool-start-node", "tool-base-node", "echo-assignment"
    field = {"field": "text", "name": "text", "type": "string", "label": "输入文本", "required": True}
    output = {"field": "echo", "name": "echo", "type": "string", "label": "回声", "default_value": ""}
    flow = {
        "nodes": [
            {"id": base, "type": base, "x": 120, "y": 80, "properties": {
                "stepName": "基础信息", "node_data": {}, "user_input_field_list": [field],
                "user_output_field_list": [output], "config": {},
            }},
            {"id": start, "type": start, "x": 120, "y": 340, "properties": {
                "stepName": "开始", "node_data": {}, "config": {"globalFields": [{"label": "输入文本", "value": "text"}]},
            }},
            {"id": assign, "type": "variable-assign-node", "x": 560, "y": 340, "properties": {
                "stepName": "返回输入", "config": {"fields": []}, "node_data": {"variable_list": [{
                    "name": "echo", "type": "string", "fields": ["output", "echo"],
                    "source": "referencing", "reference": ["global", "text"],
                }]},
            }},
        ],
        "edges": [{"id": "start-to-echo", "type": "app-edge", "sourceNodeId": start, "targetNodeId": assign,
                   "sourceAnchorId": start + "_right", "targetAnchorId": assign + "_left"}],
    }
    tool = {"name": "本地回声", "desc": "将输入原样返回", "code": "", "tool_type": "WORKFLOW",
            "input_field_list": [], "init_field_list": [], "tool_list": [], "work_flow": flow}
    return pickle.dumps(ToolInstance(tool, "v2"))


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "saved-tools-tests"}})
class SavedToolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        workspace = "debug-" + uuid.uuid4().hex[:16]
        cls.user = User.objects.create(username=workspace, nick_name="debug", password="unused")
        cls.folder = ToolFolder.objects.create(pk=workspace, workspace_id=workspace, name=workspace)

    def setUp(self):
        self.workspace = self.folder.pk
        self.tool = Tool.objects.create(name="Sum", desc="Deterministic sum", code="def add(a, b): return a + b",
                                        input_field_list=[{"name": "a", "type": "int", "is_required": True}],
                                        init_field_list=[{"field": "b", "label": "b", "input_type": "Slider",
                                                          "required": True, "default_value": 0}],
                                        workspace_id=self.workspace, folder=self.folder, user=self.user, is_active=False)

    def edit(self, data, tool_id=None):
        return ToolSerializer.Operate(data={"id": tool_id or self.tool.id, "user_id": self.user.id,
                                            "workspace_id": self.workspace}).edit(data)

    def debug(self, data, workspace=None):
        debug = ToolSerializer.Debug(data={"user_id": self.user.id, "workspace_id": workspace or self.workspace})
        return debug.debug_saved(self.tool.id, data)

    def test_parameter_only_edit_masks_preserves_and_filters(self):
        fields = self.tool.init_field_list + [{"field": "token", "label": "token", "input_type": "PasswordInput",
                                               "required": True}]
        self.edit({"init_field_list": fields})
        with self.assertRaises(ValidationError):
            self.edit({"is_active": True})
        secret = "fixture-only-token"
        saved = self.edit({"is_active": True, "init_params": {"b": 0, "token": secret, "extra": "drop"}})
        self.assertTrue(saved["is_active"])
        masked = saved["init_params"]["token"]
        self.assertNotIn(secret, json.dumps(saved, cls=DjangoJSONEncoder))
        self.edit({"init_params": {"b": 4, "token": masked}})
        self.edit({"init_params": {"b": 2}})
        self.tool.refresh_from_db()
        self.assertNotIn(secret, self.tool.init_params)
        self.assertEqual(json.loads(rsa_long_decrypt(self.tool.init_params)), {"b": 2, "token": secret})
        self.edit({"is_active": False})
        self.assertFalse(self.edit({"init_params": {"token": ""}})["is_active"])

    def test_dispatches_only_saved_code_and_typed_inputs(self):
        self.edit({"init_params": {"b": 2}})
        self.tool.input_field_list[0]["value"] = 90
        self.tool.save(update_fields=["input_field_list"])
        payload = {"debug_field_list": [{"name": "a", "value": "3"}]}
        self.assertEqual(resolve(f"/admin/api/workspace/{self.workspace}/tool/{self.tool.id}/debug_saved")
                         .func.view_class.__name__, "SavedDebug")
        with patch("tools.serializers.tool.tool_sandbox_unavailable", return_value=""), \
                patch("tools.serializers.tool.tool_executor.exec_code", return_value=5) as dispatch:
            self.assertEqual(self.debug(payload), 5)
            dispatch.assert_called_once_with(self.tool.code, {"a": 3, "b": 2})
            with self.assertRaises(ValidationError):
                self.debug({**payload, "code": self.tool.code})
            with self.assertRaises(ValidationError):
                self.debug({"debug_field_list": [{"name": "b", "value": "9"}]})
            with self.assertRaises(AppApiException):
                self.debug({"debug_field_list": [{"name": "a", "value": ""}]})
            with self.assertRaises(AppApiException):
                self.debug(payload, "another-workspace")
            with self.assertRaises(AppApiException):
                ToolSerializer.Operate(data={"id": self.tool.id, "workspace_id": "another-workspace"}).one()
            dispatch.assert_called_once()

    def test_password_default_survives_masked_configuration(self):
        field = {"field": "token", "input_type": "PasswordInput", "label": "Token", "required": True,
                 "default_value": "reviewed-test-default"}
        initial = self.edit({"init_field_list": [field]})
        self.assertNotIn(field["default_value"], json.dumps(initial, cls=DjangoJSONEncoder))
        visible = initial["init_field_list"][0]
        self.assertNotEqual(visible["default_value"], field["default_value"])
        self.edit({"init_field_list": [visible], "init_params": {"token": visible["default_value"]}, "is_active": True})
        self.tool.refresh_from_db()
        self.assertEqual(self.tool.init_field_list[0]["default_value"], field["default_value"])
        self.assertIsNone(self.tool.init_params)
        self.assertNotIn("default_value", ToolExportModelSerializer(self.tool).data["init_field_list"][0])

    def test_unsupported_platform_never_dispatches(self):
        with patch("common.mcp.sandbox.sys.platform", "win32"), patch("subprocess.run") as child:
            self.assertEqual(tool_execution("CUSTOM")["reason_code"], "linux_required")
            with self.assertRaises(AppApiException):
                self.debug({"debug_field_list": []})
            with self.assertRaises(ValueError):
                prepare_tool_execution()
            self.assertEqual(tool_execution("MCP")["reason_code"], "linux_required")
            self.assertEqual(tool_execution("DATA_SOURCE")["debug_mode"], "none")
            self.assertEqual(tool_execution("SKILL")["debug_mode"], "none")
            self.assertTrue(tool_execution("WORKFLOW")["available"])
            child.assert_not_called()

    def test_mcp_only_checks_saved_configuration(self):
        self.tool.tool_type = "MCP"
        servers = {"docs": {"transport": "sse", "url": "https://example.invalid/sse"}}
        self.tool.code = json.dumps(servers)
        self.tool.save(update_fields=["code", "tool_type"])
        with patch("tools.serializers.tool.tool_sandbox_unavailable", return_value=""), \
                patch("tools.serializers.tool.validate_mcp_config") as connection:
            self.assertIs(self.debug({}), True)
            connection.assert_called_once_with(servers)
            with self.assertRaises(ValidationError):
                self.debug({"debug_field_list": [{"name": "arbitrary", "value": "x"}]})
            connection.assert_called_once()

    def test_sandboxed_python_when_available(self):
        state = tool_execution(self.tool.tool_type)
        if not state["available"]:
            self.skipTest(state["reason_code"])
        self.edit({"init_params": {"b": 2}})
        self.assertEqual(self.debug({"debug_field_list": [{"name": "a", "value": "3"}]}), 5)

    def test_import_debug_publish_and_activate_builtin_workflow(self):
        file = SimpleUploadedFile("echo.tool", echo_workflow_package())
        saved = ToolSerializer.Import(data={"file": file, "user_id": self.user.id, "workspace_id": self.workspace,
                                            "folder_id": self.folder.id}).import_()
        tool_id = saved["id"]
        self.assertFalse(saved["is_active"])
        with self.assertRaises(ValidationError):
            self.edit({"is_active": True}, tool_id)
        workflow = ToolWorkflowSerializer.Operate(data={"tool_id": tool_id, "workspace_id": self.workspace,
                                                        "user_id": self.user.id})
        record_id = str(uuid.uuid4())
        # Production releases idle request connections here. Keep the test transaction open.
        with patch("application.flow.tool_workflow_manage.close_old_connections"), patch.object(connection, "close"):
            response = workflow.debug({"text": "hello 世界", "chat_record_id": record_id}, self.user)
            self.assertTrue(list(response.streaming_content))
        record = ToolExecute(tool_id, record_id, self.workspace, None, None, True).get_record()
        self.assertEqual(record.meta["output"], {"echo": "hello 世界"}, record.meta["details"])
        self.assertTrue(workflow.publish())
        self.assertTrue(self.edit({"is_active": True}, tool_id)["is_active"])
