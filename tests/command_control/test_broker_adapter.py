"""Unit tests for the BrokerAdapter class."""

import unittest
from unittest.mock import MagicMock, patch

from src.solace_ai_connector.command_control.broker_adapter import BrokerAdapter
from src.solace_ai_connector.common.message import Message


class TestBrokerAdapter(unittest.TestCase):
    """Test cases for the BrokerAdapter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.connector = MagicMock()
        # Make sure the config mock returns proper values
        self.connector.config = {}
        self.command_control_service = MagicMock()
        self.adapter = BrokerAdapter(self.connector, self.command_control_service)

    def test_init(self):
        """Test initialization of BrokerAdapter."""
        self.assertEqual(self.adapter.connector, self.connector)
        self.assertEqual(
            self.adapter.command_control_service, self.command_control_service
        )
        self.assertEqual(self.adapter.namespace, "solace")
        self.assertEqual(self.adapter.topic_prefix, "sac-control/v1")
        self.assertIsNone(self.adapter.command_flow_name)
        self.assertIsNone(self.adapter.response_flow_name)
        self.assertIsNone(self.adapter.command_handler)

    def test_init_with_config(self):
        """Test initialization of BrokerAdapter with configuration."""
        # Test data
        config = {
            "command_control": {
                "namespace": "test-namespace",
                "topic_prefix": "test-prefix",
            }
        }
        connector = MagicMock()
        connector.config = config

        # Create the adapter
        adapter = BrokerAdapter(connector, self.command_control_service)

        # Verify the configuration was applied
        self.assertEqual(adapter.namespace, "test-namespace")
        self.assertEqual(adapter.topic_prefix, "test-prefix")

    def test_setup_command_flow(self):
        """Test setting up the command flow."""
        # Call the method
        self.adapter.setup_command_flow("test-flow")

        # Verify the flow name was set
        self.assertEqual(self.adapter.command_flow_name, "test-flow")

    def test_setup_response_flow(self):
        """Test setting up the response flow."""
        # Call the method
        self.adapter.setup_response_flow("test-flow")

        # Verify the flow name was set
        self.assertEqual(self.adapter.response_flow_name, "test-flow")

    def test_set_command_handler(self):
        """Test setting the command handler."""
        # Test data
        handler = lambda x: x

        # Call the method
        self.adapter.set_command_handler(handler)

        # Verify the handler was set
        self.assertEqual(self.adapter.command_handler, handler)

    def test_handle_message_command_topic(self):
        """Test handling a message on a command topic."""
        # Mock the command handler
        self.adapter.command_handler = MagicMock()

        # Mock the _is_command_topic method
        self.adapter._is_command_topic = MagicMock(return_value=True)

        # Mock the _parse_command_topic method
        self.adapter._parse_command_topic = MagicMock(return_value=("GET", "/test"))

        # Mock the _create_request method
        request = {"method": "GET", "endpoint": "/test"}
        self.adapter._create_request = MagicMock(return_value=request)

        # Test data
        message = MagicMock()
        message.get_topic.return_value = "solace/sac-control/v1/GET/test"
        message.get_payload.return_value = {"data": "test"}

        # Call the method
        self.adapter.handle_message(message)

        # Verify the methods were called
        self.adapter._is_command_topic.assert_called_once_with(
            "solace/sac-control/v1/GET/test"
        )
        self.adapter._parse_command_topic.assert_called_once_with(
            "solace/sac-control/v1/GET/test"
        )
        self.adapter._create_request.assert_called_once_with(
            "GET", "/test", {"data": "test"}, message
        )
        self.adapter.command_handler.assert_called_once_with(request)

    def test_handle_message_not_command_topic(self):
        """Test handling a message on a non-command topic."""
        # Mock the _is_command_topic method
        self.adapter._is_command_topic = MagicMock(return_value=False)

        # Mock the command handler
        self.adapter.command_handler = MagicMock()

        # Test data
        message = MagicMock()
        message.get_topic.return_value = "solace/other/topic"

        # Call the method
        self.adapter.handle_message(message)

        # Verify the methods were called
        self.adapter._is_command_topic.assert_called_once_with("solace/other/topic")

        # Verify the command handler was not called
        self.adapter.command_handler.assert_not_called()

    def test_handle_message_parse_error(self):
        """Test handling a message with a parse error."""
        # Mock the _is_command_topic method
        self.adapter._is_command_topic = MagicMock(return_value=True)

        # Mock the _parse_command_topic method to return None
        self.adapter._parse_command_topic = MagicMock(return_value=(None, None))

        # Mock the command handler
        self.adapter.command_handler = MagicMock()

        # Test data
        message = MagicMock()
        message.get_topic.return_value = "solace/sac-control/v1/invalid"

        # Call the method
        self.adapter.handle_message(message)

        # Verify the methods were called
        self.adapter._is_command_topic.assert_called_once_with(
            "solace/sac-control/v1/invalid"
        )
        self.adapter._parse_command_topic.assert_called_once_with(
            "solace/sac-control/v1/invalid"
        )

        # Verify the command handler was not called
        self.adapter.command_handler.assert_not_called()

    def test_handle_message_no_handler(self):
        """Test handling a message with no command handler."""
        # Mock the _is_command_topic method
        self.adapter._is_command_topic = MagicMock(return_value=True)

        # Mock the _parse_command_topic method
        self.adapter._parse_command_topic = MagicMock(return_value=("GET", "/test"))

        # Set the command handler to None
        self.adapter.command_handler = None

        # Test data
        message = MagicMock()
        message.get_topic.return_value = "solace/sac-control/v1/GET/test"

        # Call the method
        self.adapter.handle_message(message)

        # Verify the methods were called
        self.adapter._is_command_topic.assert_called_once_with(
            "solace/sac-control/v1/GET/test"
        )
        self.adapter._parse_command_topic.assert_called_once_with(
            "solace/sac-control/v1/GET/test"
        )

    def test_is_command_topic(self):
        """Test checking if a topic is a command topic."""
        # Test data
        valid_topic = "solace/sac-control/v1/GET/test"
        invalid_topic1 = "other/sac-control/v1/GET/test"
        invalid_topic2 = "solace/other/v1/GET/test"
        invalid_topic3 = "solace/sac-control/other/GET/test"
        invalid_topic4 = "solace/sac-control"

        # Call the method
        result1 = self.adapter._is_command_topic(valid_topic)
        result2 = self.adapter._is_command_topic(invalid_topic1)
        result3 = self.adapter._is_command_topic(invalid_topic2)
        result4 = self.adapter._is_command_topic(invalid_topic3)
        result5 = self.adapter._is_command_topic(invalid_topic4)

        # Verify the results
        self.assertTrue(result1)
        self.assertFalse(result2)
        self.assertFalse(result3)
        self.assertFalse(result4)
        self.assertFalse(result5)

    def test_parse_command_topic(self):
        """Test parsing a command topic."""
        # Test data
        topic1 = "solace/sac-control/v1/GET/test"
        topic2 = "solace/sac-control/v1/POST/test/resource"
        topic3 = "solace/sac-control/v1/PUT/test/resource/123"
        topic4 = "solace/sac-control/v1"

        # Call the method
        result1 = self.adapter._parse_command_topic(topic1)
        result2 = self.adapter._parse_command_topic(topic2)
        result3 = self.adapter._parse_command_topic(topic3)
        result4 = self.adapter._parse_command_topic(topic4)

        # Verify the results
        self.assertEqual(result1, ("GET", "/test"))
        self.assertEqual(result2, ("POST", "/test/resource"))
        self.assertEqual(result3, ("PUT", "/test/resource/123"))
        self.assertEqual(result4, (None, None))

    def test_create_request(self):
        """Test creating a request object."""
        # Test data
        method = "GET"
        endpoint = "/test"
        payload = {
            "request_id": "test-request-id",
            "query_params": {"filter": "all"},
            "body": {"data": "test"},
            "timestamp": "2023-01-01T00:00:00Z",
            "source": "test-source",
            "reply_to_topic_prefix": "test-prefix",
        }
        message = MagicMock()
        message.get_user_properties.return_value = {}

        # Call the method
        request = self.adapter._create_request(method, endpoint, payload, message)

        # Verify the request
        self.assertEqual(request["request_id"], "test-request-id")
        self.assertEqual(request["method"], method)
        self.assertEqual(request["endpoint"], endpoint)
        self.assertEqual(request["query_params"], {"filter": "all"})
        self.assertEqual(request["body"], {"data": "test"})
        self.assertEqual(request["timestamp"], "2023-01-01T00:00:00Z")
        self.assertEqual(request["source"], "test-source")
        self.assertEqual(request["reply_to_topic_prefix"], "test-prefix")

    def test_create_request_with_user_properties(self):
        """Test creating a request object with reply topic from user properties."""
        # Test data
        method = "GET"
        endpoint = "/test"
        payload = {
            "request_id": "test-request-id",
            "query_params": {"filter": "all"},
            "body": {"data": "test"},
        }
        message = MagicMock()
        message.get_user_properties.return_value = {
            "reply_to_topic_prefix": "user-prefix"
        }

        # Call the method
        request = self.adapter._create_request(method, endpoint, payload, message)

        # Verify the request
        self.assertEqual(request["reply_to_topic_prefix"], "user-prefix")

    def test_publish_response(self):
        """Test publishing a response."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        response = {
            "request_id": "test-request-id",
            "status_code": 200,
            "body": {"result": "success"},
            "reply_to_topic_prefix": "test-prefix",
        }

        # Call the method
        self.adapter.publish_response(response)

        # Verify the connector was called
        self.adapter.connector.send_message_to_flow.assert_called_once()
        flow_name, message = self.adapter.connector.send_message_to_flow.call_args[0]
        self.assertEqual(flow_name, "response-flow")
        self.assertIsInstance(message, Message)
        self.assertEqual(
            message.get_topic(), "test-prefix/sac-control/v1/response/test-request-id"
        )
        self.assertEqual(message.get_payload(), response)

    def test_publish_response_no_flow(self):
        """Test publishing a response with no response flow."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name to None
        self.adapter.response_flow_name = None

        # Test data
        response = {
            "request_id": "test-request-id",
            "status_code": 200,
            "body": {"result": "success"},
            "reply_to_topic_prefix": "test-prefix",
        }

        # Call the method
        self.adapter.publish_response(response)

        # Verify the connector was not called
        self.adapter.connector.send_message_to_flow.assert_not_called()

    def test_publish_response_no_reply_prefix(self):
        """Test publishing a response with no reply topic prefix."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        response = {
            "request_id": "test-request-id",
            "status_code": 200,
            "body": {"result": "success"},
        }

        # Call the method
        self.adapter.publish_response(response)

        # Verify the connector was not called
        self.adapter.connector.send_message_to_flow.assert_not_called()

    def test_publish_status(self):
        """Test publishing a status update."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        status = "running"
        details = {"uptime": 100}

        # Call the method
        self.adapter.publish_status(entity_id, entity_type, status, details)

        # Verify the connector was called
        self.adapter.connector.send_message_to_flow.assert_called_once()
        flow_name, message = self.adapter.connector.send_message_to_flow.call_args[0]
        self.assertEqual(flow_name, "response-flow")
        self.assertIsInstance(message, Message)
        self.assertEqual(
            message.get_topic(), "solace/sac-control/v1/status/test-entity"
        )
        payload = message.get_payload()
        self.assertEqual(payload["entity_id"], entity_id)
        self.assertEqual(payload["entity_type"], entity_type)
        self.assertEqual(payload["status"], status)
        self.assertEqual(payload["details"], details)
        self.assertIn("timestamp", payload)

    def test_publish_metrics(self):
        """Test publishing metrics."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        metrics = {"metric1": {"value": 100}}

        # Call the method
        self.adapter.publish_metrics(entity_id, entity_type, metrics)

        # Verify the connector was called
        self.adapter.connector.send_message_to_flow.assert_called_once()
        flow_name, message = self.adapter.connector.send_message_to_flow.call_args[0]
        self.assertEqual(flow_name, "response-flow")
        self.assertIsInstance(message, Message)
        self.assertEqual(
            message.get_topic(), "solace/sac-control/v1/metrics/test-entity"
        )
        payload = message.get_payload()
        self.assertEqual(payload["entity_id"], entity_id)
        self.assertEqual(payload["entity_type"], entity_type)
        self.assertEqual(payload["metrics"], metrics)
        self.assertIn("timestamp", payload)

    def test_publish_registry(self):
        """Test publishing the entity registry."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        instance_id = "test-instance"
        entities = {
            "entity1": {
                "entity_id": "entity1",
                "entity_type": "test-type",
                "entity_name": "Entity 1",
                "endpoints": [{"path": "/test", "methods": {"GET": {}}}],
            }
        }

        # Call the method
        self.adapter.publish_registry(instance_id, entities)

        # Verify the connector was called
        self.adapter.connector.send_message_to_flow.assert_called_once()
        flow_name, message = self.adapter.connector.send_message_to_flow.call_args[0]
        self.assertEqual(flow_name, "response-flow")
        self.assertIsInstance(message, Message)
        self.assertEqual(message.get_topic(), "solace/sac-control/v1/registry")
        payload = message.get_payload()
        self.assertEqual(payload["instance_id"], instance_id)
        self.assertIn("entities", payload)
        self.assertEqual(len(payload["entities"]), 1)
        self.assertEqual(payload["entities"][0]["entity_id"], "entity1")
        self.assertEqual(payload["entities"][0]["entity_type"], "test-type")
        self.assertEqual(payload["entities"][0]["entity_name"], "Entity 1")
        self.assertIn("endpoints", payload["entities"][0])
        self.assertEqual(len(payload["entities"][0]["endpoints"]), 1)
        self.assertEqual(payload["entities"][0]["endpoints"][0]["path"], "/test")
        self.assertEqual(payload["entities"][0]["endpoints"][0]["methods"], ["GET"])
        self.assertIn("timestamp", payload)

    def test_publish_trace(self):
        """Test publishing a trace event."""
        # Mock the connector
        self.adapter.connector.send_message_to_flow = MagicMock()

        # Set the response flow name
        self.adapter.response_flow_name = "response-flow"

        # Test data
        entity_id = "test-entity"
        trace_level = "INFO"
        trace_event = {
            "entity_id": entity_id,
            "trace_level": trace_level,
            "operation": "test-operation",
            "stage": "start",
            "timestamp": "2023-01-01T00:00:00Z",
        }

        # Call the method
        self.adapter.publish_trace(entity_id, trace_level, trace_event)

        # Verify the connector was called
        self.adapter.connector.send_message_to_flow.assert_called_once()
        flow_name, message = self.adapter.connector.send_message_to_flow.call_args[0]
        self.assertEqual(flow_name, "response-flow")
        self.assertIsInstance(message, Message)
        self.assertEqual(
            message.get_topic(), "solace/sac-control/v1/trace/test-entity/INFO"
        )
        self.assertEqual(message.get_payload(), trace_event)


if __name__ == "__main__":
    unittest.main()
