# coding=utf-8
"""
    @project: MaxKB
    @Author：虎虎
    @file： web.py
    @date：2025/11/5 15:14
    @desc:
"""
import csv
import os
from ctypes import c_long, sizeof

from django.core.wsgi import get_wsgi_application


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'maxkb.settings')
csv.field_size_limit((1 << (sizeof(c_long) * 8 - 1)) - 1)
application = get_wsgi_application()


def post_handler():
    from common.database_model_manage.database_model_manage import DatabaseModelManage
    from common.init import init_template
    DatabaseModelManage.init()
    init_template.run()


# 启动后处理函数
post_handler()
