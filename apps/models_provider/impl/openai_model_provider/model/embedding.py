# coding=utf-8
"""
    @project: MaxKB
    @Author：虎
    @file： embedding.py
    @date：2024/7/12 17:44
    @desc:
"""
from typing import Dict, List

import openai

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.openai_model_provider.profiles import EMBEDDING_DIMENSIONS


class OpenAIEmbeddingModel(MaxKBBaseModel):
    model_name: str
    optional_params: dict

    def __init__(self, api_key, base_url, model_name: str, optional_params: dict):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url).embeddings
        self.model_name = model_name
        self.optional_params = optional_params

    def is_cache_model(self):
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = MaxKBBaseModel.filter_optional_params(model_kwargs)
        if model_name == "text-embedding-ada-002":
            optional_params.pop("dimensions", None)
        elif "dimensions" in optional_params and model_name in EMBEDDING_DIMENSIONS:
            raw = optional_params["dimensions"]
            if isinstance(raw, bool) or not isinstance(raw, (str, int)):
                raise ValueError(f"Invalid dimensions for {model_name}: {raw}")
            dimensions = int(raw)
            if not 1 <= dimensions <= EMBEDDING_DIMENSIONS[model_name]:
                raise ValueError(f"Invalid dimensions for {model_name}: {dimensions}")
            optional_params["dimensions"] = dimensions
        return OpenAIEmbeddingModel(
            api_key=model_credential.get('api_key'),
            model_name=model_name,
            base_url=model_credential.get('api_base'),
            optional_params=optional_params
        )

    def embed_query(self, text: str):
        res = self.embed_documents([text])
        return res[0]

    def embed_documents(
            self, texts: List[str], chunk_size: int | None = None
    ) -> List[List[float]]:
        # Even at 8192 tokens per input a batch of 32 is below the 300K request limit.
        batch_size = min(chunk_size, 32) if chunk_size is not None else 32
        if batch_size < 1:
            raise ValueError("chunk_size must be positive")
        vectors = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            res = self.client.create(
                input=batch, model=self.model_name, encoding_format="float",
                **self.optional_params
            )
            ordered = sorted(res.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError("OpenAI returned an incomplete embedding batch")
            vectors.extend(item.embedding for item in ordered)
        return vectors
