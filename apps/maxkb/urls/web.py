"""
URL configuration for maxkb project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os
from html import escape
from pathlib import Path

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, re_path, include
from django.views import static
from django.views.decorators.http import require_GET
from rest_framework import status

from chat.urls import urlpatterns as chat_urlpatterns
from common.init.init_doc import init_doc
from common.result import Result
from maxkb import settings
from maxkb.const import CONFIG
from maxkb.health import ready
from maxkb.capabilities import capabilities_view

admin_api_prefix = CONFIG.get_admin_path()[1:] + '/api/'
admin_ui_prefix = CONFIG.get_admin_path()
chat_api_prefix = CONFIG.get_chat_path()[1:] + '/api/'
chat_ui_prefix = CONFIG.get_chat_path()
urlpatterns = [
    path("health/ready", ready, name="ready"),
    path(admin_api_prefix, include("users.urls")),
    path(admin_api_prefix, include("tools.urls")),
    path(admin_api_prefix, include("models_provider.urls")),
    path(admin_api_prefix, include("folders.urls")),
    path(admin_api_prefix, include("knowledge.urls")),
    path(admin_api_prefix, include("system_manage.urls")),
    path(admin_api_prefix, include("application.urls")),
    path("v1/", include("litekb_api.urls")),
    path(admin_api_prefix, include("litekb_api.admin_urls")),
    path(admin_api_prefix + "capabilities", require_GET(capabilities_view)),
    path(admin_api_prefix, include("oss.urls", namespace="admin_oss")),
    path(admin_api_prefix, include("homepage.urls")),
    path(chat_api_prefix, include("oss.urls", namespace="chat_oss")),
    path(chat_api_prefix, include("chat.urls")),
    path(f'{admin_ui_prefix[1:]}/', include('oss.retrieval_urls', namespace='admin_oss_retrieval')),
]
init_doc(urlpatterns, chat_urlpatterns)


def admin_index(request):
    index_path = Path(settings.STATIC_ROOT) / 'admin' / 'index.html'
    if not index_path.is_file():
        return HttpResponse("页面不存在", status=404)
    content = index_path.read_text(encoding='utf-8').replace(
        'href="/admin/"', f'href="{escape(admin_ui_prefix.rstrip("/"))}/"'
    ).replace('data-chat-prefix="/chat"', f'data-chat-prefix="{escape(chat_ui_prefix)}"')
    return HttpResponse(content)


def pro():
    urlpatterns.append(
        re_path(rf'^{CONFIG.get_admin_path()[1:]}/api-doc/(?P<path>.*)$', static.serve,
                {'document_root': os.path.join(settings.STATIC_ROOT, "drf_spectacular_sidecar")}, name='doc'),
    )

    urlpatterns.append(
        re_path(rf'^{CONFIG.get_chat_path()[1:]}/api-doc/(?P<path>.*)$', static.serve,
                {'document_root': os.path.join(settings.STATIC_ROOT, "drf_spectacular_sidecar")}, name='doc_chat'),
    )
    # 暴露ui静态资源
    urlpatterns.extend([
        path(f'{admin_ui_prefix[1:]}/', admin_index),
        path(f'{admin_ui_prefix[1:]}/index.html', admin_index),
    ])
    urlpatterns.append(
        re_path(rf"^{CONFIG.get_admin_path()[1:]}/(?P<path>.*)$", static.serve,
                {'document_root': os.path.join(settings.STATIC_ROOT, "admin")},
                name='admin'),
    )


if not settings.DEBUG:
    pro()


def get_all_files(directory):
    base_path = Path(directory)
    file_paths = [
        '/' + str(file.relative_to(base_path)).replace('\\', '/')
        for file in base_path.rglob('*')
        if file.is_file()
    ]
    return sorted(file_paths, key=len, reverse=True)


static_dict = {
    admin_ui_prefix: get_all_files(Path(settings.STATIC_ROOT) / 'admin')
}


def page_not_found(request, exception):
    """
    页面不存在处理
    """
    if request.path.startswith(admin_ui_prefix + '/api/'):
        return Result(response_status=status.HTTP_404_NOT_FOUND, code=404, message="HTTP_404_NOT_FOUND")
    if request.path.startswith(chat_ui_prefix + '/api/'):
        return Result(response_status=status.HTTP_404_NOT_FOUND, code=404, message="HTTP_404_NOT_FOUND")
    if request.path.startswith('/v1/') or request.path == chat_ui_prefix or request.path.startswith(chat_ui_prefix + '/'):
        return Result(response_status=status.HTTP_404_NOT_FOUND, code=404, message="HTTP_404_NOT_FOUND")
    if request.path.startswith(admin_ui_prefix):
        in_ = [url for url in static_dict.get(admin_ui_prefix) if request.path.endswith(url)]
        if len(in_) > 0:
            a = admin_ui_prefix + in_[0]
            return HttpResponseRedirect(a)
        return admin_index(request)
    else:
        return HttpResponseRedirect(admin_ui_prefix + '/')


handler404 = page_not_found
