# -*- coding: utf-8 -*-
import asyncio
import base64
import io
import json
import os
import pickle
import re
import subprocess
import sys
from typing import Dict

import requests
import uuid_utils.compat as uuid
from application.models import Application
from common.constants.cache_version import Cache_Version
from common.database_model_manage.database_model_manage import DatabaseModelManage
from common.db.search import native_page_search, native_search, page_search
from common.exception.app_exception import AppApiException
from common.field.common import UploadedImageField
from common.mcp.sandbox import tool_sandbox_unavailable
from common.result import result
from common.utils.common import bytes_to_uploaded_file, common_convert_value, get_file_content
from common.utils.logger import maxkb_logger
from common.utils.file_reference import get_owned_upload
from common.utils.workflow_reference import get_exportable_tools, validate_resource_references
from common.utils.rsa_util import rsa_long_decrypt, rsa_long_encrypt
from common.utils.tool_code import ToolExecutor
from common.utils.url_validator import ALLOWED_CALLBACK_HOSTS, ALLOWED_DOWNLOAD_HOSTS, validate_trusted_url
from django.core import validators
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, CharField, OuterRef, Q, QuerySet, Subquery, Value, When
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from knowledge.models import File, FileSourceType, Knowledge
from langchain_core.messages import AIMessage, HumanMessage
from application.flow.backend.sandbox_mcp import SandboxMCPBackend
from maxkb.const import CONFIG, PROJECT_DIR
from models_provider.models import Model
from rest_framework import serializers, status
from system_manage.models import AuthTargetType, WorkspaceUserResourcePermission
from system_manage.models.resource_mapping import ResourceMapping
from system_manage.serializers.resource_mapping_serializers import ResourceMappingSerializer
from system_manage.serializers.user_resource_permission import UserResourcePermissionSerializer
from tools.models import Tool, ToolFolder, ToolRecord, ToolScope, ToolType, protect_skill_file
from tools.models.tool_workflow import ToolWorkflow
from tools.store_catalog import CATALOG_URL, StoreError, get_catalog, read_remote, resolve_release
from tools.serializers.init_field import (
    PASSWORD_MASK, InitField, InitFieldListField, restore_password_defaults, sanitize_init_field_list, validate_init_field_list,
)
from trigger.models import Trigger, TriggerTask
from users.serializers.user import is_workspace_manage, is_workspace_manage_permission_read

tool_executor = ToolExecutor()


def hand_node(node, update_tool_map):
    if node.get("type") == "tool-lib-node":
        tool_lib_id = node.get("properties", {}).get("node_data", {}).get("tool_lib_id") or ""
        node.get("properties", {}).get("node_data", {})["tool_lib_id"] = update_tool_map.get(tool_lib_id, tool_lib_id)

    if node.get("type") == "tool-workflow-lib-node":
        tool_lib_id = node.get("properties", {}).get("node_data", {}).get("tool_lib_id") or ""
        node.get("properties", {}).get("node_data", {})["tool_lib_id"] = update_tool_map.get(tool_lib_id, tool_lib_id)

    if node.get("type") == "search-knowledge-node":
        node.get("properties", {}).get("node_data", {})["knowledge_id_list"] = []
    if node.get("type") == "ai-chat-node":
        node_data = node.get("properties", {}).get("node_data", {})
        mcp_tool_ids = node_data.get("mcp_tool_ids") or []
        node_data["mcp_tool_ids"] = [update_tool_map.get(tool_id, tool_id) for tool_id in mcp_tool_ids]
        tool_ids = node_data.get("tool_ids") or []
        node_data["tool_ids"] = [update_tool_map.get(tool_id, tool_id) for tool_id in tool_ids]
        skill_tool_ids = node_data.get("skill_tool_ids") or []
        node_data["skill_tool_ids"] = [update_tool_map.get(tool_id, tool_id) for tool_id in skill_tool_ids]
    if node.get("type") == "mcp-node":
        mcp_tool_id = node.get("properties", {}).get("node_data", {}).get("mcp_tool_id") or ""
        node.get("properties", {}).get("node_data", {})["mcp_tool_id"] = update_tool_map.get(mcp_tool_id, mcp_tool_id)


class ToolInstance:
    def __init__(self, tool: dict, version: str):
        self.tool = tool
        self.version = version


ALLOWED_CLASSES = {("builtins", "dict"), ("uuid", "UUID"), ("tools.serializers.tool", "ToolInstance")}


def to_dict(message, file_name):
    return {
        "line": message.line,
        "column": message.column,
        "endLine": message.end_line,
        "endColumn": message.end_column,
        "message": (message.msg or "").replace(file_name, "code"),
        "type": message.category,
    }


def get_file_name():
    file_name = f"{uuid.uuid7()}"
    pylint_dir = os.path.join(PROJECT_DIR, "data", "pylint")
    if not os.path.exists(pylint_dir):
        os.makedirs(pylint_dir, 0o700, exist_ok=True)
        os.chmod(os.path.dirname(pylint_dir), 0o700)
    return os.path.join(pylint_dir, file_name)


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, folder, name):
        if (folder, name) in ALLOWED_CLASSES:
            return super().find_class(folder, name)
        raise pickle.UnpicklingError("global '%s.%s' is forbidden" % (folder, name))


def encryption(message: str):
    """
        加密敏感字段数据  加密方式是 如果密码是 1234567890  那么给前端则是 123******890
    :param message:
    :return:
    """
    if message == "":
        return ""
    if not isinstance(message, str) or len(message) < 5:
        return "***************"
    max_pre_len = 8
    max_post_len = 4
    message_len = len(message)
    pre_len = int(message_len / 5 * 2)
    post_len = int(message_len / 5 * 1)
    pre_str = "".join(
        [
            message[index]
            for index in range(0, max_pre_len if pre_len > max_pre_len else 1 if pre_len <= 0 else int(pre_len))
        ]
    )
    end_str = "".join(
        [
            message[index]
            for index in range(message_len - (int(post_len) if pre_len < max_post_len else max_post_len), message_len)
        ]
    )
    content = "***************"
    return pre_str + content + end_str


def tool_execution(tool_type):
    mode = {
        ToolType.CUSTOM: "python", ToolType.INTERNAL: "python", ToolType.MCP: "mcp", ToolType.WORKFLOW: "workflow",
    }.get(tool_type, "none")
    reasons = {
        "linux_required": _("Tool debugging requires an isolated Linux runtime. You can save parameters on this host."),
        "sandbox_disabled": _("Enable the isolated tool runtime to debug this tool."),
        "sandbox_missing": _("The isolated tool runtime library is missing."),
        "sandbox_identity": _("The isolated tool runtime account is unavailable."),
        "skill": _("Use this skill through an agent that supports skills."),
        "data_source": _("Test this data source in a data-source workflow node."),
        "unsupported": _("This tool type does not support independent debugging."),
    }
    reason = ""
    if mode in ("python", "mcp"):
        reason = tool_sandbox_unavailable()
    elif mode == "none":
        reason = {ToolType.SKILL: "skill", ToolType.DATA_SOURCE: "data_source"}.get(tool_type, "unsupported")
    return {"debug_mode": mode, "available": not reason, "reason_code": reason, "reason": str(reasons.get(reason, ""))}


def check_required_parameters(fields, saved):
    for field in fields:
        key = field["field"]
        value = saved.get(key, field.get("default_value"))
        if field.get("required") and (
            value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}
        ):
            raise serializers.ValidationError(_("Set the required initialization parameter: {name}").format(name=key))


def validate_mcp_config(servers: Dict):
    async def validate():
        backend = SandboxMCPBackend(servers)
        await backend.get_tools()

    try:
        asyncio.run(validate())
    except Exception as e:
        maxkb_logger.error(f"validate mcp config error: {e}")
        raise serializers.ValidationError(_("MCP configuration is invalid"))


class ToolModelSerializer(serializers.ModelSerializer):
    init_field_list = InitFieldListField(read_only=True)

    class Meta:
        model = Tool
        fields = [
            "id",
            "name",
            "icon",
            "desc",
            "code",
            "input_field_list",
            "init_field_list",
            "init_params",
            "scope",
            "is_active",
            "user_id",
            "template_id",
            "workspace_id",
            "folder_id",
            "tool_type",
            "label",
            "version",
            "create_time",
            "update_time",
        ]


class ToolRecordModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolRecord
        fields = [
            "id",
            "workspace_id",
            "tool_id",
            "source_type",
            "source_id",
            "meta",
            "state",
            "run_time",
            "create_time",
            "update_time",
        ]


class ToolExportModelSerializer(serializers.ModelSerializer):
    init_field_list = InitFieldListField(read_only=True, exporting=True)

    class Meta:
        model = Tool
        fields = [
            "id",
            "name",
            "icon",
            "desc",
            "code",
            "input_field_list",
            "init_field_list",
            "scope",
            "is_active",
            "user_id",
            "template_id",
            "workspace_id",
            "folder_id",
            "tool_type",
            "label",
            "create_time",
            "update_time",
        ]


