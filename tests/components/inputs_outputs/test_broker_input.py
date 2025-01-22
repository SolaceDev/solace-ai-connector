import unittest
from unittest.mock import patch, MagicMock
from solace_ai_connector.components.inputs_outputs.broker_input import BrokerInput
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
import os
from dotenv import load_dotenv


class TestBrokerInput(unittest.TestCase):

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_input.BrokerInput.connect"
    )
    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_input.BrokerInput.generate_uuid"
    )
    def setUp(self, mock_generate_uuid, mock_connect):
        load_dotenv()
        self.mock_generate_uuid = mock_generate_uuid
        self.mock_connect = mock_connect

        self.mock_generate_uuid.return_value = "test-uuid"

        self.config = {
            "broker_type": "solace",
            "broker_url": os.getenv("BROKER_URL"),
            "broker_username": os.getenv("BROKER_USERNAME"),
            "broker_password": os.getenv("BROKER_PASSWORD"),
            "broker_vpn": os.getenv("BROKER_VPN"),
            # "broker_subscriptions": os.getenv("BROKER_SUBSCRIPTIONS").split(","),
            "temporary_queue": True,
        }

        self.broker_input = BrokerInput(
            module_info={"config_parameters": []}, config=self.config
        )
        self.broker_input.messaging_service = MagicMock()

    def test_invoke(self):
        message = Message(
            payload="test-payload", topic="test-topic", user_properties={"key": "value"}
        )
        data = self.broker_input.invoke(message, None)
        self.assertEqual(data["payload"], "test-payload")
        self.assertEqual(data["topic"], "test-topic")
        self.assertEqual(data["user_properties"], {"key": "value"})

    def test_get_next_message(self):
        mock_broker_message = {
            "payload": "test-payload",
            "topic": "test-topic",
            "user_properties": {"key": "value"},
        }
        self.broker_input.messaging_service.receive_message.return_value = (
            mock_broker_message
        )

        message = self.broker_input.get_next_message()
        self.assertIsInstance(message, Message)
        self.assertEqual(message.get_payload(), "test-payload")
        self.assertEqual(message.get_topic(), "test-topic")
        self.assertEqual(message.get_user_properties(), {"key": "value"})

    def test_acknowledge_message(self):
        mock_broker_message = MagicMock()
        self.broker_input.current_broker_message = mock_broker_message
        ack_callback = self.broker_input.get_acknowledgement_callback()
        ack_callback()
        self.broker_input.messaging_service.ack_message.assert_called_once_with(
            mock_broker_message
        )


if __name__ == "__main__":
    unittest.main()
