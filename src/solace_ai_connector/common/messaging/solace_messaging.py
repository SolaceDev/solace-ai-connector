# solace-messaging.py - use solace-pubsubplus as a messaging service

import logging
import os
import certifi
import threading
import time
from enum import Enum

from solace.messaging.messaging_service import (
    MessagingService,
    ReconnectionListener,
    ReconnectionAttemptListener,
    ServiceInterruptionListener,
    ServiceEvent,
)
from solace.messaging.resources.queue import Queue
from solace.messaging.config.retry_strategy import RetryStrategy
from solace.messaging.receiver.persistent_message_receiver import (
    PersistentMessageReceiver,
)
from solace.messaging.publisher.persistent_message_publisher import (
    PersistentMessagePublisher,
    MessagePublishReceiptListener,
    PublishReceipt,
)
from solace.messaging.receiver.message_receiver import MessageHandler, InboundMessage
from solace.messaging.errors.pubsubplus_client_error import PubSubPlusClientError
from solace.messaging.config.missing_resources_creation_configuration import (
    MissingResourcesCreationStrategy,
)
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.resources.topic import Topic
from solace import SOLACE_LOGGING_CONFIG

from .messaging import Messaging
from ..log import log


class ConnectionStatus(Enum):
    RECONNECTING = 2
    CONNECTED = 1
    DISCONNECTED = 0


_connection_status = ConnectionStatus.DISCONNECTED
_lock = threading.Lock()


def change_connection_status(status: ConnectionStatus):
    global _connection_status
    with _lock:
        _connection_status = status


class MessageHandlerImpl(MessageHandler):

    def __init__(self, persistent_receiver: PersistentMessageReceiver):
        self.receiver: PersistentMessageReceiver = persistent_receiver
        self.persistent_receiver: PersistentMessageReceiver = None

    def on_message(self, message: InboundMessage):
        # Check if the payload is a String or Byte, decode if its the later
        payload = (
            message.get_payload_as_string()
            if message.get_payload_as_string() is not None
            else message.get_payload_as_bytes()
        )
        if isinstance(payload, bytearray):
            payload = payload.decode()

        # topic = message.get_destination_name()
        self.receiver.ack(message)


class MessagePublishReceiptListenerImpl(MessagePublishReceiptListener):

    def __init__(self, callback=None):
        self.callback = callback

    def on_publish_receipt(self, publish_receipt: PublishReceipt):
        if publish_receipt.user_context:
            callback = publish_receipt.user_context.get("callback")
            callback(publish_receipt.user_context)


# Inner classes for error handling
class ServiceEventHandler(
    ReconnectionListener, ReconnectionAttemptListener, ServiceInterruptionListener
):

    def __init__(self, stop_signal):
        self.stop_signal = stop_signal

    def on_reconnected(self, service_event: ServiceEvent):
        change_connection_status(ConnectionStatus.CONNECTED)
        log.debug("Reconnected to broker: %s", service_event.get_cause())
        log.debug("Message: %s", service_event.get_message())

    def on_reconnecting(self, event: "ServiceEvent"):
        change_connection_status(ConnectionStatus.RECONNECTING)

        def log_reconnecting():
            while (
                not self.stop_signal.is_set()
                and _connection_status == ConnectionStatus.RECONNECTING
            ):
                log.debug("Reconnecting to broker: %s", event.get_cause())
                log.debug("Message: %s", event.get_message())
                self.stop_signal.wait(timeout=1)

        log_thread = threading.Thread(target=log_reconnecting)
        log_thread.start()

    def on_service_interrupted(self, event: "ServiceEvent"):
        change_connection_status(ConnectionStatus.DISCONNECTED)
        log.debug("Service interrupted - Error cause: %s", event.get_cause())
        log.debug("Message: %s", event.get_message())


def set_python_solace_log_level(level: str):
    # get solace loggers
    loggers = SOLACE_LOGGING_CONFIG["loggers"]
    # update log level
    for logr in loggers:
        loggers.get(logr)["level"] = level
    # set logger config change
    logging.config.dictConfig(SOLACE_LOGGING_CONFIG)