class UploadedFileField(serializers.FileField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_representation(self, value):
        return value


class ToolInputField(serializers.Serializer):
    name = serializers.CharField(required=True, label=_("variable name"))
    is_required = serializers.BooleanField(required=True, label=_("required"))
    type = serializers.CharField(
        required=True,
        label=_("type"),
        validators=[
            validators.RegexValidator(
                regex=re.compile("^string|int|dict|array|float$"),
                message=_("fields only support string|int|dict|array|float"),
                code=500,
            )
        ],
    )
    source = serializers.CharField(
        required=True,
        label=_("source"),
        validators=[
            validators.RegexValidator(
                regex=re.compile("^custom|reference$"), message=_("The field only supports custom|reference"), code=500
            )
        ],
    )


class ToolCreateRequest(serializers.Serializer):
    name = serializers.CharField(required=True, label=_("tool name"))

    desc = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("tool description"))

    code = serializers.CharField(required=True, label=_("tool content"))

    input_field_list = serializers.ListField(required=False, default=list, label=_("input field list"))

    init_field_list = InitField(required=False, default=list, many=True, label=_("init field list"))

    is_active = serializers.BooleanField(required=False, label=_("Is active"))

    folder_id = serializers.CharField(required=False, allow_null=True)


class ToolEditRequest(serializers.Serializer):
    name = serializers.CharField(required=False, label=_("tool name"), allow_null=True)
    desc = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("tool description"))
    code = serializers.CharField(
        required=False,
        label=_("tool content"),
        allow_null=True,
    )
    input_field_list = serializers.ListField(required=False, default=list, allow_null=True, label=_("input field list"))
    init_field_list = InitField(required=False, default=list, allow_null=True, many=True, label=_("init field list"))
    init_params = serializers.DictField(required=False, default=dict, allow_null=True, label=_("init params"))
    is_active = serializers.BooleanField(
        required=False,
        label=_("Is active"),
        allow_null=True,
    )
    folder_id = serializers.CharField(required=False, allow_null=True)


class AddInternalToolRequest(serializers.Serializer):
    name = serializers.CharField(required=False, label=_("tool name"), allow_null=True, allow_blank=True)
    folder_id = serializers.CharField(required=False, allow_null=True, label=_("folder id"))


class DebugField(serializers.Serializer):
    name = serializers.CharField(required=True, label=_("variable name"))
    value = serializers.CharField(required=False, allow_blank=True, allow_null=True, label=_("variable value"))


class SavedToolDebugRequest(serializers.Serializer):
    debug_field_list = DebugField(required=False, default=list, many=True)

    def to_internal_value(self, data):
        if isinstance(data, dict) and data.keys() - {"debug_field_list"}:
            raise serializers.ValidationError({"debug_field_list": _("Submit only the runtime input fields.")})
        return super().to_internal_value(data)


class StoreInstallRequest(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=64)
    folder_id = serializers.CharField(required=False, max_length=64)
    version = serializers.CharField(required=False, max_length=64)
    download_url = serializers.CharField(required=False, max_length=2048)


def notify_store_download(release):
    url = release.get("downloadCallbackUrl")
    if not url:
        return
    try:
        if validate_trusted_url(url, ALLOWED_CALLBACK_HOSTS):
            with requests.get(url, timeout=(2, 3), allow_redirects=False, stream=True):
                pass
    except (ValueError, requests.RequestException):
        maxkb_logger.info("Tool store download counter unavailable")


def parse_store_package(raw):
    try:
        package = RestrictedUnpickler(io.BytesIO(raw)).load()
        if not isinstance(package, ToolInstance) or not isinstance(package.tool, dict):
            raise ValueError()
        return package.tool
    except (ValueError, AttributeError, TypeError, EOFError, pickle.UnpicklingError):
        raise AppApiException(400, _("Unsupported file format")) from None


class ToolDebugRequest(serializers.Serializer):
    code = serializers.CharField(required=True, label=_("tool content"))
    input_field_list = serializers.ListField(required=False, default=list, label=_("input field list"))
    init_field_list = InitField(required=False, default=list, many=True, label=_("init field list"))
    init_params = serializers.DictField(required=False, default=dict, label=_("init params"))
    debug_field_list = DebugField(required=True, many=True)


class PylintInstance(serializers.Serializer):
    code = serializers.CharField(required=True, allow_null=True, allow_blank=True, label=_("function content"))


