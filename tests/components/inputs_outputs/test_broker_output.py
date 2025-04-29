import unittest
from unittest.mock import patch, MagicMock
from solace_ai_connector.components.inputs_outputs.broker_output import BrokerOutput
from solace_ai_connector.common.message import Message
import os
from dotenv import load_dotenv


class TestBrokerOutput(unittest.TestCase):

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_output.BrokerOutput.connect"
    )
    def setUp(self, mock_connect):
        load_dotenv()
        self.mock_connect = mock_connect

        self.config = {
            "broker_type": "solace",
            "broker_url": os.getenv("BROKER_URL"),
            "broker_username": os.getenv("BROKER_USERNAME"),
            "broker_password": os.getenv("BROKER_PASSWORD"),
            "broker_vpn": os.getenv("BROKER_VPN"),
            "propagate_acknowledgements": True,
            "copy_user_properties": True,
            "decrement_ttl": True,
            "discard_on_ttl_expiration": True,
        }

        self.broker_output = BrokerOutput(
            module_info={"config_parameters": []}, config=self.config
        )
        self.broker_output.messaging_service = MagicMock()

    def test_invoke(self):
        message = Message(
            payload="test-payload", topic="test-topic", user_properties={"key": "value"}
        )
        data = {
            "payload": "test-payload",
            "topic": "test-topic",
            "user_properties": {"key": "value"},
        }
        result = self.broker_output.invoke(message, data)
        self.assertEqual(result, data)

    def test_send_message(self):
        message = Message(
            payload="test-payload", topic="test-topic", user_properties={"key": "value"}
        )
        message.set_previous(
            {
                "payload": "test-payload",
                "topic": "test-topic",
                "user_properties": {"ttl": 1},
            }
        )
        # Call the send_message method
        self.broker_output.send_message(message)

        # Verify that messaging_service.send_message was called with the expected arguments
        self.broker_output.messaging_service.send_message.assert_called_once_with(
            payload="test-payload",
            destination_name="test-topic",
            user_properties={"ttl": 0, "key": "value"},
            user_context={
                "message": message,
                "callback": self.broker_output.handle_message_ack_from_broker,
            },
        )

    def test_handle_message_ack_from_broker(self):
        mock_context = {"message": MagicMock()}
        self.broker_output.handle_message_ack_from_broker(mock_context)
        mock_context["message"].call_acknowledgements.assert_called_once()


if __name__ == "__main__":
    unittest.main()
