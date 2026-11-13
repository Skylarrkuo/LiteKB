from langchain_core.documents import BaseDocumentCompressor
from pydantic import SecretStr

from models_provider.base_model_provider import MaxKBBaseModel
from ..transport import endpoint, request


class AliyunBaiLianReranker(MaxKBBaseModel, BaseDocumentCompressor):
    model: str
    api_key: SecretStr
    base_url: str
    top_n: int = 3
    instruct: str | None = None

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential, **model_kwargs):
        return AliyunBaiLianReranker(model=model_name, api_key=model_credential.get("dashscope_api_key")
                                    or model_credential.get("api_key"), base_url=endpoint(model_credential.get("api_base")),
                                    top_n=model_kwargs.get("top_n", 3), instruct=model_kwargs.get("instruct") or None)

    def compress_documents(self, documents, query, callbacks=None):
        if not documents:
            return []
        params = {"top_n": min(self.top_n, len(documents)), "return_documents": False}
        if self.instruct and self.model.startswith(("qwen3-rerank", "qwen3.7-text-rerank")):
            params["instruct"] = self.instruct
        inputs = {"query": query, "documents": [doc.page_content for doc in documents]}
        if self.model == "qwen3-vl-rerank":
            inputs = {"query": {"text": query}, "documents": [{"text": doc.page_content} for doc in documents]}
        output = request(self.base_url, self.api_key.get_secret_value(), "services/rerank/text-rerank/text-rerank",
                         {"model": self.model, "input": inputs, "parameters": params})
        ranked = []
        for row in output["results"]:
            index = row["index"]
            if not isinstance(index, int) or not 0 <= index < len(documents):
                raise ValueError("DashScope returned an invalid document index")
            doc = documents[index]
            ranked.append(doc.model_copy(update={"metadata": {**doc.metadata, "relevance_score": row["relevance_score"]}}))
        return ranked
