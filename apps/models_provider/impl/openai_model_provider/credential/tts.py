# coding=utf-8
from typing import Dict

from django.utils.translation import gettext

from common import forms
from common.exception.app_exception import AppApiException
from common.forms import BaseForm
from models_provider.base_model_provider import BaseModelCredential, ValidCode
from common.utils.logger import maxkb_logger
from models_provider.impl.openai_model_provider.profiles import choices, family

class OpenAITTSModelGeneralParams(BaseForm):
    voice = choices("Voice", ("alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"), "alloy")


class OpenAITTSModelCredential(BaseForm, BaseModelCredential):
    api_base = forms.TextInputField('API URL', required=True, default_value='https://api.openai.com/v1')
    api_key = forms.PasswordInputField('API Key', required=True)

    def is_valid(self, model_type: str, model_name, model_credential: Dict[str, object], model_params, provider,
                 raise_exception=False):
        model_type_list = provider.get_model_type_list()
        if not any(list(filter(lambda mt: mt.get('value') == model_type, model_type_list))):
            raise AppApiException(ValidCode.valid_error.value,
                                  gettext('{model_type} Model type is not supported').format(model_type=model_type))

        for key in ['api_base', 'api_key']:
            if key not in model_credential:
                if raise_exception:
                    raise AppApiException(ValidCode.valid_error.value, gettext('{key}  is required').format(key=key))
                else:
                    return False
        try:
            model = provider.get_model(model_type, model_name, model_credential, **model_params)
            model.check_auth()
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

    def get_model_params_setting_form(self, model_name):
        if family(model_name) == "gpt-4o-mini-tts":
            return InstructedSpeechParams()
        return OpenAITTSModelGeneralParams()


class InstructedSpeechParams(BaseForm):
    voice = choices("Voice", ("marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx",
                              "sage", "shimmer", "verse"), "marin")
    instructions = forms.TextInputField("Speaking instructions", required=False)
