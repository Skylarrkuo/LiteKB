from django.utils.translation import gettext_lazy as _
from common import forms
from ..parameters import DIMENSIONS, INSTRUCT_EMBEDDINGS, fields_form, menu, switch
from ..transport import COMPAT
from .standard import ModelCredential


class AliyunBaiLianEmbeddingCredential(ModelCredential):
    key_field = "dashscope_api_key"
    api_base = forms.TextInputField(_("API URL"), required=True, default_value=COMPAT)
    dashscope_api_key = forms.PasswordInputField(_("API Key"), required=True)

    def get_model_params_setting_form(self, model_name):
        values = DIMENSIONS.get(model_name, ())
        fields = {"dimensions": menu(_("Dimensions"), values, values[0])} if values else {}
        if model_name in DIMENSIONS:
            fields["use_query_type"] = switch(_("Use DashScope query embeddings"))
        if model_name in INSTRUCT_EMBEDDINGS:
            fields["instruct"] = forms.TextInputField(_("Query retrieval instruction (English)"), required=False)
        return fields_form(fields)
