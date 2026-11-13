"""OpenAI model settings shared by the catalog, forms and request adapters."""

import re

from common import forms
from common.forms import BaseForm


# The first entry is the default recommended for LiteKB's RAG workflow.
# Each tuple contains the initial Studio setting and the API's supported choices.
_EFFORTS = ("low", "medium", "high", "xhigh", "max")
REASONING = {
    "gpt-6.1-sol": ("medium", _EFFORTS),
    "gpt-6.1-terra": ("medium", ("none", *_EFFORTS)),
    "gpt-6-luna": ("medium", ("none", *_EFFORTS)),
    "gpt-6-astra": ("medium", _EFFORTS),
    "gpt-6-sol": ("medium", ("none", *_EFFORTS)),
    "gpt-5.6-terra": ("medium", ("none", *_EFFORTS)),
    "gpt-5.6-sol": ("medium", ("none", *_EFFORTS)),
    "gpt-5.6-luna": ("medium", ("none", *_EFFORTS)),
    "gpt-5.5": ("medium", ("none", "low", "medium", "high", "xhigh")),
    "gpt-5.4": ("none", ("none", "low", "medium", "high", "xhigh")),
    "gpt-5.4-mini": ("none", ("none", "low", "medium", "high", "xhigh")),
    "gpt-5.4-nano": ("none", ("none", "low", "medium", "high", "xhigh")),
}
IMAGE_MODELS = (
    "gpt-image-2.6-flare", "gpt-image-2.6-sunburst",
    "gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2", "gpt-image-1.5",
)
EMBEDDING_DIMENSIONS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}


def family(model_name):
    name = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_name or "")
    return "gpt-5.6-sol" if name == "gpt-5.6" else name


def choices(label, values, default):
    return forms.SingleSelect(label, text_field="label", value_field="value", required=True, default_value=default,
                              option_list=[{"label": str(value), "value": value} for value in values])


class ReasoningParams(BaseForm):
    reasoning_effort = None
    max_tokens = forms.SliderField("Max output tokens", required=True, default_value=8192, _min=16, _max=128000,
                                   _step=1, precision=0)

    def __init__(self, model):
        default, efforts = REASONING[family(model)]
        self.reasoning_effort = choices("Reasoning effort", efforts, default)


def chat_options(model, params):
    profile = REASONING.get(family(model))
    if profile is None:
        return params
    default, supported = profile
    reasoning = params.get("reasoning") or {}
    effort = params.get("reasoning_effort") or reasoning.get("effort") or default
    if effort not in supported:
        raise ValueError(f"{model} reasoning_effort must be one of {', '.join(supported)}")
    options = dict(params, use_responses_api=True, output_version="responses/v1", reasoning_effort=effort)
    options.setdefault("store", False)
    if effort != "none":
        for key in ("temperature", "top_p", "logprobs", "top_logprobs"):
            options.pop(key, None)
    return options
