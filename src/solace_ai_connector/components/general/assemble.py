"""A flow component that assembles multiple messages into one message through the use of an assembly key"""

import time
import math
from datetime import datetime

from ...common.log import log
from ..component_base import ComponentBase
from ...common.message import Message

info = {
    "class_name": "Assemble",
    "description": "Using an assembly key to match message fragments, assemble messages with that key into one message. "
    "The number of fragments indicates how many message fragments are required to produce one full message. "
    "If the timeout occurs before all fragments have been received, an incomplete message will be released.",
    "short_description": "Using an assembly key, assemble messages with that key into one message.",
    "config_parameters": [
        {
            "name": "assembly_key_source_expression",
            "required": True,
            "type": "string",
            "description": "The expression to extract the assembly key from the message",
        },
        {
            "name": "number_of_fragments",
            "required": True,
            "type": "integer",
            "description": "Number of message fragments required to produce one full message",
        },
        {
            "name": "assembly_timeout_ms",
            "required": False,
            "description": "Number of milliseconds to wait for all fragments to be received before releasing an incomplete message",
            "default": 30000,
            "type": "integer",
        },
    ],
    "input_schema": {
        "type": "object",
        "description": "The input message to be aggregated",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "fragments": {
                "type": "array",
                "description": "List of all fragments received",
                "items": {
                    "type": "object",
                    "description": "Fragment of the message",
                    "properties": {
                        "payload": {
                            "type": "object",
                            "description": "The payload of the fragment",
                        },
                        "user_properties": {
                            "type": "object",
                            "description": "The user properties of the fragment",
                        },
                        "topic": {
                            "type": "string",
                            "description": "The topic of the fragment",
                        },
                    },
                    "required": ["payload", "topic"],
                },
            },
            "status": {
                "type": "string",
                "description": "The status of the assembly: 'ok', 'timeout' or 'no_assembly_key'",
            },
        },
    },
}


class Assemble(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.assembly_key_source_expression = self.get_config(
            "assembly_key_source_expression"
        )
        self.number_of_fragments = self.get_config("number_of_fragments")
        self.assembly_timeout_ms = self.get_config("assembly_timeout_ms")
        self.assembly_cache = AssemblyCache()

    def invoke(self, message, data):
        # Get the payload, user properties, and topic from the message
        message_input = message.get_data("input")

        # Extract the assembly key from the message
        assembly_key = message.get_data(self.assembly_key_source_expression)

        # If the assembly key is not found, pass it on with 'no_assembly_key' status
        if assembly_key is None:
            return {
                "fragments": [message_input],
                "status": "no_assembly_key",
            }

        assembly = self.assembly_cache.get_assembly(assembly_key)

        # is_expired, remaining_time = self.update_queue_timer()

        self.current_aggregation["list"].append(data)
        message.combine_with_message(self.current_aggregation["message"])

        # If the aggregation is full or timed out, send it
        if is_expired or len(self.current_aggregation["list"]) >= self.max_items:
            self.set_queue_timeout(None)
            log.debug("Aggregation done - sending: %s", self.current_aggregation)
            self.send_aggregation()
            return None

        # Aggregation is not full, so set the timer to the remaining time
        self.set_queue_timeout(remaining_time)

        # Otherwise, return None to indicate that no message should be sent
        return None

    def update_queue_timer(self):
        # Get the epoch time in milliseconds
        epoch_time_ms = math.floor(time.time() * 1000)

        # How much time is left on the timer
        remaining_time = (
            self.current_aggregation["next_aggregation_time"] - epoch_time_ms
        )

        if remaining_time <= 0:
            return True, self.max_time_ms

        return False, remaining_time

    def handle_queue_timeout(self):
        # If we have an aggregation, send it
        if self.current_aggregation is not None:
            self.send_aggregation()
        else:
            # Otherwise, clear the timer
            self.set_queue_timeout(None)

    def send_aggregation(self):
        # Send the aggregation
        data, message = self.complete_aggregation()
        self.process_post_invoke(data, message)

    def start_new_aggregation(self):
        # Get the epoch time in milliseconds
        epoch_time_ms = math.floor(time.time() * 1000)
        next_time_for_timeout = self.max_time_ms + epoch_time_ms
        return {
            "list": [],
            "next_aggregation_time": next_time_for_timeout,
            "message": Message(),
        }

    def complete_aggregation(self):
        log.debug("Completing aggregation")
        aggregation = self.current_aggregation
        self.current_aggregation = None
        return aggregation["list"], aggregation["message"]

    # def get_default_queue_timeout(self):
    #     return self.get_config("max_time_ms")


class AssemblyCache:
    def __init__(self):
        self.cache = {}
        self.timeout_list = []

    def add_fragment(self, assembly_key, fragment):
        if assembly_key not in self.cache:
            entry = {"fragments": [], "created_at": datetime.now()}
            self.cache[assembly_key] = entry
            self.timeout_list.append(entry)
        self.cache[assembly_key].append(fragment)
        return len(self.cache[assembly_key])

    def get_assembly(self, assembly_key):
        return self.cache.get(assembly_key, None)

    def remove_assembly(self, assembly_key):
        if assembly_key in self.cache:
            entry = self.cache[assembly_key]
            # We are leaving the entry in the timeout list to avoid having to search for it
            # But we are removing the fragments to save memory and deleting it from the cache
            entry["fragments"] = None
            del self.cache[assembly_key]

    def get_next_timeout(self):
        if len(self.timeout_list) == 0:
            return None
        while len(self.timeout_list) > 0:
            if self.timeout_list[0]["fragments"] is None:
                self.timeout_list.pop(0)
            else:
                return self.timeout_list[0]["created_at"]
        return None