class ToolSerializer(serializers.Serializer):
    class Query(serializers.Serializer):
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        folder_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, label=_("folder id"))
        name = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("tool name"))
        user_id = serializers.UUIDField(required=False, allow_null=True, label=_("user id"))
        scope = serializers.CharField(required=True, label=_("scope"))
        tool_type = serializers.CharField(required=False, label=_("tool type"), allow_null=True, allow_blank=True)
        create_user = serializers.UUIDField(required=False, label=_("create user"), allow_null=True)

        def get_query_set(self, workspace_manage, is_x_pack_ee):
            tool_query_set = QuerySet(Tool).filter(workspace_id=self.data.get("workspace_id"))
            folder_query_set = QuerySet(ToolFolder)
            default_query_set = QuerySet(Tool)

            workspace_id = self.data.get("workspace_id")
            user_id = self.data.get("user_id")
            scope = self.data.get("scope")
            tool_type = self.data.get("tool_type")
            desc = self.data.get("desc")
            name = self.data.get("name")
            folder_id = self.data.get("folder_id")
            create_user = self.data.get("create_user")

            if workspace_id is not None:
                folder_query_set = folder_query_set.filter(workspace_id=workspace_id)
                default_query_set = default_query_set.filter(workspace_id=workspace_id)
            if folder_id is not None and folder_id != workspace_id:
                folder_query_set = folder_query_set.filter(parent=folder_id)
                default_query_set = default_query_set.filter(folder_id=folder_id)
            if name is not None:
                folder_query_set = folder_query_set.filter(name__icontains=name)
                default_query_set = default_query_set.filter(name__icontains=name)
            if desc is not None:
                folder_query_set = folder_query_set.filter(desc__icontains=desc)
                default_query_set = default_query_set.filter(desc__icontains=desc)
            if create_user is not None:
                tool_query_set = tool_query_set.filter(user_id=create_user)
                folder_query_set = folder_query_set.filter(user_id=create_user)

            default_query_set = default_query_set.order_by("-create_time")

            if scope is not None:
                tool_query_set = tool_query_set.filter(scope=scope)
            if tool_type:
                tool_query_set = tool_query_set.filter(tool_type=tool_type)

            query_set_dict = {
                "tool_query_set": tool_query_set,
                "default_query_set": default_query_set,
            }
            if not workspace_manage:
                query_set_dict["workspace_user_resource_permission_query_set"] = QuerySet(
                    WorkspaceUserResourcePermission
                ).filter(auth_target_type="TOOL", workspace_id=workspace_id, user_id=user_id)
            return query_set_dict

        def get_authorized_query_set(self):
            default_query_set = QuerySet(Tool)
            tool_type = self.data.get("tool_type")
            desc = self.data.get("desc")
            name = self.data.get("name")
            create_user = self.data.get("create_user")

            default_query_set = default_query_set.filter(workspace_id="None")
            default_query_set = default_query_set.filter(scope=ToolScope.SHARED)
            if name is not None:
                default_query_set = default_query_set.filter(name__icontains=name)
            if desc is not None:
                default_query_set = default_query_set.filter(desc__icontains=desc)
            if create_user is not None:
                default_query_set = default_query_set.filter(user_id=create_user)
            if tool_type:
                default_query_set = default_query_set.filter(tool_type=tool_type)

            default_query_set = default_query_set.order_by("-create_time")

            return default_query_set

        @staticmethod
        def is_x_pack_ee():
            workspace_user_role_mapping_model = DatabaseModelManage.get_model("workspace_user_role_mapping")
            role_permission_mapping_model = DatabaseModelManage.get_model("role_permission_mapping_model")
            return workspace_user_role_mapping_model is not None and role_permission_mapping_model is not None

        def get_tools(self):
            self.is_valid(raise_exception=True)

            workspace_manage = is_workspace_manage(self.data.get("user_id"), self.data.get("workspace_id"))
            is_x_pack_ee = self.is_x_pack_ee()
            results = native_search(
                self.get_query_set(workspace_manage, is_x_pack_ee),
                get_file_content(
                    os.path.join(
                        PROJECT_DIR,
                        "apps",
                        "tools",
                        "sql",
                        "list_tool.sql"
                        if workspace_manage
                        else ("list_tool_user_ee.sql" if is_x_pack_ee else "list_tool_user.sql"),
                    )
                ),
            )

            get_authorized_tool = DatabaseModelManage.get_model("get_authorized_tool")
            shared_queryset = QuerySet(Tool).none()
            if get_authorized_tool is not None:
                shared_queryset = self.get_authorized_query_set()
                shared_queryset = get_authorized_tool(shared_queryset, self.data.get("workspace_id"))

            return {
                "shared_tools": [ToolModelSerializer(data).data for data in shared_queryset],
                "tools": [
                    {
                        **tool,
                        "input_field_list": json.loads(tool.get("input_field_list", "[]")),
                        "init_field_list": sanitize_init_field_list(json.loads(tool.get("init_field_list", "[]"))),
                    }
                    for tool in results
                    if tool["resource_type"] == "tool"
                ],
            }

    class Create(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("user id"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))

        @transaction.atomic
        def insert(self, instance, with_valid=True):
            if with_valid:
                self.is_valid(raise_exception=True)
                ToolCreateRequest(data=instance).is_valid(raise_exception=True)
                # 校验代码是否包括禁止的关键字
                if instance.get("tool_type") == ToolType.MCP:
                    ToolExecutor().validate_mcp_transport(instance.get("code", ""))
            if instance.get('tool_type') == ToolType.WORKFLOW:
                validate_resource_references(instance, self.data['workspace_id'], self.data['user_id'])

            # 处理 work_flow_template
            if instance.get("work_flow_template") is not None:
                template_instance = instance.get("work_flow_template")
                download_url = template_instance.get("downloadUrl")
                if not validate_trusted_url(download_url, ALLOWED_DOWNLOAD_HOSTS):
                    raise AppApiException(500, _("Illegal download url"))
                # 查找匹配的版本名称
                res = requests.get(download_url, timeout=5, allow_redirects=False)
                tool = ToolSerializer.Import(
                    data={
                        "file": bytes_to_uploaded_file(res.content, "file.tool"),
                        "user_id": self.data.get("user_id"),
                        "workspace_id": self.data.get("workspace_id"),
                        "folder_id": str(instance.get("folder_id", self.data.get("workspace_id"))),
                    }
                ).import_(name=instance.get("name"), source="template")

                try:
                    download_callback_url = template_instance.get("downloadCallbackUrl", "")
                    if not validate_trusted_url(download_callback_url, ALLOWED_CALLBACK_HOSTS):
                       raise AppApiException(500, _("Illegal download callback url"))
                    requests.get(download_callback_url, timeout=5, allow_redirects=False)
                except Exception as e:
                    maxkb_logger.error(f"callback appstore tool download error: {e}")
                return tool

            tool_id = uuid.uuid7()
            Tool(
                id=tool_id,
                name=instance.get("name"),
                desc=instance.get("desc"),
                code=instance.get("code"),
                user_id=self.data.get("user_id"),
                workspace_id=self.data.get("workspace_id"),
                input_field_list=instance.get("input_field_list", []),
                init_field_list=validate_init_field_list(instance.get("init_field_list", [])),
                scope=instance.get("scope", ToolScope.WORKSPACE),
                tool_type=instance.get("tool_type", ToolType.CUSTOM),
                folder_id=instance.get("folder_id", self.data.get("workspace_id")),
                is_active=False,
            ).save()

            # 自动授权给创建者
            UserResourcePermissionSerializer(
                data={
                    "workspace_id": self.data.get("workspace_id"),
                    "user_id": self.data.get("user_id"),
                    "auth_target_type": AuthTargetType.TOOL.value,
                }
            ).auth_resource(str(tool_id))
            if instance.get("tool_type") == ToolType.WORKFLOW:
                ToolWorkflow(
                    id=uuid.uuid7(),
                    tool_id=tool_id,
                    work_flow=instance.get("work_flow", {}),
                    default_model_setting=instance.get("default_model_setting") or {},
                ).save()
            # 如果是SKILL类型的工具，修改file表中对应的记录
            if instance.get("tool_type") == ToolType.SKILL:
                file_id = instance.get("code")
                old_file = get_owned_upload(file_id, self.data.get("user_id"))
                if old_file:
                    # 创建新的文件副本,不复制实际文件内容
                    new_file_id = uuid.uuid7()
                    new_file = File(
                        id=new_file_id,
                        file_name=old_file.file_name,
                        file_size=old_file.file_size,
                        sha256_hash=old_file.sha256_hash,
                        source_type=FileSourceType.TOOL,
                        source_id=tool_id,
                        meta={**old_file.meta, "skill_file": True},
                    )
                    new_file.save(old_file.get_bytes())
                    # 更新工具的code为新的文件id
                    QuerySet(Tool).filter(id=tool_id).update(code=str(new_file_id))
            return ToolSerializer.Operate(data={"id": tool_id, "workspace_id": self.data.get("workspace_id")}).one()

    class TestConnection(serializers.Serializer):
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        code = serializers.CharField(required=True, label=_("tool content"))

        def test_connection(self):
            self.is_valid(raise_exception=True)
            # 校验代码是否包括禁止的关键字
            ToolExecutor().validate_mcp_transport(self.data.get("code", ""))

            # 校验mcp json
            validate_mcp_config(json.loads(self.data.get("code")))
            return True

    class Debug(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("user id"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))

        def debug(self, debug_instance):
            self.is_valid(raise_exception=True)
            request = ToolDebugRequest(data=debug_instance)
            request.is_valid(raise_exception=True)
            data = request.validated_data
            return self.run_python(data["code"], data["input_field_list"], data["debug_field_list"],
                                   data["init_field_list"], data["init_params"])

        def debug_saved(self, tool_id, instance):
            self.is_valid(raise_exception=True)
            request = SavedToolDebugRequest(data=instance)
            request.is_valid(raise_exception=True)
            tool = Tool.objects.filter(id=tool_id, workspace_id=self.validated_data["workspace_id"],
                                       scope=ToolScope.WORKSPACE).first()
            if tool is None:
                raise AppApiException(404, _("Tool not found"))
            state = tool_execution(tool.tool_type)
            if not state["available"]:
                raise AppApiException(400, state["reason"])
            inputs = request.validated_data["debug_field_list"]
            if state["debug_mode"] == "mcp" and not inputs:
                return ToolSerializer.TestConnection(data={"workspace_id": tool.workspace_id,
                                                           "code": tool.code}).test_connection()
            if state["debug_mode"] != "python":
                raise serializers.ValidationError(_("Use the debug action for this tool type."))
            allowed = {field["name"] for field in tool.input_field_list}
            submitted = [entry["name"] for entry in inputs]
            if len(set(submitted)) != len(submitted) or set(submitted) - allowed:
                raise serializers.ValidationError(_("Unknown or duplicate runtime input field."))
            init_params = json.loads(rsa_long_decrypt(tool.init_params)) if tool.init_params else {}
            check_required_parameters(tool.init_field_list, init_params)
            return self.run_python(tool.code, tool.input_field_list, inputs, tool.init_field_list, init_params)

        def run_python(self, code, input_field_list, debug_field_list, init_field_list, init_params):
            params = {
                field["name"]: self.convert_value(
                    field["name"], self.get_field_value(debug_field_list, field["name"], field.get("is_required")),
                    field.get("type"), field.get("is_required"),
                ) for field in input_field_list
            }
            # 合并初始化参数（默认值 → 已保存的启动参数 → 运行时入参）
            init_params_default_value = {i["field"]: i.get('default_value') for i in init_field_list}
            # 合并初始化参数
            if init_params is not None:
                all_params = init_params_default_value | init_params | params
            else:
                all_params = init_params_default_value | params
            return tool_executor.exec_code(code, all_params)

        @staticmethod
        def get_field_value(debug_field_list, name, is_required):
            result = [field for field in debug_field_list if field.get("name") == name]
            value = result[-1].get("value") if result else None
            if is_required and (value is None or (isinstance(value, str) and not value.strip())):
                raise AppApiException(500, f"{name}" + _("field has no value set"))
            return value

        @staticmethod
        def convert_value(name: str, value: str, _type: str, is_required: bool):
            if not is_required and (value is None or (isinstance(value, str) and len(value.strip()) == 0)):
                return None
            try:
                return common_convert_value(_type, value)
            except Exception:
                raise AppApiException(
                    500,
                    _("Field: {name} Type: {type} Value: {value} Type conversion error").format(
                        name=name, type=_type, value=value
                    ),
                )

    class Operate(serializers.Serializer):
        user_id = serializers.UUIDField(required=False, label=_("User ID"))
        id = serializers.UUIDField(required=True, label=_("tool id"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))

        def is_one_valid(self, *, raise_exception=False):
            super().is_valid(raise_exception=True)
            workspace_id = self.data.get("workspace_id")
            query_set = QuerySet(Tool).filter(id=self.data.get("id"))
            if workspace_id:
                query_set = query_set.filter(workspace_id=workspace_id)
            if not query_set.exists():
                get_authorized_tool = DatabaseModelManage.get_model("get_authorized_tool")
                shared = QuerySet(Tool).filter(id=self.data.get("id"), scope=ToolScope.SHARED)
                if not get_authorized_tool or not get_authorized_tool(shared, workspace_id).exists():
                    raise AppApiException(404, _("Tool not found"))

        def is_valid(self, *, raise_exception=False):
            super().is_valid(raise_exception=True)
            workspace_id = self.data.get("workspace_id")
            query_set = QuerySet(Tool).filter(id=self.data.get("id"))
            if workspace_id:
                query_set = query_set.filter(workspace_id=workspace_id)
            if not query_set.exists():
                raise AppApiException(500, _("Tool id does not exist"))

        @transaction.atomic
        def edit(self, instance, with_valid=True):
            if with_valid:
                self.is_valid(raise_exception=True)
                request = ToolEditRequest(data=instance, partial=True)
                request.is_valid(raise_exception=True)
                instance = request.validated_data

            tool = Tool.objects.select_for_update().filter(id=self.data.get("id"),
                                                           workspace_id=self.data.get("workspace_id")).first()
            if tool is None:
                raise serializers.ValidationError(_("Tool not found"))

            edit_field_list = [
                "name",
                "desc",
                "code",
                "icon",
                "input_field_list",
                "init_field_list",
                "init_params",
                "is_active",
                "folder_id",
            ]
            edit_dict = {
                field: instance.get(field)
                for field in edit_field_list
                if (field in instance and instance.get(field) is not None)
            }

            if "init_field_list" in edit_dict:
                edit_dict["init_field_list"] = validate_init_field_list(edit_dict["init_field_list"])
                restore_password_defaults(edit_dict["init_field_list"], tool.init_field_list)

            if "code" in edit_dict and tool.tool_type == ToolType.MCP:
                ToolExecutor().validate_mcp_transport(edit_dict["code"])
            if tool.tool_type == ToolType.SKILL and "code" in edit_dict and tool.code != edit_dict["code"]:
                get_owned_upload(edit_dict["code"], self.data.get("user_id"))
            if "folder_id" in edit_dict and not ToolFolder.objects.filter(
                id=edit_dict["folder_id"], workspace_id=tool.workspace_id,
            ).exists():
                raise serializers.ValidationError(_("Folder not found"))
            configuring = "init_field_list" in edit_dict or "init_params" in edit_dict
            enabling = edit_dict.get("is_active", tool.is_active if configuring else False)
            if configuring or enabling:
                fields = edit_dict.get("init_field_list", tool.init_field_list)
                old = json.loads(rsa_long_decrypt(tool.init_params)) if tool.init_params else {}
                supplied = edit_dict.get("init_params", {})
                saved = {}
                for field in fields:
                    key = field["field"]
                    if key not in supplied and key not in old:
                        continue
                    value = supplied.get(key, old.get(key))
                    if field.get("input_type") == "PasswordInput" and key in old and value == encryption(old[key]):
                        value = old[key]
                    elif field.get("input_type") == "PasswordInput" and key not in old and value == PASSWORD_MASK:
                        # The form displayed the masked field default. Keep using that default.
                        if field.get("default_value") not in (None, ""):
                            continue
                    saved[key] = value
                if enabling:
                    check_required_parameters(fields, saved)
                    if tool.tool_type == ToolType.WORKFLOW and not ToolWorkflow.objects.filter(
                        tool_id=tool.id, workspace_id=tool.workspace_id, is_publish=True,
                    ).exists():
                        raise serializers.ValidationError(_("Publish the workflow before enabling this tool."))
                if configuring:
                    edit_dict["init_params"] = rsa_long_encrypt(json.dumps(saved)) if saved else None

            edit_dict["update_time"] = timezone.now()
            if "code" in edit_dict and tool.code != edit_dict["code"]:
                protect_skill_file(tool)
            QuerySet(Tool).filter(
                id=self.data.get("id"), workspace_id=self.data.get("workspace_id")
            ).update(**edit_dict)
            if "is_active" in edit_dict:
                QuerySet(TriggerTask).filter(source_type="TOOL", source_id=self.data.get("id")).update(
                    is_active=edit_dict["is_active"]
                )

            # 如果是SKILL类型的工具，修改file表中对应的记录
            if tool.tool_type == ToolType.SKILL and "code" in edit_dict:
                old_file_id = tool.code
                file_id = edit_dict["code"]
                if old_file_id != file_id:
                    QuerySet(File).filter(id=old_file_id, source_type=FileSourceType.TOOL, source_id=tool.id).delete()
                    QuerySet(File).filter(id=file_id).update(source_id=tool.id, source_type=FileSourceType.TOOL)
                    skill_file = QuerySet(File).filter(id=file_id).first()
                    if skill_file:
                        QuerySet(File).filter(id=file_id).update(meta={**skill_file.meta, "skill_file": True})

            return self.one()

        @transaction.atomic
        def delete(self):
            from trigger.handler.simple_tools import deploy
            from trigger.serializers.trigger import TriggerModelSerializer

            self.is_valid(raise_exception=True)
            tool = QuerySet(Tool).filter(
                id=self.data.get("id"), workspace_id=self.data.get("workspace_id")
            ).first()
            if tool is None:
                raise serializers.ValidationError(_("Tool not found"))
            if tool.template_id is None and tool.icon != "":
                QuerySet(File).filter(id=tool.icon.split("/")[-1]).delete()
            if tool.tool_type == ToolType.SKILL:
                QuerySet(File).filter(id=tool.code).delete()
            QuerySet(WorkspaceUserResourcePermission).filter(target=tool.id).delete()
            QuerySet(Tool).filter(
                id=self.data.get("id"), workspace_id=self.data.get("workspace_id")
            ).delete()
            ResourceMapping.objects.filter(Q(target_id=self.data.get("id")) | Q(source_id=self.data.get("id"))).delete()
            QuerySet(ToolRecord).filter(tool_id=self.data.get("id")).delete()
            trigger_ids = list(
                QuerySet(TriggerTask)
                .filter(source_type="TOOL", source_id=self.data.get("id"))
                .values("trigger_id")
                .distinct()
            )
            QuerySet(TriggerTask).filter(
                source_type="TOOL", source_id=self.data.get("id")
            ).delete()
            for trigger_id in trigger_ids:
                trigger = Trigger.objects.filter(id=trigger_id["trigger_id"]).first()
                if trigger and trigger.is_active:
                    deploy(TriggerModelSerializer(trigger).data, **{})

        def one(self):
            self.is_one_valid(raise_exception=True)
            tool = QuerySet(Tool).filter(id=self.data.get("id")).select_related("user").first()
            nick_name = tool.user.nick_name if tool and tool.user else None
            if tool.init_params:
                tool.init_params = json.loads(rsa_long_decrypt(tool.init_params))
            if tool.init_field_list:
                password_fields = [i["field"] for i in tool.init_field_list if i.get("input_type") == "PasswordInput"]
                if tool.init_params:
                    for k in tool.init_params:
                        if k in password_fields and tool.init_params[k] is not None:
                            tool.init_params[k] = encryption(tool.init_params[k])
            if tool.tool_type == "SKILL":
                skill_file = QuerySet(File).filter(id=tool.code).first()
                skill_file_dict = (
                    {
                        "id": str(skill_file.id),
                        "name": skill_file.file_name,
                        "size": skill_file.file_size,
                    }
                    if skill_file
                    else None
                )
            work_flow = {}
            is_publish = False
            default_model_setting = {}
            if tool.tool_type == "WORKFLOW":
                tool_workflow = QuerySet(ToolWorkflow).filter(tool_id=tool.id).first()
                if tool_workflow:
                    work_flow = tool_workflow.work_flow
                    is_publish = tool_workflow.is_publish
                    default_model_setting = tool_workflow.default_model_setting
            return {
                **ToolModelSerializer(tool).data,
                "init_params": tool.init_params if tool.init_params else {},
                "nick_name": nick_name,
                "fileList": [skill_file_dict] if tool.tool_type == "SKILL" else [],
                "work_flow": work_flow,
                "default_model_setting": default_model_setting,
                "is_publish": is_publish,
                "execution": tool_execution(tool.tool_type),
            }

        def get_child_tool_list(self, work_flow, response):
            from application.flow.tools import get_tool_id_list

            tool_id_list = get_tool_id_list(work_flow, False)
            tool_id_list = [
                tool_id for tool_id in tool_id_list if len([r for r in response if r.get("id") == tool_id]) == 0
            ]
            tool_list = []
            if len(tool_id_list) > 0:
                tool_list = get_exportable_tools(tool_id_list, self.data.get('workspace_id'),
                                                 self.data.get('user_id'))
                work_flow_tools = [tool for tool in tool_list if tool.tool_type == ToolType.WORKFLOW]
                if len(work_flow_tools) > 0:
                    work_flow_tool_dict = {
                        tw.tool_id: tw
                        for tw in QuerySet(ToolWorkflow).filter(tool_id__in=[t.id for t in work_flow_tools])
                    }
                    for tool in tool_list:
                        if tool.tool_type == ToolType.WORKFLOW:
                            response.append(
                                {
                                    **ToolExportModelSerializer(tool).data,
                                    "work_flow": work_flow_tool_dict.get(tool.id).work_flow,
                                }
                            )
                            self.get_child_tool_list(work_flow_tool_dict.get(tool.id).work_flow, response)
                        else:
                            response.append(ToolExportModelSerializer(tool).data)
                else:
                    for tool in tool_list:
                        response.append(ToolExportModelSerializer(tool).data)
                skill_tools = [tool for tool in tool_list if tool.tool_type == ToolType.SKILL]
                for tool in skill_tools:
                    skill_file = QuerySet(File).filter(id=tool.code).first()
                    if skill_file:
                        tool.code = base64.b64encode(skill_file.get_bytes()).decode("utf-8")
                        response.append(ToolExportModelSerializer(tool).data)

            return response

        def export(self):
            try:
                self.is_valid()
                id = self.data.get("id")
                tool = QuerySet(Tool).filter(id=id).first()
                tool_dict = ToolExportModelSerializer(tool).data
                # 如果是SKILL类型的工具，校验文件是否存在
                if tool.tool_type == ToolType.SKILL:
                    skill_file = QuerySet(File).filter(id=tool.code).first()
                    if skill_file:
                        tool_dict["code"] = base64.b64encode(skill_file.get_bytes()).decode("utf-8")
                if tool.tool_type == ToolType.WORKFLOW:
                    workflow = QuerySet(ToolWorkflow).filter(tool_id=tool.id).first()
                    if workflow:
                        tool_dict["work_flow"] = workflow.work_flow
                        tool_dict["tool_list"] = self.get_child_tool_list(workflow.work_flow, [])
                mk_instance = ToolInstance(tool_dict, "v2")
                tool_pickle = pickle.dumps(mk_instance)
                response = HttpResponse(content_type="text/plain", content=tool_pickle)
                response["Content-Disposition"] = f'attachment; filename="{tool.name}.tool"'
                return response
            except Exception as e:
                return result.error(str(e), response_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    class Pylint(serializers.Serializer):
        def run(self, instance, is_valid=True):
            if is_valid:
                self.is_valid(raise_exception=True)
                PylintInstance(data=instance).is_valid(raise_exception=True)

            code = instance.get("code") or ""
            file_name = get_file_name()
            if not file_name.endswith(".py"):
                file_name = file_name + ".py"

            try:
                with open(file_name, "w", encoding="utf-8") as file:
                    file.write(code)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "ruff",
                        "check",
                        file_name,
                        "--output-format=json",
                        "--ignore=E501",
                        "--extend-select=PL",
                        "--no-cache",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                )

                if result.returncode not in (0, 1):
                    raise Exception(result.stderr or result.stdout)

                if not result.stdout.strip():
                    return []

                messages = json.loads(result.stdout)
                base_name = os.path.basename(file_name)
                return [
                    {
                        "type": "error"
                        if (
                                item.get("code") == "E999"
                                or str(item.get("code") or "").startswith("E9")
                                or item.get("code") in ["F821", "F822", "F823"]
                        )
                        else "warning",
                        "module": "",
                        "obj": "",
                        "line": item.get("location", {}).get("row", 1),
                        # Ruff column 是 1-based，前端 CodeMirror 用 0-based
                        "column": max(item.get("location", {}).get("column", 1) - 1, 0),
                        "endLine": item.get("end_location", {}).get("row", item.get("location", {}).get("row", 1)),
                        "endColumn": max(
                            item.get("end_location", {}).get("column", item.get("location", {}).get("column", 1) + 1)
                            - 1,
                            0,
                        ),
                        "path": base_name,
                        "symbol": item.get("code") or "",
                        "message": (
                            f"{item.get('code')}: {item.get('message')}" if item.get("code") else item.get("message")
                        ),
                    }
                    for item in messages
                ]

            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)

    class Import(serializers.Serializer):
        file = UploadedFileField(required=True, label=_("file"))
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        folder_id = serializers.CharField(required=False, allow_null=True, label=_("folder id"))

        @staticmethod
        def to_tool_workflow(work_flow, update_tool_map):
            for node in work_flow.get("nodes", []):
                hand_node(node, update_tool_map)
                if node.get("type") == "loop-node":
                    for n in node.get("properties", {}).get("node_data", {}).get("loop_body", {}).get("nodes", []):
                        hand_node(n, update_tool_map)
            return work_flow

        @staticmethod
        def to_tool(tool, workspace_id, user_id, folder_id):
            # 如果是技能类型的工具，需要将code保存为文件
            code = tool.get("code")
            if tool.get("tool_type") == ToolType.SKILL:
                skill_file_id = uuid.uuid7()
                skill_file = File(
                    id=skill_file_id,
                    file_name=f"{tool.get('name')}.zip",
                    source_type=FileSourceType.TOOL,
                    source_id=tool.get("id"),
                    meta={"skill_file": True},
                )
                skill_file.save(base64.b64decode(code))
                tool["code"] = skill_file_id
            return Tool(
                id=tool.get("id"),
                user_id=user_id,
                name=tool.get("name"),
                code=tool.get("code"),
                template_id=tool.get("template_id"),
                input_field_list=tool.get("input_field_list"),
                init_field_list=validate_init_field_list(tool.get("init_field_list")),
                is_active=False
                if (len((tool.get("init_field_list") or [])) > 0 or tool.get("tool_type") == ToolType.WORKFLOW)
                else tool.get("is_active"),
                tool_type=tool.get("tool_type", "CUSTOM") or "CUSTOM",
                scope=ToolScope.SHARED if workspace_id == "None" else ToolScope.WORKSPACE,
                folder_id=folder_id if folder_id else "default" if workspace_id == "None" else workspace_id,
                workspace_id=workspace_id,
            )

        def import_workflow_tools(self, tool, workspace_id, user_id, folder_id, new_child_policy):
            """

            @param tool:                  工具对象
            @param workspace_id:          工作空间id
            @param user_id:               用户id
            @param folder_id:             文件夹id
            @param new_child_policy:      子工具创建策略
                                          0: 不创建
                                          1: 对比创建: 如果存在就不创建 不存在则创建
                                          2: 全部创建
            @return:
            """
            from application.serializers.application import resolve_import_tools

            if new_child_policy == 0:
                tool_list = []
            else:
                tool_list = tool.get("tool_list") or []

            # 已存在且有权限的工具复用, 无权限或不存在则生成新id新建
            update_tool_map, tool_list = resolve_import_tools(
                tool_list, user_id, workspace_id, force_new=new_child_policy == 2
            )

            work_flow = self.to_tool_workflow(
                tool.get("work_flow"),
                update_tool_map,
            )
            created_ids = {str(imported_tool['id']) for imported_tool in tool_list}
            validate_resource_references({'work_flow': work_flow}, workspace_id, user_id, created_ids)
            for imported_tool in tool_list:
                if imported_tool.get('tool_type') == ToolType.WORKFLOW:
                    child_flow = self.to_tool_workflow(imported_tool.get('work_flow'), update_tool_map)
                    validate_resource_references({'work_flow': child_flow}, workspace_id, user_id, created_ids)
            defaults = {"tool_id": tool.get("id"), "workspace_id": workspace_id, "work_flow": work_flow}
            if tool.get("default_model_setting") is not None:
                defaults["default_model_setting"] = tool.get("default_model_setting")
            QuerySet(ToolWorkflow).update_or_create(
                tool_id=tool.get("id"),
                create_defaults={
                    "id": uuid.uuid7(),
                    "tool_id": tool.get("id"),
                    "workspace_id": workspace_id,
                    **defaults,
                },
                defaults=defaults,
            )
            tool_model_list = [self.to_tool(tool, workspace_id, user_id, folder_id) for tool in tool_list]
            workflow_tool_model_list = [
                {
                    "tool_id": t.get("id"),
                    "workflow": self.to_tool_workflow(
                        t.get("work_flow"),
                        update_tool_map,
                    ),
                }
                for t in tool_list
                if t.get("tool_type") == ToolType.WORKFLOW
            ]

            existing_records = QuerySet(ToolWorkflow).filter(
                tool_id__in=[wt.get("tool_id") for wt in workflow_tool_model_list], workspace_id=workspace_id
            )

            existing_map = {record.tool_id: record for record in existing_records}

            QuerySet(ToolWorkflow).bulk_create(
                [
                    ToolWorkflow(work_flow=wt.get("workflow"), workspace_id=workspace_id, tool_id=wt.get("tool_id"))
                    for wt in workflow_tool_model_list
                    if wt.get("tool_id") not in existing_map
                ]
            )

            if len(tool_model_list) > 0:
                QuerySet(Tool).bulk_create(tool_model_list)
                UserResourcePermissionSerializer(
                    data={
                        "workspace_id": self.data.get("workspace_id"),
                        "user_id": self.data.get("user_id"),
                        "auth_target_type": AuthTargetType.TOOL.value,
                    }
                ).auth_resource_batch([t.id for t in tool_model_list])

        def update_template_workflow(self, tool_id: str):
            self.is_valid(raise_exception=True)
            tool_instance_bytes = self.data.get("file").read()
            try:
                tool_instance = RestrictedUnpickler(io.BytesIO(tool_instance_bytes)).load()
            except Exception:
                raise AppApiException(1001, _("Unsupported file format"))
            tool = tool_instance.tool
            tool["id"] = tool_id
            folder_id = self.data.get("folder_id")
            self.import_workflow_tools(
                tool,
                workspace_id=self.data.get("workspace_id"),
                user_id=self.data.get("user_id"),
                folder_id=folder_id,
                new_child_policy=2,
            )
            return True

        @transaction.atomic
        def import_(self, scope=ToolScope.WORKSPACE, name=None, source=None):
            self.is_valid(raise_exception=True)
            workspace_id = self.validated_data["workspace_id"]
            user_id = self.validated_data["user_id"]
            folder_id = self.validated_data.get("folder_id") or workspace_id
            if scope == ToolScope.WORKSPACE:
                if not ToolFolder.objects.filter(pk=folder_id, workspace_id=workspace_id).exists():
                    raise AppApiException(400, _("Folder not found"))
            tool = parse_store_package(self.validated_data["file"].read())
            tool_id = uuid.uuid7()
            code = tool.get("code")
            if tool.get("tool_type") == ToolType.SKILL:
                skill_file_id = uuid.uuid7()
                skill_file = File(
                    id=skill_file_id,
                    file_name=f"{tool.get('name')}.zip",
                    source_type=FileSourceType.TOOL,
                    source_id=tool_id,
                    meta={"skill_file": True},
                )
                skill_file.save(base64.b64decode(code))
                code = skill_file_id
            tool_model = Tool(
                id=tool_id,
                name=name or tool.get("name"),
                desc=tool.get("desc"),
                code=code,
                user_id=user_id,
                workspace_id=workspace_id,
                input_field_list=tool.get("input_field_list"),
                init_field_list=validate_init_field_list(tool.get("init_field_list", [])),
                tool_type=tool.get("tool_type"),
                folder_id=folder_id,
                scope=scope,
                is_active=False,
            )
            # 校验代码是否包括禁止的关键字
            if tool.get("tool_type") == ToolType.MCP:
                ToolExecutor().validate_mcp_transport(code)
            tool_model.save()
            if tool.get("tool_type") == ToolType.WORKFLOW:
                tool["id"] = tool_id
                self.import_workflow_tools(
                    tool,
                    workspace_id=self.data.get("workspace_id"),
                    user_id=user_id,
                    folder_id=folder_id,
                    new_child_policy=2 if source == "template" else 1,
                )
            # 自动授权给创建者
            UserResourcePermissionSerializer(
                data={
                    "workspace_id": self.data.get("workspace_id"),
                    "user_id": self.data.get("user_id"),
                    "auth_target_type": AuthTargetType.TOOL.value,
                }
            ).auth_resource(str(tool_id))

            return ToolSerializer.Operate(data={"id": tool_id, "workspace_id": self.data.get("workspace_id")}).one()

    class IconOperate(serializers.Serializer):
        id = serializers.UUIDField(required=True, label=_("function ID"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        image = UploadedImageField(required=True, label=_("picture"))

        def is_valid(self, *, raise_exception=False):
            super().is_valid(raise_exception=True)
            workspace_id = self.data.get("workspace_id")
            query_set = QuerySet(Tool).filter(id=self.data.get("id"))
            if workspace_id:
                query_set = query_set.filter(workspace_id=workspace_id)
            if not query_set.exists():
                raise AppApiException(500, _("Tool id does not exist"))

        def edit(self, with_valid=True):
            if with_valid:
                self.is_valid(raise_exception=True)
            tool = QuerySet(Tool).filter(id=self.data.get("id")).first()
            if tool is None:
                raise AppApiException(500, _("Function does not exist"))
            # 删除旧的图片
            if tool.icon != "":
                QuerySet(File).filter(id=tool.icon.split("/")[-1]).delete()
            if self.data.get("image") is None:
                tool.icon = ""
            else:
                meta = {"debug": False}
                file_id = uuid.uuid7()
                file = File(
                    id=file_id,
                    file_name=self.data.get("image").name,
                    source_type=FileSourceType.TOOL,
                    source_id=tool.id,
                    meta=meta,
                )
                file.save(self.data.get("image").read())

                tool.icon = f"./oss/file/{file_id}"
            tool.save()

            return tool.icon

    class InternalTool(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        name = serializers.CharField(required=False, label=_("tool name"), allow_null=True, allow_blank=True)

        def get_internal_tools(self):
            self.is_valid(raise_exception=True)
            query_set = QuerySet(Tool)

            if self.data.get("name", "") != "":
                query_set = query_set.filter(
                    Q(name__icontains=self.data.get("name")) | Q(desc__icontains=self.data.get("name"))
                )

            query_set = query_set.filter(Q(scope=ToolScope.INTERNAL) & Q(is_active=True))
            return ToolModelSerializer(query_set, many=True).data

    class AddInternalTool(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        tool_id = serializers.UUIDField(required=True, label=_("tool id"))

        def add(self, instance, with_valid=True):
            if with_valid:
                self.is_valid(raise_exception=True)
                AddInternalToolRequest(data=instance).is_valid(raise_exception=True)

            internal_tool = QuerySet(Tool).filter(
                id=self.data.get("tool_id"), scope=ToolScope.INTERNAL
            ).first()
            if internal_tool is None:
                raise AppApiException(500, _("Tool does not exist"))

            tool_id = uuid.uuid7()
            tool = Tool(
                id=tool_id,
                name=instance.get("name", internal_tool.name),
                desc=internal_tool.desc,
                code=internal_tool.code,
                user_id=self.data.get("user_id"),
                icon=internal_tool.icon,
                workspace_id=self.data.get("workspace_id"),
                input_field_list=internal_tool.input_field_list,
                init_field_list=validate_init_field_list(internal_tool.init_field_list),
                scope=ToolScope.WORKSPACE,
                tool_type=ToolType.CUSTOM,
                folder_id=instance.get("folder_id", self.data.get("workspace_id")),
                template_id=internal_tool.id,
                label=internal_tool.label,
                is_active=False,
            )
            tool.save()

            # 自动授权给创建者
            UserResourcePermissionSerializer(
                data={
                    "workspace_id": self.data.get("workspace_id"),
                    "user_id": self.data.get("user_id"),
                    "auth_target_type": AuthTargetType.TOOL.value,
                }
            ).auth_resource(str(tool_id))

            return ToolModelSerializer(tool).data

    class StoreTool(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        name = serializers.CharField(required=False, allow_null=True, allow_blank=True)

        def get_appstore_tools(self):
            self.is_valid(raise_exception=True)
            return get_catalog(CONFIG.get("APPSTORE_URL", CATALOG_URL), self.validated_data.get("name") or "")

    class AddStoreTool(serializers.Serializer):
        user_id = serializers.UUIDField(required=True)
        workspace_id = serializers.CharField(required=True)
        tool_id = serializers.CharField(required=True)

        def add(self, instance):
            self.is_valid(raise_exception=True)
            req = StoreInstallRequest(data=instance)
            req.is_valid(raise_exception=True)
            workspace = self.validated_data["workspace_id"]
            folder_id = req.validated_data.get("folder_id") or workspace
            folders = ToolFolder.objects.filter(id=folder_id, workspace_id=workspace)
            if not folders.exists():
                raise StoreError(404, _("Folder not found"))
            item, release = resolve_release(get_catalog(CONFIG.get("APPSTORE_URL", CATALOG_URL)),
                                            self.validated_data["tool_id"], req.validated_data.get("version"),
                                            req.validated_data.get("download_url"))
            name = req.validated_data.get("name") or item["name"]
            if len(name) > 64:
                raise serializers.ValidationError(_("Tool name must be at most 64 characters"))
            file = SimpleUploadedFile("store.tool", read_remote(release["downloadUrl"], 32 * 1024 * 1024))
            with transaction.atomic():
                # Serialise concurrent imports into the same folder, including a retried request after a timeout.
                if not folders.select_for_update().first():
                    raise StoreError(404, _("Folder not found"))
                if Tool.objects.filter(workspace_id=workspace, folder_id=folder_id, name=name).exists():
                    raise StoreError(409, _("A tool with this name already exists in this folder"))
                importer = ToolSerializer.Import(data={"file": file, "user_id": self.validated_data["user_id"],
                                                       "workspace_id": workspace, "folder_id": folder_id})
                created = importer.import_(scope=ToolScope.WORKSPACE, name=name, source="template")
                tool = Tool.objects.get(pk=created["id"], workspace_id=workspace)
                tool.template_id, tool.version = item["id"], release["name"]
                tool.label, tool.icon = item["label"], item["icon"]
                tool.save(update_fields=["template_id", "version", "label", "icon"])
            notify_store_download(release)
            return ToolModelSerializer(tool).data

    class UpdateStoreTool(serializers.Serializer):
        user_id = serializers.UUIDField(required=True)
        workspace_id = serializers.CharField(required=True)
        tool_id = serializers.UUIDField(required=True)

        def update_tool(self, instance):
            self.is_valid(raise_exception=True)
            req = StoreInstallRequest(data=instance)
            req.is_valid(raise_exception=True)
            workspace = self.validated_data["workspace_id"]
            tools = Tool.objects.filter(id=self.validated_data["tool_id"], workspace_id=workspace, scope=ToolScope.WORKSPACE)
            target = tools.first()
            if not target:
                raise StoreError(404, _("Tool not found"))
            item, release = resolve_release(get_catalog(CONFIG.get("APPSTORE_URL", CATALOG_URL)), target.template_id,
                                            req.validated_data.get("version"), req.validated_data.get("download_url"))
            if target.version == release["name"]:
                return ToolModelSerializer(target).data
            raw = read_remote(release["downloadUrl"], 32 * 1024 * 1024)
            data = parse_store_package(raw)
            with transaction.atomic():
                tool = tools.select_for_update().first()
                if not tool or tool.template_id != item["id"]:
                    raise StoreError(404, _("Tool not found"))
                if tool.version == release["name"]:
                    return ToolModelSerializer(tool).data
                if tool.version != target.version:
                    raise StoreError(409, _("Tool was updated. Refresh and try again."))
                if data.get("tool_type", ToolType.CUSTOM) != tool.tool_type:
                    raise StoreError(400, _("Tool type does not match"))
                code = data.get("code")
                if tool.tool_type == ToolType.SKILL:
                    skill = File(id=uuid.uuid7(), file_name=f"{tool.name}.zip", source_type=FileSourceType.TOOL,
                                 source_id=tool.id, meta={"skill_file": True})
                    skill.save(base64.b64decode(code, validate=True))
                    code = str(skill.id)
                if tool.tool_type == ToolType.MCP:
                    ToolExecutor().validate_mcp_transport(code)
                if tool.tool_type == ToolType.WORKFLOW:
                    importer = ToolSerializer.Import(data={"file": SimpleUploadedFile("store.tool", raw),
                                                           "user_id": self.validated_data["user_id"],
                                                           "workspace_id": workspace, "folder_id": tool.folder_id})
                    importer.update_template_workflow(str(tool.id))
                tool.code, tool.desc = code, data.get("desc")
                tool.input_field_list = data.get("input_field_list") or []
                tool.init_field_list = validate_init_field_list(data.get("init_field_list") or [])
                tool.icon, tool.version, tool.label = item["icon"], release["name"], item["label"]
                tool.save()
            notify_store_download(release)
            return ToolModelSerializer(tool).data

    class ToolRecord(serializers.Serializer):
        workspace_id = serializers.CharField(required=False, allow_null=True, label=_("workspace id"))
        tool_id = serializers.UUIDField(required=True, label=_("tool id"))
        record_id = serializers.UUIDField(required=False, allow_null=True, label=_("record id"))
        source_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("source name"))
        source_type = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("source type"))
        state = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("state"))

        class Operate(serializers.Serializer):
            id = serializers.UUIDField(required=False, allow_null=True, label=_("record id"))
            tool_id = serializers.UUIDField(required=True, label=_("tool id"))
            workspace_id = serializers.CharField(required=False, allow_null=True, label=_("workspace id"))

            def one(self):
                self.is_valid(raise_exception=True)
                tool_record = cache.get(
                    Cache_Version.TOOL_WORKFLOW_EXECUTE.get_key(key=self.data.get("id")),
                    version=Cache_Version.TOOL_WORKFLOW_EXECUTE.get_version(),
                )
                if (
                    tool_record
                    and str(tool_record.get("tool_id")) == str(self.data.get("tool_id"))
                    and tool_record.get("workspace_id") == self.data.get("workspace_id")
                ):
                    return tool_record
                tool_record = (
                    QuerySet(ToolRecord)
                    .filter(
                        id=self.data.get("id"),
                        tool_id=self.data.get("tool_id"),
                        workspace_id=self.data.get("workspace_id"),
                    )
                    .first()
                )
                if tool_record:
                    return {
                        "id": tool_record.id,
                        "tool_id": tool_record.tool_id,
                        "workspace_id": tool_record.workspace_id,
                        "source_type": tool_record.source_type,
                        "source_id": tool_record.source_id,
                        "meta": tool_record.meta,
                        "state": tool_record.state,
                        "run_time": tool_record.run_time,
                    }
                raise AppApiException(500, _("Tool record does not exist"))

        def one(self):
            self.is_valid(raise_exception=True)
            if self.data.get("record_id"):
                page = self.get_tool_records(1, 1)
                return page.get("records")[0]

            return None

        def get_tool_records(self, current_page: int, page_size: int):
            self.is_valid(raise_exception=True)
            application_subquery = Application.objects.filter(id=OuterRef("source_id")).values("name")[:1]
            knowledge_subquery = Knowledge.objects.filter(id=OuterRef("source_id")).values("name")[:1]
            trigger_subquery = Trigger.objects.filter(id=OuterRef("source_id")).values("name")[:1]
            trigger_type_subquery = Trigger.objects.filter(id=OuterRef("source_id")).values("trigger_type")[:1]

            query_set = QuerySet(ToolRecord)
            query_set = (
                query_set.filter(tool_id=self.data.get("tool_id"))
                .annotate(
                    source_name=Case(
                        When(source_type="APPLICATION", then=Subquery(application_subquery)),
                        When(source_type="KNOWLEDGE", then=Subquery(knowledge_subquery)),
                        When(source_type="TRIGGER", then=Subquery(trigger_subquery)),
                        default=Value(""),
                        output_field=CharField(),
                    )
                )
                .annotate(
                    trigger_type=Case(
                        When(source_type="TRIGGER", then=Subquery(trigger_type_subquery)),
                        default=Value(""),
                        output_field=CharField(),
                    )
                )
                .annotate(tool_name=Subquery(Tool.objects.filter(id=OuterRef("tool_id")).values("name")[:1]))
                .annotate(tool_icon=Subquery(Tool.objects.filter(id=OuterRef("tool_id")).values("icon")[:1]))
            )
            if self.data.get("source_type"):
                query_set = query_set.filter(Q(source_type=self.data.get("source_type", "")))
            if self.data.get("state"):
                query_set = query_set.filter(Q(state=self.data.get("state", "")))
            if self.data.get("source_name"):
                query_set = query_set.filter(Q(source_name__icontains=self.data.get("source_name", "")))
            if self.data.get("record_id"):
                query_set = query_set.filter(Q(id=self.data.get("record_id")))
            if self.data.get("workspace_id"):
                query_set = query_set.filter(Q(workspace_id=self.data.get("workspace_id")))
            query_set = query_set.order_by("-create_time")

            return page_search(
                current_page,
                page_size,
                query_set,
                lambda record: {
                    **ToolRecordModelSerializer(record).data,
                    "source_name": record.source_name,
                    "tool_icon": record.tool_icon,
                    "trigger_type": record.trigger_type,
                },
            )

    class UploadSkillFile(serializers.Serializer):
        file = UploadedFileField(required=True, label=_("file"))
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))

        def upload(self):
            self.is_valid()
            file = self.data.get("file")
            if not file.name.endswith(".zip"):
                raise AppApiException(1001, _("Unsupported file format"))
            file_id = uuid.uuid7()
            file = File(id=file_id, file_name=self.data.get("file").name,
                        meta={"user_id": str(self.data.get("user_id")), "skill_file": True})
            file.save(self.data.get("file").read())
            return file_id

    class DownloadSkillFile(serializers.Serializer):
        user_id = serializers.UUIDField(required=True, label=_("User ID"))
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        tool_id = serializers.CharField(required=True, label=_("tool id"))

        def download(self):
            self.is_valid(raise_exception=True)
            tool = (
                QuerySet(Tool)
                .filter(
                    id=self.data.get("tool_id"), workspace_id=self.data.get("workspace_id"), tool_type=ToolType.SKILL
                )
                .first()
            )

            if tool is None:
                raise AppApiException(500, _("Tool does not exist"))
            skill_file = QuerySet(File).filter(id=tool.code).first()
            if skill_file is None:
                raise AppApiException(500, _("Skill file does not exist"))

            response = HttpResponse(content_type="application/zip", content=skill_file.get_bytes())
            response["Content-Disposition"] = f'attachment; filename="{skill_file.file_name}"'
            return response

    class GenerateCodeSerializer(serializers.Serializer):
        workspace_id = serializers.CharField(required=True, label=_("Workspace ID"))
        model_id = serializers.UUIDField(required=True, label=_("Model ID"))
        prompt = serializers.CharField(required=True, label=_("Prompt"))
        messages = serializers.ListField(required=True, label=_("Messages"))
        model_params_setting = serializers.DictField(required=False, default=dict, label=_("Model Params Setting"))
        init_field_list = serializers.ListField(required=False, default=list, label=_("Init Field List"))
        input_field_list = serializers.ListField(required=False, default=list, label=_("Input Field List"))

        def generate_code(self):
            from application.flow.tools import to_stream_response_simple
            from models_provider.tools import get_model_instance_by_model_workspace_id

            self.is_valid(raise_exception=True)

            workspace_id = self.data.get("workspace_id")
            model_id = self.data.get("model_id")
            prompt = self.data.get("prompt")
            messages = self.data.get("messages")
            model_params_setting = self.data.get("model_params_setting")
            init_field_list = self.data.get("init_field_list")
            input_field_list = self.data.get("input_field_list")

            message = messages[-1]["content"]
            q = (
                prompt.replace("{userInput}", message)
                .replace("{initFieldList}", json.dumps(init_field_list))
                .replace("{inputFieldList}", json.dumps(input_field_list))
            )

            messages[-1]["content"] = q
            SUPPORTED_MODEL_TYPES = ["LLM"]
            model_exist = QuerySet(Model).filter(id=model_id, model_type__in=SUPPORTED_MODEL_TYPES).exists()
            if not model_exist:
                raise Exception(_("Model does not exist or is not an LLM model"))

            def process():
                model = get_model_instance_by_model_workspace_id(
                    model_id=model_id, workspace_id=workspace_id, **model_params_setting
                )
                try:
                    for r in model.stream(
                            [
                                # SystemMessage(content=SYSTEM_ROLE),
                                *[
                                    HumanMessage(content=m.get("content"))
                                    if m.get("role") == "user"
                                    else AIMessage(content=m.get("content"))
                                    for m in messages
                                ]
                            ]
                    ):
                        yield "data: " + json.dumps({"content": r.content}) + "\n\n"
                except Exception as e:
                    yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

            return to_stream_response_simple(process())


