"""This component sends messages to a websocket connection."""

from ...common.log import log
from ...common.utils import encode_payload
from .websocket_base import WebsocketBase

info = {
    "class_name": "WebsocketOutput",
    "description": "Send messages to a websocket connection.",
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "int",
            "required": False,
            "description": "Port to listen on (optional)",
        },
        {
            "name": "serve_html",
            "type": "bool",
            "required": False,
            "description": "Serve the example HTML file",
            "default": False,
        },
        {
            "name":
            "html_path",
            "type": "string",
            "required": False,
            "description": "Path to the HTML file to serve",
            "default": "examples/websocket/websocket_example_app.html",
        },
        {
            "name": "payload_encoding",
            "required": False,
            "description": "Encoding for the payload (utf-8, base64, gzip, none)",
            "default": "none",
        },
        {
            "name": "payload_format",
            "required": False,
            "description": "Format for the payload (json, yaml, text)",
            "default": "json",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "The payload to be sent via WebSocket",
            },
            "socket_id": {
                "type": "string",
                "description": "Identifier for the WebSocket connection",
            },
        },
        "required": ["payload", "user_properties"],
    },
}


class WebsocketOutput(WebsocketBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.payload_encoding = self.get_config("payload_encoding")
        self.payload_format = self.get_config("payload_format")

    def run(self):
        if self.listen_port:
            self.run_server()

    def stop_component(self):
        self.stop_server()

    def invoke(self, message, data):
        try:
            payload = data.get("payload")
            socket_id = data.get("socket_id")

            if not socket_id:
                log.error("No socket_id provided")
                self.discard_current_message()
                return None

            encoded_payload = encode_payload(
                payload, self.payload_encoding, self.payload_format
            )
            
            if not self.send_to_socket(socket_id, encoded_payload):
                self.discard_current_message()
                return None

        except Exception as e:
            log.error("Error sending message via WebSocket: %s", str(e))
            self.discard_current_message()
            return None

        return data
