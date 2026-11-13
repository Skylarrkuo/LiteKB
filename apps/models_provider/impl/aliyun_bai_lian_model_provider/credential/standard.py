from django.utils.translation import gettext_lazy as _
from langchain_core.documents import Document

from common.forms import BaseForm
from common.exception.app_exception import AppApiException
from models_provider.base_model_provider import BaseModelCredential, ValidCode
from ..transport import check_catalog


class ModelCredential(BaseForm, BaseModelCredential):
    key_field = "api_key"

    def encryption_dict(self, model):
        return {**model, self.key_field: self.encryption(model.get(self.key_field, ""))}

    def is_valid(self, model_type, model_name, model_credential, model_params, provider, raise_exception=False):
        key = (model_credential or {}).get(self.key_field)
        try:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Missing API key")
            model = provider.get_model(model_type, model_name, model_credential, **(model_params or {}))
            if model_type == "LLM":
                model.invoke("Hello")
            elif model_type == "IMAGE":
                model.check_auth()
            elif model_type == "EMBEDDING":
                model.embed_query("Hello")
            elif model_type == "RERANKER":
                model.compress_documents([Document(page_content="Hello")], "Hello")
            else:
                check_catalog(model_credential.get("api_base") or model_credential.get("api_url"), key, model_name)
            return True
        except Exception as exc:
            if raise_exception:
                # SDK exceptions can contain request data. Never include keys or payloads in an API response.
                status = getattr(exc, "status_code", None)
                detail = type(exc).__name__
                if isinstance(exc, ValueError) and (not key or str(key) not in str(exc)):
                    detail = str(exc)
                raise AppApiException(ValidCode.valid_error.value, f"{_('Verification failed')}: {status or detail}") from exc
            return False
