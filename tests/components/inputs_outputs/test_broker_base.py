import unittest
from unittest.mock import patch, MagicMock
import os
from dotenv import load_dotenv
from solace_ai_connector.components.inputs_outputs.broker_base import BrokerBase

# Load environment variables from .env file in the current directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


class TestBrokerBase(unittest.TestCase):

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_base.MessagingServiceBuilder"
    )
    def setUp(self, MockMessagingServiceBuilder):
        self.mock_messaging_service = (
            MockMessagingServiceBuilder.return_value.from_properties.return_value.build.return_value
        )
        self.broker = BrokerBase(module_info={})

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_base.BrokerBase.get_broker_properties"
    )
    def test_initialization(self, mock_get_broker_properties):
        mock_get_broker_properties.return_value = {
            "broker_type": os.getenv("BROKER_TYPE", "test"),
            "host": os.getenv("SOLACE_BROKER_URL", "localhost"),
            "username": os.getenv("SOLACE_BROKER_USERNAME", "user"),
            "password": os.getenv("SOLACE_BROKER_PASSWORD", "pass"),
            "vpn_name": os.getenv("SOLACE_BROKER_VPN", "vpn"),
            "queue_name": os.getenv("SOLACE_BROKER_QUEUE_NAME", "queue"),
            "subscriptions": os.getenv("SOLACE_BROKER_SUBSCRIPTIONS", "").split(","),
            "trust_store_path": os.getenv(
                "SOLACE_BROKER_TRUST_STORE_PATH", "/path/to/truststore"
            ),
            "temporary_queue": os.getenv("TEMPORARY_QUEUE", "False") == "True",
        }
        self.broker = BrokerBase(module_info={})
        self.assertEqual(self.broker.broker_properties["broker_type"], "test")
        self.assertFalse(self.broker.connected)
        self.assertTrue(self.broker.needs_acknowledgement)

    def test_connect(self):
        self.broker.connect()
        self.mock_messaging_service.connect.assert_called_once()
        self.assertTrue(self.broker.connected)

    def test_disconnect(self):
        self.broker.connect()
        self.broker.disconnect()
        self.mock_messaging_service.disconnect.assert_called_once()
        self.assertFalse(self.broker.connected)

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_base.BrokerBase.get_config"
    )
    def test_encode_payload(self, mock_get_config):
        mock_get_config.side_effect = lambda key: {
            "payload_encoding": "utf-8",
            "payload_format": "json",
        }.get(key)
        payload = {"key": "value"}
        encoded_payload = self.broker.encode_payload(payload)
        self.assertIsInstance(encoded_payload, bytes)
        self.assertEqual(encoded_payload, b'{"key": "value"}')

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_base.BrokerBase.get_config"
    )
    def test_decode_payload(self, mock_get_config):
        mock_get_config.side_effect = lambda key: {
            "payload_encoding": "utf-8",
            "payload_format": "json",
        }.get(key)
        payload = b'{"key": "value"}'
        decoded_payload = self.broker.decode_payload(payload)
        self.assertIsInstance(decoded_payload, dict)
        self.assertEqual(decoded_payload["key"], "value")

    def test_generate_uuid(self):
        uuid1 = self.broker.generate_uuid()
        uuid2 = self.broker.generate_uuid()
        self.assertNotEqual(uuid1, uuid2)
        self.assertIsInstance(uuid1, str)
        self.assertIsInstance(uuid2, str)

    @patch(
        "solace_ai_connector.components.inputs_outputs.broker_base.BrokerBase.disconnect"
    )
    def test_stop_component(self, mock_disconnect):
        self.broker.stop_component()
        mock_disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
