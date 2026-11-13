from openai import OpenAI

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_tti import BaseTextToImage
from ..profiles import IMAGE_MODELS, family


class OpenAITextToImage(MaxKBBaseModel, BaseTextToImage):
    api_base: str
    api_key: str
    model: str
    params: dict

    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential, **model_kwargs):
        options = MaxKBBaseModel.filter_optional_params(model_kwargs)
        model = family(model_name)
        if model in IMAGE_MODELS:
            options.setdefault("size", "1024x1024")
            # Old Studio image forms saved DALL·E values for all model IDs.
            options["quality"] = {"standard": "auto", "hd": "high"}.get(options.get("quality"), options.get("quality", "auto"))
            options.pop("response_format", None)  # GPT Image returns base64.
            complexity = options.pop("complexity", None)
            if complexity is not None and model.startswith("gpt-image-2.6-"):
                options["extra_body"] = {**(options.get("extra_body") or {}), "complexity": complexity}
            if model == "gpt-image-1.5":
                migrated_sizes = {"1024x1792": "1024x1536", "1792x1024": "1536x1024"}
                options["size"] = migrated_sizes.get(options["size"], options["size"])
        else:
            options.setdefault("size", "1024x1024")
            options.setdefault("quality", "standard")
        options.setdefault("n", 1)
        if model_name == "dall-e-3" and options["n"] != 1:
            raise ValueError("DALL·E 3 supports one image per request")
        return OpenAITextToImage(api_base=model_credential["api_base"], api_key=model_credential["api_key"],
                                 model=model_name, params=options)

    def check_auth(self):
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            client.models.retrieve(self.model)

    def generate_image(self, prompt, negative_prompt=None):
        with OpenAI(api_key=self.api_key, base_url=self.api_base) as client:
            result = client.images.generate(model=self.model, prompt=prompt, **self.params)
        return [image.url or image.b64_json for image in result.data if image.url or image.b64_json]
