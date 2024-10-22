"""LiteLLM chat model component"""

from .litellm_base import LiteLLMChatModelBase, litellm_info_base

info = litellm_info_base.copy()
info["class_name"] = "LiteLLMChatModel"
info["description"] = "LiteLLM chat model component"

class LiteLLMChatModel(LiteLLMChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