class ToolBatchOperateSerializer(serializers.Serializer):
    workspace_id = serializers.CharField(required=True, label=_("workspace id"))

    def is_valid(self, *, raise_exception=False):
        super().is_valid(raise_exception=True)

    @transaction.atomic
    def batch_delete(self, instance: Dict, with_valid=True):
        from knowledge.serializers.common import BatchSerializer
        from trigger.handler.simple_tools import deploy
        from trigger.serializers.trigger import TriggerModelSerializer

        if with_valid:
            BatchSerializer(data=instance).is_valid(model=Tool, raise_exception=True)
            self.is_valid(raise_exception=True)
        id_list = instance.get("id_list")
        workspace_id = self.data.get("workspace_id")

        tool_query_set = QuerySet(Tool).filter(id__in=id_list, workspace_id=workspace_id)

        for tool in tool_query_set:
            if tool.template_id is None and tool.icon != "":
                QuerySet(File).filter(id=tool.icon.split("/")[-1]).delete()
            if tool.tool_type == ToolType.SKILL:
                QuerySet(File).filter(id=tool.code).delete()

        QuerySet(WorkspaceUserResourcePermission).filter(target__in=id_list).delete()
        QuerySet(ResourceMapping).filter(Q(target_id__in=id_list) | Q(source_id__in=id_list)).delete()
        QuerySet(ToolRecord).filter(tool_id__in=id_list).delete()

        trigger_ids = list(
            QuerySet(TriggerTask).filter(source_type="TOOL", source_id__in=id_list).values("trigger_id").distinct()
        )

        QuerySet(TriggerTask).filter(source_type="TOOL", source_id__in=id_list).delete()
        for trigger_id in trigger_ids:
            trigger = Trigger.objects.filter(id=trigger_id["trigger_id"]).first()
            if trigger and trigger.is_active:
                deploy(TriggerModelSerializer(trigger).data, **{})

        tool_query_set.delete()
        return True

    def batch_move(self, instance: Dict, with_valid=True):
        from knowledge.serializers.common import BatchMoveSerializer

        if with_valid:
            BatchMoveSerializer(data=instance).is_valid(model=Tool, raise_exception=True)
            self.is_valid(raise_exception=True)
        id_list = instance.get("id_list")
        folder_id = instance.get("folder_id")
        workspace_id = self.data.get("workspace_id")

        QuerySet(Tool).filter(id__in=id_list, workspace_id=workspace_id).update(folder_id=folder_id)
        return True


