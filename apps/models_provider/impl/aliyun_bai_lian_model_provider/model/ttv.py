from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.base_ttv import BaseGenerationVideo
from ..transport import check_catalog, endpoint, generate_async


class GenerationVideoModel(MaxKBBaseModel, BaseGenerationVideo):
    api_key: str
    api_base: str
    model_name: str
    params: dict

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

    def generate_video(self, prompt, negative_prompt=None, first_frame_url=None, last_frame_url=None, **kwargs):
        inputs = {"prompt": prompt}
        params = dict(self.params)
        if negative_prompt and not self.model_name.startswith("wan3.0"):
            inputs["negative_prompt"] = negative_prompt
        if self.model_name.startswith(("wan2.7", "wan3.0")):
            if first_frame_url or last_frame_url:
                inputs["media"] = [{"type": kind, "url": url} for kind, url in (
                    ("first_frame", first_frame_url), ("last_frame", last_frame_url)) if url]
        elif "kf2v" in self.model_name:
            inputs.update(first_frame_url=first_frame_url, last_frame_url=last_frame_url)
        elif first_frame_url:
            inputs["img_url"] = first_frame_url
        output = generate_async(self.api_base, self.api_key, "services/aigc/video-generation/video-synthesis",
                                {"model": self.model_name, "input": inputs, "parameters": params})
        return output["video_url"]
