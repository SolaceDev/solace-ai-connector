"""This is a simple broker for testing purposes. It allows sending and receiving 
messages to/from queues. It supports subscriptions based on topics."""

from typing import Dict, List, Any
import threading
import queue
import re
from copy import deepcopy
from .messaging import Messaging


class DevBroker(Messaging):
    def __init__(self, broker_properties: dict):
        super().__init__(broker_properties)
        self.subscriptions: Dict[str, List[str]] = {}
        self.queues: Dict[str, queue.Queue] = {}
        self.connected = False
        self.lock = threading.Lock()

    def connect(self):
        self.connected = True
        queue_name = self.broker_properties.get("queue_name")
        subscriptions = self.broker_properties.get("subscriptions", [])
        if queue_name:
            self.queues[queue_name] = queue.Queue()
            for subscription in subscriptions:
                self.subscribe(subscription["topic"], queue_name)

    def disconnect(self):
        self.connected = False

    def receive_message(self, timeout_ms, queue_id: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        try:
            return self.queues[queue_id].get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return None

    def send_message(
        self, destination_name: str, payload: Any, user_properties: Dict = None
    ):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        message = {
            "payload": payload,
            "topic": destination_name,
            "user_properties": user_properties or {},
        }

        matching_queue_ids = self._get_matching_queue_ids(destination_name)

        for queue_id in matching_queue_ids:
            # Clone the message for each queue to ensure isolation
            self.queues[queue_id].put(deepcopy(message))

    def subscribe(self, subscription: str, queue_id: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        with self.lock:
            if queue_id not in self.queues:
                self.queues[queue_id] = queue.Queue()
            if subscription not in self.subscriptions:
                self.subscriptions[subscription] = []
            self.subscriptions[subscription].append(queue_id)

    def _get_matching_queue_ids(self, topic: str) -> List[str]:
        matching_queue_ids = []
        for subscription, queue_ids in self.subscriptions.items():
            if self._topic_matches(subscription, topic):
                matching_queue_ids.extend(queue_ids)
        return list(set(matching_queue_ids))  # Remove duplicates

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        regex = subscription.replace(">", ".*").replace("*", "[^/]+")
        return re.match(f"^{regex}$", topic) is not None
