from django.utils.translation import gettext_lazy as _
from common import forms
from ..parameters import chat_form
from ..transport import COMPAT
from .standard import ModelCredential


class BaiLianLLMModelCredential(ModelCredential):
    api_base = forms.TextInputField(_("API URL"), required=True, default_value=COMPAT)
    api_key = forms.PasswordInputField(_("API Key"), required=True)

    def get_model_params_setting_form(self, model_name):
        return chat_form(model_name)
