from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_tti import BaseTextToImage
from ..transport import check_catalog, endpoint, generate_async, request


class QwenTextToImageModel(MaxKBBaseModel, BaseTextToImage):
    api_key: str
    model_name: str
    params: dict
    api_base: str

    @staticmethod
    def is_cache_model():
        return False

    @classmethod
    def new_instance(cls, model_type, model_name, model_credential, **model_kwargs):
        params = {k: v for k, v in cls.filter_optional_params(model_kwargs).items() if v is not None and v != ""}
        return cls(api_key=model_credential["api_key"], api_base=endpoint(model_credential.get("api_base")),
                   model_name=model_name, params=params)

    def check_auth(self):
        check_catalog(self.api_base, self.api_key, self.model_name)
        return True

    def generate_image(self, prompt, negative_prompt=None):
        params = dict(self.params)
        if self.model_name.startswith(("wanx", "wan2.1", "wan2.2", "wan2.5", "qwen-image-plus")):
            inputs = {"prompt": prompt}
            if negative_prompt:
                inputs["negative_prompt"] = negative_prompt
            output = generate_async(self.api_base, self.api_key, "services/aigc/text2image/image-synthesis",
                                    {"model": self.model_name, "input": inputs, "parameters": params})
            return [row["url"] for row in output["results"]]
        params.pop("style", None)  # Wanx presets could previously be saved on Qwen models.
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        path = ("services/aigc/image-generation/generation" if self.model_name.startswith(("wan2.6", "wan2.7", "z-image"))
                else "services/aigc/multimodal-generation/generation")
        output = request(self.api_base, self.api_key, path, {"model": self.model_name, "input": {
            "messages": [{"role": "user", "content": [{"text": prompt}]}]}, "parameters": params})
        images = [item["image"] for c in output["choices"] for item in c["message"]["content"] if "image" in item]
        if not images:
            raise ValueError("DashScope returned no generated image")
        return images