class ToolTreeSerializer(serializers.Serializer):
    class Query(serializers.Serializer):
        workspace_id = serializers.CharField(required=True, label=_("workspace id"))
        folder_id = serializers.CharField(required=True, label=_("folder id"))
        name = serializers.CharField(required=False, allow_null=True, allow_blank=True, label=_("tool name"))
        user_id = serializers.UUIDField(required=False, allow_null=True, label=_("user id"))
        scope = serializers.CharField(required=True, label=_("scope"))
        tool_type = serializers.CharField(required=False, label=_("tool type"), allow_null=True, allow_blank=True)
        tool_type_list = serializers.ListField(
            child=serializers.CharField(), required=False, label=_("tool type list"), allow_null=True, allow_empty=True
        )
        create_user = serializers.UUIDField(required=False, label=_("create user"), allow_null=True)

        def page_tool(self, current_page: int, page_size: int):
            self.is_valid(raise_exception=True)

            folder_id = self.data.get("folder_id", self.data.get("workspace_id"))
            root = ToolFolder.objects.filter(id=folder_id).first()
            if not root:
                raise serializers.ValidationError(_("Folder not found"))
            # 使用MPTT的get_descendants()方法获取所有相关节点
            all_folders = root.get_descendants(include_self=True)

            if self.data.get("name"):
                tools = QuerySet(Tool).filter(
                    Q(workspace_id=self.data.get("workspace_id"))
                    & Q(folder_id__in=all_folders)
                    & Q(user_id=self.data.get("user_id"))
                    & Q(name__contains=self.data.get("name"))
                )
            else:
                tools = QuerySet(Tool).filter(
                    Q(workspace_id=self.data.get("workspace_id"))
                    & Q(folder_id__in=all_folders)
                    & Q(user_id=self.data.get("user_id"))
                )
            return page_search(current_page, page_size, tools, lambda record: ToolModelSerializer(record).data)

        def get_query_set(self, workspace_manage, is_x_pack_ee):
            tool_query_set = QuerySet(Tool).filter(workspace_id=self.data.get("workspace_id"))
            folder_query_set = QuerySet(ToolFolder)
            default_query_set = QuerySet(Tool)

            workspace_id = self.data.get("workspace_id")
            user_id = self.data.get("user_id")
            scope = self.data.get("scope")
            tool_type = self.data.get("tool_type")
            desc = self.data.get("desc")
            name = self.data.get("name")
            folder_id = self.data.get("folder_id")
            create_user = self.data.get("create_user")

            if workspace_id is not None:
                folder_query_set = folder_query_set.filter(workspace_id=workspace_id)
                default_query_set = default_query_set.filter(workspace_id=workspace_id)
            if folder_id is not None and folder_id != workspace_id:
                folder_query_set = folder_query_set.filter(parent=folder_id)
                default_query_set = default_query_set.filter(folder_id=folder_id)
            if name is not None:
                folder_query_set = folder_query_set.filter(name__icontains=name)
                default_query_set = default_query_set.filter(name__icontains=name)
            if desc is not None:
                folder_query_set = folder_query_set.filter(desc__icontains=desc)
                default_query_set = default_query_set.filter(desc__icontains=desc)
            if create_user is not None:
                tool_query_set = tool_query_set.filter(user_id=create_user)
                folder_query_set = folder_query_set.filter(user_id=create_user)

            default_query_set = default_query_set.order_by("-create_time")

            if scope is not None:
                tool_query_set = tool_query_set.filter(scope=scope)

            tool_type_list = self.data.get("tool_type_list")
            if tool_type_list:
                tool_query_set = tool_query_set.filter(tool_type__in=tool_type_list)
            elif tool_type:
                tool_query_set = tool_query_set.filter(tool_type=tool_type)

            query_set_dict = {
                "tool_query_set": tool_query_set,
                "default_query_set": default_query_set,
            }
            if not workspace_manage:
                query_set_dict["workspace_user_resource_permission_query_set"] = QuerySet(
                    WorkspaceUserResourcePermission
                ).filter(auth_target_type="TOOL", workspace_id=workspace_id, user_id=user_id)
            return query_set_dict

        @staticmethod
        def is_x_pack_ee():
            workspace_user_role_mapping_model = DatabaseModelManage.get_model("workspace_user_role_mapping")
            role_permission_mapping_model = DatabaseModelManage.get_model("role_permission_mapping_model")
            return workspace_user_role_mapping_model is not None and role_permission_mapping_model is not None

        def page_tool_with_folders(self, current_page: int, page_size: int):
            self.is_valid(raise_exception=True)

            workspace_manage = is_workspace_manage_permission_read(self.data.get("user_id"),
                                                                   self.data.get("workspace_id"), 'TOOL:READ')
            is_x_pack_ee = self.is_x_pack_ee()
            result = native_page_search(
                current_page,
                page_size,
                self.get_query_set(workspace_manage, is_x_pack_ee),
                get_file_content(
                    os.path.join(
                        PROJECT_DIR,
                        "apps",
                        "tools",
                        "sql",
                        "list_tool.sql"
                        if workspace_manage
                        else ("list_tool_user_ee.sql" if is_x_pack_ee else "list_tool_user.sql"),
                    )
                ),
                post_records_handler=lambda record: {
                    **record,
                    "input_field_list": json.loads(record.get("input_field_list", "[]")),
                    "init_field_list": sanitize_init_field_list(json.loads(record.get("init_field_list", "[]"))),
                },
            )
            return ResourceMappingSerializer().get_resource_count(result)

        def get_tools(self):
            self.is_valid(raise_exception=True)

            workspace_manage = is_workspace_manage_permission_read(self.data.get("user_id"),
                                                                   self.data.get("workspace_id"), 'TOOL:READ')
            is_x_pack_ee = self.is_x_pack_ee()
            results = native_search(
                self.get_query_set(workspace_manage, is_x_pack_ee),
                get_file_content(
                    os.path.join(
                        PROJECT_DIR,
                        "apps",
                        "tools",
                        "sql",
                        "list_tool.sql"
                        if workspace_manage
                        else ("list_tool_user_ee.sql" if is_x_pack_ee else "list_tool_user.sql"),
                    )
                ),
            )

            # 返回包含文件夹和工具的结构
            return {
                "folders": [folder for folder in results if folder["resource_type"] == "folder"],
                "tools": [
                    {
                        **tool,
                        "input_field_list": json.loads(tool.get("input_field_list", "[]")),
                        "init_field_list": sanitize_init_field_list(json.loads(tool.get("init_field_list", "[]"))),
                    }
                    for tool in results
                    if tool["resource_type"] == "tool"
                ],
            }