# Create SolaceMessaging class inheriting from Messaging
class SolaceMessaging(Messaging):

    def __init__(self, broker_properties: dict, stop_signal):
        super().__init__(broker_properties)
        self.persistent_receivers = []
        self.messaging_service = None
        self.service_handler = None
        self.publisher = None
        self.persistent_receiver: PersistentMessageReceiver = None
        self.stop_signal = stop_signal
        # MessagingService.set_core_messaging_log_level(
        #     level="DEBUG", file="/home/efunnekotter/core.log"
        # )
        # set_python_solace_log_level("DEBUG")

    def __del__(self):
        change_connection_status(ConnectionStatus.DISCONNECTED)
        self.disconnect()

    def connect(self):
        # Build A messaging service with a reconnection strategy of 20 retries over
        # an interval of 3 seconds
        broker_props = {
            "solace.messaging.transport.host": self.broker_properties.get("host"),
            "solace.messaging.service.vpn-name": self.broker_properties.get("vpn_name"),
            "solace.messaging.authentication.scheme.basic.username": self.broker_properties.get(
                "username"
            ),
            "solace.messaging.authentication.scheme.basic.password": self.broker_properties.get(
                "password"
            ),
            "solace.messaging.tls.trust-store-path": self.broker_properties.get(
                "trust_store_path"
            )
            or os.environ.get("TRUST_STORE")
            or os.path.dirname(certifi.where())
            or "/usr/share/ca-certificates/mozilla/",
        }
        strategy = self.broker_properties.get("reconnection_strategy")
        if strategy and strategy == "forever_retry":
            retry_interval = self.broker_properties.get("retry_interval")
            if not retry_interval:
                log.warning(
                    "retry_interval not provided, using default value of 3000 milliseconds"
                )
                retry_interval = 3000
            self.messaging_service = (
                MessagingService.builder()
                .from_properties(broker_props)
                .with_reconnection_retry_strategy(
                    RetryStrategy.forever_retry(retry_interval)
                )
                .with_connection_retry_strategy(
                    RetryStrategy.forever_retry(retry_interval)
                )
                .build()
            )
        elif strategy and strategy == "parametrized_retry":
            retry_count = self.broker_properties.get("retry_count")
            retry_wait = self.broker_properties.get("retry_wait")
            if not retry_count:
                log.warning("retry_count not provided, using default value of 20")
                retry_count = 20
            if not retry_wait:
                log.warning("retry_wait not provided, using default value of 3000")
                retry_wait = 3000
            self.messaging_service = (
                MessagingService.builder()
                .from_properties(broker_props)
                .with_reconnection_retry_strategy(
                    RetryStrategy.parametrized_retry(retry_count, retry_wait)
                )
                .with_connection_retry_strategy(
                    RetryStrategy.parametrized_retry(retry_count, retry_wait)
                )
                .build()
            )
        else:
            # default
            log.info(
                "Using default reconnection strategy. 20 retries with 3000ms interval"
            )
            self.messaging_service = (
                MessagingService.builder()
                .from_properties(broker_props)
                .with_reconnection_retry_strategy(
                    RetryStrategy.parametrized_retry(20, 3000)
                )
                .with_connection_retry_strategy(
                    RetryStrategy.parametrized_retry(20, 3000)
                )
                .build()
            )

        # Blocking connect thread
        result = self.messaging_service.connect_async()
        while not (self.stop_signal.is_set() or result.done()):
            log.debug("Connecting to broker...")
            self.stop_signal.wait(timeout=1)

        if result.result() is None:
            log.error("Failed to connect to broker")
            return False
        change_connection_status(ConnectionStatus.CONNECTED)

        # Event Handling for the messaging service
        self.service_handler = ServiceEventHandler(self.stop_signal)
        self.messaging_service.add_reconnection_listener(self.service_handler)
        self.messaging_service.add_reconnection_attempt_listener(self.service_handler)
        self.messaging_service.add_service_interruption_listener(self.service_handler)

        # Create a publisher
        self.publisher: PersistentMessagePublisher = (
            self.messaging_service.create_persistent_message_publisher_builder().build()
        )
        self.publisher.start()

        publish_receipt_listener = MessagePublishReceiptListenerImpl()
        self.publisher.set_message_publish_receipt_listener(publish_receipt_listener)

        if "queue_name" in self.broker_properties and self.broker_properties.get(
            "queue_name"
        ):
            self.bind_to_queue(
                self.broker_properties.get("queue_name"),
                self.broker_properties.get("subscriptions"),
                self.broker_properties.get("temporary_queue"),
            )

    def bind_to_queue(
        self, queue_name: str, subscriptions: list = None, temporary: bool = False
    ):
        if subscriptions is None:
            subscriptions = []

        if temporary:
            queue = Queue.non_durable_exclusive_queue(queue_name)
        else:
            queue = Queue.durable_exclusive_queue(queue_name)

        try:
            # Build a receiver and bind it to the queue
            self.persistent_receiver: PersistentMessageReceiver = (
                self.messaging_service.create_persistent_message_receiver_builder()
                .with_missing_resources_creation_strategy(
                    MissingResourcesCreationStrategy.CREATE_ON_START
                )
                .build(queue)
            )
            self.persistent_receiver.start()

            log.debug(
                "Persistent receiver started... Bound to Queue [%s] (Temporary: %s)",
                queue.get_name(),
                temporary,
            )

        # Handle API exception
        except PubSubPlusClientError as exception:
            log.warning(
                "Error creating persistent receiver for queue [%s], %s",
                queue_name,
                exception,
            )

        # Add to list of receivers
        self.persistent_receivers.append(self.persistent_receiver)

        # If subscriptions are provided, add them to the receiver
        if subscriptions:
            for subscription in subscriptions:
                sub = TopicSubscription.of(subscription.get("topic"))
                self.persistent_receiver.add_subscription(sub)
                log.debug("Subscribed to topic: %s", subscription)

        return self.persistent_receiver

    def disconnect(self):
        try:
            self.messaging_service.disconnect()
            change_connection_status(ConnectionStatus.DISCONNECTED)
        except Exception as exception:  # pylint: disable=broad-except
            log.debug("Error disconnecting: %s", exception)

    def get_connection_status(self):
        return _connection_status

    def send_message(
        self,
        destination_name: str,
        payload: str,
        user_properties: dict = None,
        user_context=None,
    ):
        # Create a topic destination
        destination = Topic.of(destination_name)

        # Encode the message if it is a string
        if isinstance(payload, str):
            payload = bytearray(payload.encode("utf-8"))

        # Convert to bytearray if bytes
        elif isinstance(payload, bytes):
            payload = bytearray(payload)

        # Publish the message
        self.publisher.publish(
            message=payload,
            destination=destination,
            additional_message_properties=user_properties,
            user_context=user_context,
        )

    def receive_message(self, timeout_ms, queue_id):
        broker_message = self.persistent_receivers[0].receive_message(timeout_ms)
        if broker_message is None:
            return None

        # Convert Solace message to dictionary format
        return {
            "payload": broker_message.get_payload_as_string()
            or broker_message.get_payload_as_bytes(),
            "topic": broker_message.get_destination_name(),
            "user_properties": broker_message.get_properties(),
            "_original_message": broker_message,  # Keep original message for acknowledgement
        }

    def subscribe(
        self, subscription: str, persistent_receiver: PersistentMessageReceiver
    ):
        sub = TopicSubscription.of(subscription)
        persistent_receiver.add_subscription(sub)

    def ack_message(self, broker_message):
        if "_original_message" in broker_message:
            self.persistent_receiver.ack(broker_message["_original_message"])
        else:
            log.warning("Cannot acknowledge message: original Solace message not found")
