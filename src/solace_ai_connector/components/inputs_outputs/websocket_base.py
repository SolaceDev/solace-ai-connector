"""Base class for WebSocket components."""

from flask import Flask, send_file, request
from flask_socketio import SocketIO
from ...common.log import log
from ..component_base import ComponentBase

class WebsocketBase(ComponentBase):
    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.listen_port = self.get_config("listen_port")
        self.serve_html = self.get_config("serve_html", False)
        self.html_path = self.get_config("html_path", "")
        self.sockets = {}
        self.app = None
        self.socketio = None

        if self.listen_port:
            self.setup_websocket_server()

    def setup_websocket_server(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.setup_websocket()

        if self.serve_html:
            self.setup_html_route()

    def setup_html_route(self):
        @self.app.route("/")
        def serve_html():
            return send_file(self.html_path)

    def setup_websocket(self):
        @self.socketio.on("connect")
        def handle_connect():
            socket_id = request.sid
            self.sockets[socket_id] = self.socketio
            self.kv_store_set("websocket_connections", self.sockets)
            log.info("New WebSocket connection established. Socket ID: %s", socket_id)
            return socket_id

        @self.socketio.on("disconnect")
        def handle_disconnect():
            socket_id = request.sid
            if socket_id in self.sockets:
                del self.sockets[socket_id]
                self.kv_store_set("websocket_connections", self.sockets)
                log.info("WebSocket connection closed. Socket ID: %s", socket_id)

    def run_server(self):
        if self.socketio:
            self.socketio.run(self.app, port=self.listen_port)

    def stop_server(self):
        if self.socketio:
            self.socketio.stop()

    def get_sockets(self):
        if not self.sockets:
            self.sockets = self.kv_store_get("websocket_connections") or {}
        return self.sockets

    def send_to_socket(self, socket_id, payload):
        sockets = self.get_sockets()
        if socket_id == "*":
            for socket in sockets.values():
                socket.emit("message", payload)
            log.debug("Message sent to all WebSocket connections")
        elif socket_id in sockets:
            sockets[socket_id].emit("message", payload)
            log.debug("Message sent to WebSocket connection %s", socket_id)
        else:
            log.error("No active connection found for socket_id: %s", socket_id)
            return False
        return True
