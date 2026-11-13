from langchain_core.messages import HumanMessage

from .llm import BaiLianChatModel


# Locally generated 128×128 black PNG. The save probe exercises a real visual-input request.
_TEST_IMAGE = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAAAAADmVT4XAAAAJklEQVR4"
               "nO3BAQEAAACCIP+vbkhAAQAAAAAAAAAAAAAAAAAAAO8GQIAAAfnHrWYAAAAASUVORK5CYII=")


class QwenVLChatModel(BaiLianChatModel):
    def check_auth(self, api_key=None):
        self.invoke([HumanMessage(content=[{"type": "text", "text": "Name this color."},
                                           {"type": "image_url", "image_url": {"url": _TEST_IMAGE}}])])
        return True
