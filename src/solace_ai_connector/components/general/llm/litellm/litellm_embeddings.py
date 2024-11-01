"""LiteLLM embedding component"""

from .litellm_base import LiteLLMBase, litellm_info_base
from .....common.log import log

info = litellm_info_base.copy()
info.update(
    {
        "class_name": "LiteLLMEmbeddings",
        "description": "Embed text using a LiteLLM model",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                        "type": "array",
                        "description": "A single element or a list of elements to embed",
                    },
                },
                "required": ["messages"],
            },
        "output_schema": {
            "type": "object",
            "properties": {
                "embedding": {
                    "type": "array",
                    "description": (
                        "A list of floating point numbers representing the embedding. "
                        "Its length is the size of vector that the embedding model produces"
                    ),
                    "items": {"type": "float"},
                }
            },
            "required": ["embedding"],
        },
    }
)

class LiteLLMEmbeddings(LiteLLMBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        """invoke the embedding model"""
        items = data.get("items", [])

        response = self.router.embedding(model=self.load_balancer[0]["model_name"], 
                input=items)
        log.debug("Embedding response: %s", response)

        # Extract the embedding data from the response
        embedding_data = response['data'][0]['embedding']
        return {"embedding": embedding_data}