from django.utils.translation import gettext_lazy as _
from common import forms
from ..parameters import fields_form, menu, number, switch
from ..transport import NATIVE
from .standard import ModelCredential


class MediaCredential(ModelCredential):
    api_base = forms.TextInputField(_("API URL"), required=True, default_value=NATIVE)
    api_key = forms.PasswordInputField(_("API Key"), required=True)

    def __init__(self, kind):
        self.kind = kind

    def get_model_params_setting_form(self, name):
        if self.kind == "TTI":
            fields = {"size": menu("Image dimensions (pixels)", ("1024*1024", "1536*1024", "1024*1536", "2048*2048"), "1024*1024"),
                      "n": number("Images per request", 1, 6, 1), "seed": number("Random seed", 0, 2147483647),
                      "prompt_extend": switch("Expand prompt", True), "watermark": switch("Watermark")}
        elif self.kind in ("TTV", "ITV"):
            fields = {"resolution": menu("Resolution", ("720P", "1080P"), "720P"),
                      "duration": number("Duration (seconds)", 2, 30 if name.startswith("wan3.0") else 15, 5),
                      "prompt_extend": switch("Expand prompt", True)}
            if self.kind == "TTV":
                fields["ratio"] = menu("Aspect ratio", ("16:9", "9:16", "1:1", "4:3", "3:4"), "16:9")
        elif self.kind == "TTS" and name.startswith("qwen-audio-"):
            voice = {"qwen-audio-3.0-tts-plus": "longanlingxin", "qwen-audio-3.0-tts-flash": "longanhuan_v3.6",
                     "qwen-audio-3.1-tts-plus": "longanlingxin_v3.1", "qwen-audio-3.1-tts-flash": "longanhuan_v3.1"}[name]
            fields = {"voice": forms.TextInputField("Voice ID", required=True, default_value=voice),
                      "format": menu("Audio format", ("mp3", "wav"), "mp3"),
                      "sample_rate": menu("Sample rate (Hz)", (8000, 12000, 16000, 22050, 24000, 44100, 48000), 24000),
                      "rate": number("Speed", .5, 2, None, .1), "volume": number("Volume", 0, 100),
                      "pitch": number("Pitch", .5, 2, None, .1),
                      "instruction": forms.TextInputField("Speaking instructions", required=False)}
        elif self.kind == "TTS":
            fields = {"voice": menu("Voice", ("Cherry", "Serena", "Ethan", "Chelsie"), "Cherry"),
                      "language_type": menu("Language", ("Auto", "Chinese", "English"), "Auto")}
            if "instruct" in name:
                fields["instructions"] = forms.TextInputField("Speaking instructions")
        elif self.kind == "STT" and name.startswith("qwen3-asr"):
            fields = {"enable_itn": switch("Normalize numbers and punctuation"),
                      "language": forms.TextInputField("Language code", required=False)}
        elif self.kind == "STT" and name.startswith("qwen-audio-3."):
            fields = {"sample_rate": menu("Input sample rate (Hz)", ("8000", "16000", "24000", "48000")),
                      "vocabulary_id": forms.TextInputField("Vocabulary ID", required=False)}
            if name.startswith("qwen-audio-3.1"):
                fields["keep_dialect"] = switch("Preserve dialect")
        else:
            fields = {}
        return fields_form(fields)
