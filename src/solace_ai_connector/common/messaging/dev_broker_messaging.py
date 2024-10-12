"""This is a simple broker for testing purposes. It allows sending and receiving 
messages to/from queues. It supports subscriptions based on topics."""

from typing import Dict, List, Any
import queue
import re
from copy import deepcopy
from .messaging import Messaging


class DevBroker(Messaging):
    def __init__(self, broker_properties: dict, flow_lock_manager, flow_kv_store):
        super().__init__(broker_properties)
        self.flow_lock_manager = flow_lock_manager
        self.flow_kv_store = flow_kv_store
        self.connected = False
        self.subscriptions_lock = self.flow_lock_manager.get_lock("subscriptions")
        with self.subscriptions_lock:
            self.subscriptions = self.flow_kv_store.get("dev_broker:subscriptions")
            if self.subscriptions is None:
                self.subscriptions: Dict[str, List[str]] = {}
                self.flow_kv_store.set("dev_broker:subscriptions", self.subscriptions)
            self.queues = self.flow_kv_store.get("dev_broker:queues")
            if self.queues is None:
                self.queues: Dict[str, queue.Queue] = {}
                self.flow_kv_store.set("dev_broker:queues", self.queues)

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
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
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

        if user_context and "callback" in user_context:
            user_context["callback"](user_context)

    def subscribe(self, subscription: str, queue_id: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        subscription = self._subscription_to_regex(subscription)

        with self.subscriptions_lock:
            if queue_id not in self.queues:
                self.queues[queue_id] = queue.Queue()
            if subscription not in self.subscriptions:
                self.subscriptions[subscription] = []
            self.subscriptions[subscription].append(queue_id)

    def ack_message(self, message):
        pass

    def _get_matching_queue_ids(self, topic: str) -> List[str]:
        matching_queue_ids = []
        with self.subscriptions_lock:
            for subscription, queue_ids in self.subscriptions.items():
                if self._topic_matches(subscription, topic):
                    matching_queue_ids.extend(queue_ids)
            return list(set(matching_queue_ids))  # Remove duplicates

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        return re.match(f"^{subscription}$", topic) is not None

    @staticmethod
    def _subscription_to_regex(subscription: str) -> str:
        return subscription.replace("*", "[^/]+").replace(">", ".*")
