from django.utils.translation import gettext_lazy as _
from common import forms
from ..parameters import fields_form, number
from ..transport import NATIVE
from .standard import ModelCredential


class AliyunBaiLianRerankerCredential(ModelCredential):
    key_field = "dashscope_api_key"
    api_base = forms.TextInputField(_("API URL"), required=True, default_value=NATIVE)
    dashscope_api_key = forms.PasswordInputField(_("API Key"), required=True)

    def get_model_params_setting_form(self, model_name):
        fields = {"top_n": number("Top N", 1, 100, 3)}
        if model_name.startswith(("qwen3-rerank", "qwen3.7-text-rerank")):
            fields["instruct"] = forms.TextInputField(_("Ranking instructions"), required=False)
        return fields_form(fields)
