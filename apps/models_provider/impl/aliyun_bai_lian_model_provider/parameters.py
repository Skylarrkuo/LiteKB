from common import forms
from common.forms.switch_field import SwitchField


DIMENSIONS = {
    "text-embedding-v1": (), "text-embedding-v2": (),
    "text-embedding-v3": (1024, 768, 512, 256, 128, 64),
    "text-embedding-v4": (1024, 2048, 1536, 768, 512, 256, 128, 64),
    "qwen3.7-text-embedding": (1024, 2560, 2048, 1536, 768, 512, 256),
    "qwen3.7-text-embedding-flash": (1024, 768, 512, 256),
}

INSTRUCT_EMBEDDINGS = {"qwen3.7-text-embedding", "qwen3.7-text-embedding-flash", "text-embedding-v4"}


def menu(label, values, default=None):
    return forms.SingleSelect(label, text_field="label", value_field="value",
                              option_list=[{"label": str(v), "value": v} for v in values], default_value=default)


def number(label, low, high, default=None, step=1):
    return forms.SliderField(label, _min=low, _max=high, _step=step, precision=0 if step == 1 else 2,
                             default_value=default)


def switch(label, default=False):
    return SwitchField(label, default_value=default, attrs={"active-value": True, "inactive-value": False})


def fields_form(fields):
    # BaseForm discovers class-level fields. Each instance gets its own per-model fields and limits.
    return type("BailianModelParameters", (forms.BaseForm,), fields)()


def chat_form(name):
    recent = name.startswith(("qwen3.8", "qwen3.7", "qwen3.6", "qwen3.5"))
    fields = {
        "temperature": number("Temperature [0, 2)", 0, 1.99, .7, .01),
        "max_tokens": number("Maximum output tokens", 1, 65536 if recent else 8192, 4096),
        "top_p": number("Nucleus sampling (top_p)", .01, 1, None, .01),
        "top_k": number("Candidate tokens (top_k)", 0, 100),
        "seed": number("Random seed", 0, 2147483647),
    }
    if recent or name.startswith(("qwen3-vl", "qwen-plus", "qwen-flash")):
        if name not in ("qwen3.6-max-preview", "qwen3.7-max-preview"):
            fields["enable_thinking"] = menu("Thinking mode", (True, False))
        fields["thinking_budget"] = number("Maximum reasoning tokens", 1, 32768)
    return fields_form(fields)
