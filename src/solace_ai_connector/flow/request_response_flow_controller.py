"""
This file will handle sending a message to a named flow and then 
receiving the output message from that flow. It will also support the result
message being a streamed message that comes in multiple parts. 

Each component can optionally create multiple of these using the configuration:

```yaml
- name: example_flow
  components:
    - component_name: example_component
      component_module: custom_component
      request_response_flow_controllers:
        - name: example_controller
          flow_name: llm_flow
          streaming: true
          streaming_complete_expression: input.payload:streaming.last_message
          request_expiry_ms: 300000
```

"""

import queue
import time
from typing import Dict, Any

from ..common.message import Message
from ..common.event import Event, EventType


# This is a very basic component which will be stitched onto the final component in the flow
class RequestResponseControllerOuputComponent:
    def __init__(self, controller):
        self.controller = controller

    def enqueue(self, event):
        self.controller.enqueue_response(event)


# This is the main class that will be used to send messages to a flow and receive the response
class RequestResponseFlowController:
    def __init__(self, config: Dict[str, Any], connector):
        self.config = config
        self.connector = connector
        self.broker_config = config.get("broker_config")
        self.request_expiry_ms = config.get("request_expiry_ms", 300000)
        self.request_expiry_s = self.request_expiry_ms / 1000
        self.input_queue = None
        self.response_queue = None
        self.enqueue_time = None
        self.request_outstanding = False

        self.flow = self.create_broker_request_response_flow()
        self.setup_queues(self.flow)
        self.flow.run()

    def create_broker_request_response_flow(self):
        self.broker_config["request_expiry_ms"] = self.request_expiry_ms
        config = {
            "name": "_internal_broker_request_response_flow",
            "components": [
                {
                    "component_name": "_internal_broker_request_response",
                    "component_module": "broker_request_response",
                    "component_config": self.broker_config,
                }
            ],
        }
        return self.connector.create_flow(flow=config, index=0, flow_instance_index=0)

    def setup_queues(self, flow):
        # Input queue to send the message to the flow
        self.input_queue = flow.get_input_queue()

        # Response queue to receive the response from the flow
        self.response_queue = queue.Queue()
        rrcComponent = RequestResponseControllerOuputComponent(self)
        flow.set_next_component(rrcComponent)

    def do_broker_request_response(
        self, request_message, stream=False, streaming_complete_expression=None
    ):
        # Send the message to the broker
        self.send_message(request_message, stream, streaming_complete_expression)

        # Now we will wait for the response
        now = time.time()
        elapsed_time = now - self.enqueue_time
        remaining_timeout = self.request_expiry_s - elapsed_time
        if stream:
            # If we are in streaming mode, we will return individual messages
            # until we receive the last message. Use the expression to determine
            # if this is the last message
            while True:
                try:
                    event = self.response_queue.get(timeout=remaining_timeout)
                    if event.event_type == EventType.MESSAGE:
                        message = event.data
                        last_message = message.get_data(streaming_complete_expression)
                        yield message, last_message
                        if last_message:
                            return
                except queue.Empty:
                    if (time.time() - self.enqueue_time) > self.request_expiry_s:
                        raise TimeoutError(  # pylint: disable=raise-missing-from
                            "Timeout waiting for response"
                        )
                except Exception as e:
                    raise e

                now = time.time()
                elapsed_time = now - self.enqueue_time
                remaining_timeout = self.request_expiry_s - elapsed_time

        # If we are not in streaming mode, we will return a single message
        # and then stop the iterator
        try:
            event = self.response_queue.get(timeout=remaining_timeout)
            if event.event_type == EventType.MESSAGE:
                message = event.data
                yield message, True
                return
        except queue.Empty:
            if (time.time() - self.enqueue_time) > self.request_expiry_s:
                raise TimeoutError(  # pylint: disable=raise-missing-from
                    "Timeout waiting for response"
                )
        except Exception as e:
            raise e

    def send_message(
        self, message: Message, stream=False, streaming_complete_expression=None
    ):
        # Make a new message, but copy the data from the original message
        if not self.input_queue:
            raise ValueError(f"Input queue for flow {self.flow.name} not found")

        # Need to set the previous object to the required input for the
        # broker_request_response component
        message.set_previous(
            {
                "payload": message.get_payload(),
                "user_properties": message.get_user_properties(),
                "topic": message.get_topic(),
                "stream": stream,
                "streaming_complete_expression": streaming_complete_expression,
            },
        )

        event = Event(EventType.MESSAGE, message)
        self.enqueue_time = time.time()
        self.request_outstanding = True
        self.input_queue.put(event)

    def enqueue_response(self, event):
        self.response_queue.put(event)