"""Test component to nack the message when it is processed"""

from ...component_base import ComponentBase
from ....common import Message_NACK_Outcome


info = {
    "class_name": "GiveNackOutput",
    "description": ("A component that will nack the message when it is processed. "),
    "config_parameters": [
        {
            "name": "nack_outcome",
            "required": False,
            "description": "The outcome to use for the nack (FAILED or REJECTED)",
            "type": "string",
            "default": "REJECTED",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class GiveNackOutput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        nack_outcome = self.get_config("nack_outcome")
        if nack_outcome == "FAILED":
            message.call_negative_acknowledgements(Message_NACK_Outcome.FAILED)
        else:
            message.call_negative_acknowledgements(Message_NACK_Outcome.REJECTED)
        return data
