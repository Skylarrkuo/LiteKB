from openai import OpenAI

from models_provider.base_model_provider import MaxKBBaseModel
from ..parameters import DIMENSIONS, INSTRUCT_EMBEDDINGS
from ..transport import endpoint, request


class AliyunBaiLianEmbedding(MaxKBBaseModel):
    def __init__(self, api_key, model_name, api_base, optional_params):
        self.model_name, self.api_key, self.base = model_name, api_key, api_base
        self.params = {k: v for k, v in optional_params.items() if v is not None and v != ""}
        self.use_query_type = self.params.pop("use_query_type", False)
        self.instruct = self.params.pop("instruct", None)
        dims = DIMENSIONS.get(model_name)
        if dims == ():
            # Old forms incorrectly saved dimensions for fixed-size v1/v2 models.
            self.params.pop("dimensions", None)
        elif "dimensions" in self.params:
            dimension = int(self.params["dimensions"])
            if dims and dimension not in dims:
                raise ValueError(f"Unsupported dimension for {model_name}: {dimension}")
            self.params["dimensions"] = dimension
        self.client = OpenAI(api_key=api_key, base_url=endpoint(api_base, compatible=True)).embeddings

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential, **model_kwargs):
        return AliyunBaiLianEmbedding(model_credential.get("dashscope_api_key") or model_credential.get("api_key"),
                                      model_name, model_credential.get("api_base"),
                                      MaxKBBaseModel.filter_optional_params(model_kwargs))

    def embed_query(self, text):
        if self.model_name in DIMENSIONS and (self.use_query_type or self.instruct):
            params = {"text_type": "query"}
            if "dimensions" in self.params:
                params["dimension"] = self.params["dimensions"]
            if self.instruct and self.model_name in INSTRUCT_EMBEDDINGS:
                params["instruct"] = self.instruct
            output = request(endpoint(self.base), self.api_key, "services/embeddings/text-embedding/text-embedding",
                             {"model": self.model_name, "input": {"texts": [text]}, "parameters": params})
            return output["embeddings"][0]["embedding"]
        return self.embed_documents([text])[0]

    def embed_documents(self, texts, chunk_size=None):
        if not texts:
            return []
        if any(token in self.model_name for token in ("vl-embedding", "embedding-vision", "multimodal")):
            result = []
            for text in texts:
                output = request(endpoint(self.base), self.api_key, "services/embeddings/multimodal-embedding/multimodal-embedding",
                                 {"model": self.model_name, "input": {"contents": [{"text": text}]},
                                  "parameters": dict(self.params)})
                result.append(output["embeddings"][0]["embedding"])
            return result
        limit = 25 if self.model_name in ("text-embedding-v1", "text-embedding-v2") else 10
        batch = max(1, min(chunk_size or limit, limit))
        result = []
        for start in range(0, len(texts), batch):
            group = texts[start:start + batch]
            response = self.client.create(input=group, model=self.model_name, encoding_format="float", **self.params)
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(group))):
                raise ValueError("Incomplete or duplicate embedding indices")
            result.extend(item.embedding for item in ordered)
        return result
