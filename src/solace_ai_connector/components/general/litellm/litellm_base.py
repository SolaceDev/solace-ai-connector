"""Base class for LiteLLM chat models"""

import uuid
import time
import asyncio
import litellm

from ...component_base import ComponentBase
from ....common.message import Message
from ....common.log import log

litellm_info_base = {
    "class_name": "LiteLLMChatModelBase",
    "description": "Base class for LiteLLM chat models",
    "config_parameters": [
        {
            "name": "action",
            "required": True,
            "description": "The action to perform (e.g., 'inference', 'embedding')",
            "default": "inference",
        },
        {
            "name": "load_balancer",
            "required": False,
            "description": (
                "Add a list of models to load balancer."
            ),
            "default": "",
        },
        {
            "name": "litellm_params",
            "required": False,
            "description": (
                "LiteLLM model parameters. The model, api_key and base_url are mandatory."
                "find more models at https://docs.litellm.ai/docs/providers"
                "find more parameters at https://docs.litellm.ai/docs/completion/input"
            ),
            "default": "",
        },
        {
            "name": "temperature",
            "required": False,
            "description": "Sampling temperature to use",
            "default": 0.7,
        },
        {
            "name": "stream_to_flow",
            "required": False,
            "description": (
                "Name the flow to stream the output to - this must be configured for "
                "llm_mode='stream'. This is mutually exclusive with stream_to_next_component."
            ),
            "default": "",
        },
        {
            "name": "stream_to_next_component",
            "required": False,
            "description": (
                "Whether to stream the output to the next component in the flow. "
                "This is mutually exclusive with stream_to_flow."
            ),
            "default": False,
        },
        {
            "name": "llm_mode",
            "required": False,
            "description": (
                "The mode for streaming results: 'sync' or 'stream'. 'stream' "
                "will just stream the results to the named flow. 'none' will "
                "wait for the full response."
            ),
            "default": "none",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result. Default: 15.",
            "default": 15,
        },
        {
            "name": "set_response_uuid_in_user_properties",
            "required": False,
            "description": (
                "Whether to set the response_uuid in the user_properties of the "
                "input_message. This will allow other components to correlate "
                "streaming chunks with the full response."
            ),
            "default": False,
            "type": "boolean",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant"],
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
        },
        "required": ["messages"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The generated response from the model",
            },
            "chunk": {
                "type": "string",
                "description": "The current chunk of the response",
            },
            "response_uuid": {
                "type": "string",
                "description": "The UUID of the response",
            },
            "first_chunk": {
                "type": "boolean",
                "description": "Whether this is the first chunk of the response",
            },
            "last_chunk": {
                "type": "boolean",
                "description": "Whether this is the last chunk of the response",
            },
            "streaming": {
                "type": "boolean",
                "description": "Whether this is a streaming response",
            },
        },
        "required": ["content"],
    },
}


class LiteLLMChatModelBase(ComponentBase):
    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.init()
        self.init_load_balancer()

    def init(self):
        litellm.suppress_debug_info = True
        self.action = self.get_config("action")
        self.load_balancer = self.get_config("load_balancer")
        self.litellm_params = self.get_config("litellm_params")
        self.stream_to_flow = self.get_config("stream_to_flow")
        self.stream_to_next_component = self.get_config("stream_to_next_component")
        self.llm_mode = self.get_config("llm_mode")
        self.stream_batch_size = self.get_config("stream_batch_size")
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties"
        )
        if self.stream_to_flow and self.stream_to_next_component:
            raise ValueError(
                "stream_to_flow and stream_to_next_component are mutually exclusive"
            )
        self.enabled_load_balancer = True if self.load_balancer is not None else False
        self.router = None

    def init_load_balancer(self):
        """initialize a load balancer"""
        if self.enabled_load_balancer:
            try:
                self.router = litellm.Router(model_list=self.load_balancer)
                log.debug("Load balancer initialized with models: %s", self.load_balancer)
            except Exception as e:
                log.error("Error initializing load balancer: %s", e)
                self.enabled_load_balancer = False
                log.warning("Continued without load balancer")
    
    async def load_balance(self, messages):
        """load balance the messages"""
        response = await self.router.acompletion(model=self.load_balancer[0]["model_name"], 
                messages=messages)
        log.debug("Load balancer response: %s", response)
        return response

    def invoke(self, message, data):
        """invoke the model"""
        messages = data.get("messages", [])

        if self.action == "inference":
            if self.llm_mode == "stream":
                return self.invoke_stream(message, messages)
            else:
                return self.invoke_non_stream(messages)
        elif self.action == "embedding":
            return self.invoke_embedding(messages)
        else:
            raise ValueError(f"Unsupported action: {self.action}") 

    def invoke_embedding(self, messages):
        """invoke the embedding model"""
        response = litellm.embedding(input=messages[0]["content"], 
                                        ** self.litellm_params
                                        )
        # Extract the embedding data from the response
        embedding_data = response['data'][0]['embedding']
        return {"embedding": embedding_data}

    def invoke_non_stream(self, messages):
        """invoke the model without streaming"""
        max_retries = 3
        while max_retries > 0:
            try:
                if self.enabled_load_balancer:
                    response = asyncio.run(self.load_balance(messages))
                else:
                    response = litellm.completion(messages=messages, 
                                                        stream=False,
                                                        ** self.litellm_params
                                                        )
                
                return {"content": response.choices[0].message.content}
            except Exception as e:
                    log.error("Error invoking LiteLLM: %s", e)
                    max_retries -= 1
                    if max_retries <= 0:
                        raise e
                    else:
                        time.sleep(1)

    def invoke_stream(self, message, messages):
        """invoke the model with streaming"""
        response_uuid = str(uuid.uuid4())
        if self.set_response_uuid_in_user_properties:
            message.set_data("input.user_properties:response_uuid", response_uuid)

        aggregate_result = ""
        current_batch = ""
        first_chunk = True

        max_retries = 3
        while max_retries > 0:
            try:
                if self.enabled_load_balancer:
                    response = asyncio.run(self.load_balance(messages))
                else:
                    response = litellm.completion(messages=messages, 
                                                stream=True,
                                                ** self.litellm_params,
                                                )

                for chunk in response:
                    # If we get any response, then don't retry
                    max_retries = 0
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        aggregate_result += content
                        current_batch += content
                        if len(current_batch.split()) >= self.stream_batch_size:
                            if self.stream_to_flow:
                                self.send_streaming_message(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            elif self.stream_to_next_component:
                                self.send_to_next_component(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            current_batch = ""
                            first_chunk = False
            except Exception as e:
                log.error("Error invoking LiteLLM: %s", e)
                max_retries -= 1
                if max_retries <= 0:
                    raise e
                else:
                    # Small delay before retrying
                    time.sleep(1)

        if self.stream_to_next_component:
            # Just return the last chunk
            return {
                "content": aggregate_result,
                "chunk": current_batch,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": True,
                "streaming": True,
            }

        if self.stream_to_flow:
            self.send_streaming_message(
                message,
                current_batch,
                aggregate_result,
                response_uuid,
                first_chunk,
                True,
            )

        return {"content": aggregate_result, "response_uuid": response_uuid}

    def send_streaming_message(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )
        self.send_to_flow(self.stream_to_flow, message)

    def send_to_next_component(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )

        result = {
            "chunk": chunk,
            "content": aggregate_result,
            "response_uuid": response_uuid,
            "first_chunk": first_chunk,
            "last_chunk": last_chunk,
            "streaming": True,
        }

        self.process_post_invoke(result, message)
