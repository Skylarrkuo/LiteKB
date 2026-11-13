# coding=utf-8
"""
    @project: MaxKB
    @Author：虎
    @file： llm.py
    @date：2024/7/11 17:51
    @desc:
"""
from typing import Dict

from django.utils.translation import gettext_lazy as _, gettext
from langchain_core.messages import HumanMessage

from common import forms
from common.exception.app_exception import AppApiException
from common.forms import BaseForm, TooltipLabel
from models_provider.base_model_provider import BaseModelCredential, ValidCode
from common.utils.logger import maxkb_logger


class DeepSeekLLMModelParams(BaseForm):
    thinking_mode = forms.SingleSelect("Thinking", "value", "value",
                                       [{"value": v} for v in ("enabled", "disabled")], default_value="enabled")
    reasoning_effort = forms.SingleSelect("Reasoning effort", "value", "value",
                                          [{"value": v} for v in ("low", "high", "max")], default_value="high",
                                          relation_show_field_dict={"thinking_mode": ["enabled"]})
    temperature = forms.SliderField(_("Temperature"), 0, 2, 0.01, 2, default_value=1,
                                    relation_show_field_dict={"thinking_mode": ["disabled"]})
    top_p = None

    def __init__(self, model_name):
        flash = model_name.startswith(("deepseek-flash", "deepseek-v4-flash"))
        self.top_p = forms.SliderField("Top P", 0.95 if flash else 0, 1, 0.01, 2, default_value=1,
                                       relation_show_field_dict={"thinking_mode": ["enabled" if flash else "disabled"]})

    max_tokens = forms.SliderField(
        TooltipLabel(_('Output the maximum Tokens'),
                     _('Specify the maximum number of tokens that the model can generate')),
        required=True, default_value=8192,
        _min=1,
        _max=393216,
        _step=1,
        precision=0)


class DeepSeekLLMModelCredential(BaseForm, BaseModelCredential):

    def is_valid(self, model_type: str, model_name, model_credential: Dict[str, object], model_params, provider,
                 raise_exception=False):
        model_type_list = provider.get_model_type_list()
        if not any(list(filter(lambda mt: mt.get('value') == model_type, model_type_list))):
            raise AppApiException(ValidCode.valid_error.value,
                                  gettext('{model_type} Model type is not supported').format(model_type=model_type))

        for key in ['api_key', 'api_base']:
            if key not in model_credential:
                if raise_exception:
                    raise AppApiException(ValidCode.valid_error.value, gettext('{key}  is required').format(key=key))
                else:
                    return False
        try:
            model = provider.get_model(model_type, model_name, model_credential, **model_params)
            model.invoke([HumanMessage(content=gettext('Hello'))])
        except Exception as e:
            maxkb_logger.error(f'Exception: {e}', exc_info=True)
            if isinstance(e, AppApiException):
                raise e
            if raise_exception:
                raise AppApiException(ValidCode.valid_error.value,
                                      gettext(
                                          'Verification failed, please check whether the parameters are correct: {error}').format(
                                          error=str(e)))
            else:
                return False
        return True

    def encryption_dict(self, model: Dict[str, object]):
        return {**model, 'api_key': super().encryption(model.get('api_key', ''))}

    api_base = forms.TextInputField(_('API URL'), required=True,
                                    default_value='https://api.deepseek.com')
    api_key = forms.PasswordInputField('API Key', required=True)

    def get_model_params_setting_form(self, model_name):
        return DeepSeekLLMModelParams(model_name)
