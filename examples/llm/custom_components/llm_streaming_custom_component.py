# A simple pass-through component - what goes in comes out

import sys

sys.path.append("src")

from solace_ai_connector.components.component_base import ComponentBase


info = {
    "class_name": "LlmStreamingCustomComponent",
    "description": "Do a blocking LLM request/response",
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class LlmStreamingCustomComponent(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        data_iter = self.send_request_response_flow_message(
            "llm_streaming_request",
            message,
            data,
        )

        text = None
        for result_message, _result_data, is_last in data_iter():
            text = result_message.get_data("input.payload:chunk")
            if not text:
                text = result_message.get_data("input.payload:content") or "no response"
            if not is_last:
                self.output_streaming(result_message, {"chunk": text})

        return {"chunk": text}

    def output_streaming(self, message, data):
        return self.process_post_invoke(data, message)
