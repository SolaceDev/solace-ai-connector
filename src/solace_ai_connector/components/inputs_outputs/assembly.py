"""Assembly component for the Solace AI Event Connector"""

from ...common.log import log
from ..component_base import ComponentBase
from ...common.message import Message


info = {
    "class_name": "Assembly",
    "description": (
        "Assembles messages till criteria is met, "
        "the output will be the assembled message"
    ),
    "config_parameters": [
        {
            "name": "assemble_key",
            "required": True,
            "description": "The key from input message that would cluster the similar messages together",
        },
        {
            "name": "max_items",
            "required": False,
            "default": 10,
            "description": "Maximum number of messages to assemble. Once this value is reached, the messages would be flushed to the output",
        },
        {
            "name": "max_time_ms",
            "required": False,
            "default": 10000,
            "description": "The timeout in seconds to wait for the messages to assemble. If timeout is reached before the max size is reached, the messages would be flushed to the output",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "output_schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "string",
                },
                "topic": {
                    "type": "string",
                },
                "user_properties": {
                    "type": "object",
                },
            },
        },
    },
}

# Default timeout to flush the messages
DEFAULT_FLUSH_TIMEOUT_MS = 10000
TIMEOUT_PREFIX = "assembly_timeout_"


class Assembly(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.assemble_key = self.get_config("assemble_key")
        self.max_items = self.get_config("max_items")
        self.max_time_ms = self.get_config("max_time_ms", DEFAULT_FLUSH_TIMEOUT_MS)

    def invoke(self, message, data):
        # Check if the message has the assemble key
        if self.assemble_key not in data:
            log.error(f"Message does not have the key {self.assemble_key}")
            raise ValueError(f"Message does not have the key {self.assemble_key}")

        event_key = data[self.assemble_key]
        # Fetch the current assembly from cache
        current_assembly = self.cache_service.get_data(event_key)

        # Create a new assembly if not present
        if not current_assembly:
            current_assembly = self.start_new_assembly(event_key)

        # Update cache with the new data
        message.combine_with_message(current_assembly["message"])
        current_assembly["message"] = message
        current_assembly["list"].append(data)
        self.cache_service.add_data(event_key, current_assembly)

        # Flush the assembly if the max size is reached
        if len(current_assembly["list"]) >= self.max_items:
            log.debug(f"Flushing data by size - {len(current_assembly['list'])} items")
            return self.flush_assembly(event_key)["list"]

    def handle_timer_event(self, timer_data):
        if timer_data["timer_id"].startswith(TIMEOUT_PREFIX):
            assemble_key = timer_data["timer_id"].replace(TIMEOUT_PREFIX, "")
            assembled_data = self.flush_assembly(assemble_key)
            log.debug(f"Flushing data by timeout - {len(assembled_data['list'])} items")
            self.process_post_invoke(assembled_data["list"], assembled_data["message"])

    def start_new_assembly(self, assemble_key):
        self.add_timer(self.max_time_ms, TIMEOUT_PREFIX + assemble_key)
        return {
            "list": [],
            "message": Message(),
        }

    def flush_assembly(self, assemble_key):
        self.cancel_timer(TIMEOUT_PREFIX + assemble_key)
        assembly = self.cache_service.get_data(assemble_key)
        self.cache_service.remove_data(assemble_key)
        return assembly
