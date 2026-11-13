#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project ：MaxKB
@File    ：deepseek_model_provider.py
@Author  ：Brian Yang
@Date    ：5/12/24 7:40 AM
"""

import os

from common.utils.common import get_file_content
from models_provider.base_model_provider import (
    IModelProvider,
    ModelProvideInfo,
    ModelInfo,
    ModelTypeConst,
    ModelInfoManage,
)
from models_provider.impl.deepseek_model_provider.credential.llm import DeepSeekLLMModelCredential
from models_provider.impl.deepseek_model_provider.model.llm import DeepSeekChatModel
from maxkb.conf import PROJECT_DIR

deepseek_llm_model_credential = DeepSeekLLMModelCredential()
docs_url = "https://api-docs.deepseek.com/quick_start/pricing/"
deepseek_llm_list = [
    ModelInfo(name, desc, kind, deepseek_llm_model_credential, DeepSeekChatModel, docs_url=docs_url)
    for kind, name, desc in [
        (ModelTypeConst.LLM, "deepseek-flash", "V4.1 Flash · 1M context · text, vision and tools"),
        (ModelTypeConst.LLM, "deepseek-v4-pro", "V4 Pro · 1M context · text and tools"),
        (ModelTypeConst.IMAGE, "deepseek-flash", "V4.1 Flash · image understanding"),
    ]
]

model_info_manage = (
    ModelInfoManage.builder()
    .append_model_info_list(deepseek_llm_list)
    .append_default_model_info(deepseek_llm_list[0])
    .append_default_model_info(deepseek_llm_list[-1])
    .build()
)


class DeepSeekModelProvider(IModelProvider):
    def get_model_info_manage(self):
        return model_info_manage

    def get_model_provide_info(self):
        return ModelProvideInfo(
            provider="model_deepseek_provider",
            name="DeepSeek",
            icon=get_file_content(
                os.path.join(
                    PROJECT_DIR,
                    "apps",
                    "models_provider",
                    "impl",
                    "deepseek_model_provider",
                    "icon",
                    "deepseek_icon_svg",
                )
            ),
        )
