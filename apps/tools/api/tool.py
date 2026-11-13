# coding=utf-8
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

from common.mixins.api_mixin import APIMixin
from common.result import ResultSerializer, DefaultResultSerializer
from knowledge.serializers.common import BatchSerializer, BatchMoveSerializer
from tools.serializers.tool import ToolModelSerializer, ToolCreateRequest, ToolDebugRequest, ToolEditRequest, \
    PylintInstance, AddInternalToolRequest, StoreInstallRequest


class ToolCreateResponse(ResultSerializer):
    def get_data(self):
        return ToolModelSerializer()


class ToolCreateAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            )
        ]

    @staticmethod
    def get_request():
        return ToolCreateRequest

    @staticmethod
    def get_response():
        return ToolCreateResponse


class ToolReadAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="工具id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            )
        ]

    @staticmethod
    def get_response():
        return ToolCreateResponse


class ToolEditAPI(ToolReadAPI):

    @staticmethod
    def get_request():
        return ToolEditRequest


class ToolDeleteAPI(ToolReadAPI):
    @staticmethod
    def get_response():
        return DefaultResultSerializer


class ToolTreeReadAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="folder_id",
                description="文件夹id",
                type=OpenApiTypes.STR,
                location='query',
                required=False,
            )
        ]


class ToolDebugApi(APIMixin):
    @staticmethod
    def get_request():
        return ToolDebugRequest

    @staticmethod
    def get_response():
        return DefaultResultSerializer


class ToolExportAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="工具id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            )
        ]

    @staticmethod
    def get_response():
        return DefaultResultSerializer


class ToolImportAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),

        ]

    @staticmethod
    def get_request():
        return {
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary'  # Tells Swagger it's a file
                    }
                }
            }
        }

    @staticmethod
    def get_response():
        return DefaultResultSerializer


class ToolPageAPI(ToolReadAPI):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="current_page",
                description="当前页码",
                type=OpenApiTypes.INT,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="page_size",
                description="每页大小",
                type=OpenApiTypes.INT,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="folder_id",
                description="文件夹id",
                type=OpenApiTypes.STR,
                location='query',
                required=True,
            ),
            OpenApiParameter(
                name="user_id",
                description="创建者id",
                type=OpenApiTypes.STR,
                location='query',
                required=False,
            ),
            OpenApiParameter(
                name="scope",
                description="工具类型",
                type=OpenApiTypes.STR,
                enum=["SHARED", "WORKSPACE"],
                location='query',
                required=True,
            ),
            OpenApiParameter(
                name="name",
                description="工具名称",
                type=OpenApiTypes.STR,
                location='query',
                required=False,
            ),
        ]


class PylintAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),

        ]

    @staticmethod
    def get_request():
        return PylintInstance


class EditIconAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="工具id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
        ]

    @staticmethod
    def get_request():
        return {
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'icon': {
                        'type': 'string',
                        'format': 'binary'  # Tells Swagger it's a file
                    }
                }
            }
        }

    @staticmethod
    def get_response():
        return DefaultResultSerializer


class GetInternalToolAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="name",
                description="工具名称",
                type=OpenApiTypes.STR,
                location='query',
                required=False,
            )
        ]

    @staticmethod
    def get_response():
        return DefaultResultSerializer()


class AddInternalToolAPI(APIMixin):
    @staticmethod
    def get_request():
        return AddInternalToolRequest

    @staticmethod
    def get_response():
        return DefaultResultSerializer

    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="工具id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
        ]

store_template_parameter = OpenApiParameter(
    "tool_id", OpenApiTypes.STR, OpenApiParameter.PATH, required=True,
    description="广场目录中的工具 ID，例如 tool-timestamp。",
)
store_error_schema = {
    "type": "object",
    "required": ["code", "message", "data"],
    "properties": {
        "code": {"type": "integer"}, "message": {"type": "string"}, "data": {"nullable": True},
    },
}
store_errors = {
    400: OpenApiResponse(store_error_schema, "不支持的版本或无效的包。"),
    401: OpenApiResponse(store_error_schema, "请登录控制台。"),
    404: OpenApiResponse(store_error_schema, "工具或目标资源不存在。"),
    502: OpenApiResponse(store_error_schema, "上游目录或文件暂不可用。"),
}
store_write_responses = {
    **store_errors,
    200: ToolCreateResponse,
    403: OpenApiResponse(store_error_schema, "当前用户没有操作权限。"),
    409: OpenApiResponse(store_error_schema, "目标文件夹中已有同名工具，或工具被同时更新。"),
}


class AddStoreToolAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [*ToolCreateAPI.get_parameters(), store_template_parameter]

    @staticmethod
    def get_request():
        return StoreInstallRequest


class DownloadStoreToolAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            store_template_parameter,
            OpenApiParameter("version", OpenApiTypes.STR, OpenApiParameter.QUERY,
                             description="目录中发布的版本号。省略时下载目录当前版本。"),
        ]

    @staticmethod
    def get_response():
        return {**store_errors, (200, "application/octet-stream"): OpenApiTypes.BINARY}


class UpdateStoreToolAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            *ToolCreateAPI.get_parameters(),
            OpenApiParameter("tool_id", OpenApiTypes.UUID, OpenApiParameter.PATH, required=True,
                             description="已安装在当前工作空间中的工具 UUID。"),
        ]

    @staticmethod
    def get_request():
        return {
            "application/json": {
                "type": "object",
                "properties": {
                    "version": {"type": "string", "maxLength": 64, "description": "省略时使用目录当前版本。"},
                    "download_url": {
                        "type": "string", "maxLength": 2048, "deprecated": True,
                        "description": "兼容旧客户端，必须与该工具在可信目录的对应发布地址相符。",
                    },
                },
            },
        }


class ToolBatchOperateAPI(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            )
        ]

    @staticmethod
    def get_request():
        return BatchSerializer

    @staticmethod
    def get_move_request():
        return BatchMoveSerializer


