"""Unit tests for the CommandControlService class."""

import unittest
from unittest.mock import MagicMock, patch
import datetime

from src.solace_ai_connector.command_control.command_control_service import CommandControlService
from src.solace_ai_connector.command_control.tracing import TracingSystem


class TestCommandControlService(unittest.TestCase):
    """Test cases for the CommandControlService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.connector = MagicMock()
        self.broker_adapter = MagicMock()
        self.connector.broker_adapter = self.broker_adapter
        self.service = CommandControlService(self.connector)
        # Replace the UUID with a fixed value for testing
        self.service.instance_id = "test-instance-id"

    def test_init(self):
        """Test initialization of CommandControlService."""
        self.assertIsNotNone(self.service.entity_registry)
        self.assertIsNotNone(self.service.request_router)
        self.assertEqual(self.service.instance_id, "test-instance-id")
        self.assertEqual(self.service.connector, self.connector)
        self.assertIsNotNone(self.service.tracing_system)

    def test_register_entity(self):
        """Test registering an entity."""
        # Mock the entity registry
        self.service.entity_registry.register_entity = MagicMock(return_value=True)
        self.service.publish_registry = MagicMock()
        self.service.emit_trace = MagicMock()

        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        entity_name = "Test Entity"
        description = "Test description"
        version = "1.0.0"
        parent_entity_id = "parent-entity"
        endpoints = [{"path": "/test", "methods": {"GET": {}}}]
        status_attributes = [{"name": "status", "description": "Status"}]
        metrics = [{"name": "metric", "description": "Metric"}]
        configuration = {"config": "value"}

        # Call the method
        result = self.service.register_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            description=description,
            version=version,
            parent_entity_id=parent_entity_id,
            endpoints=endpoints,
            status_attributes=status_attributes,
            metrics=metrics,
            configuration=configuration
        )

        # Verify the result
        self.assertTrue(result)
        
        # Verify the entity registry was called with the correct data
        self.service.entity_registry.register_entity.assert_called_once()
        call_args = self.service.entity_registry.register_entity.call_args[0][0]
        self.assertEqual(call_args["entity_id"], entity_id)
        self.assertEqual(call_args["entity_type"], entity_type)
        self.assertEqual(call_args["entity_name"], entity_name)
        self.assertEqual(call_args["description"], description)
        self.assertEqual(call_args["version"], version)
        self.assertEqual(call_args["parent_entity_id"], parent_entity_id)
        self.assertEqual(call_args["endpoints"], endpoints)
        self.assertEqual(call_args["status_attributes"], status_attributes)
        self.assertEqual(call_args["metrics"], metrics)
        self.assertEqual(call_args["configuration"], configuration)
        
        # Verify publish_registry was called
        self.service.publish_registry.assert_called_once()
        
        # Verify emit_trace was called
        self.service.emit_trace.assert_called_once()

    def test_register_entity_failure(self):
        """Test registering an entity with failure."""
        # Mock the entity registry to return False
        self.service.entity_registry.register_entity = MagicMock(return_value=False)
        self.service.publish_registry = MagicMock()
        self.service.emit_trace = MagicMock()

        # Call the method
        result = self.service.register_entity(
            entity_id="test-entity",
            entity_type="test-type",
            entity_name="Test Entity",
            description="Test description",
            version="1.0.0"
        )

        # Verify the result
        self.assertFalse(result)
        
        # Verify publish_registry was not called
        self.service.publish_registry.assert_not_called()
        
        # Verify emit_trace was not called
        self.service.emit_trace.assert_not_called()

    def test_handle_request_valid(self):
        """Test handling a valid request."""
        # Mock the request router
        expected_response = {"status_code": 200, "body": {"result": "success"}}
        self.service.request_router.route_request = MagicMock(return_value=expected_response)
        
        # Mock the tracing system
        self.service.tracing_system = MagicMock()
        mock_trace_context = MagicMock()
        mock_trace_context.__enter__ = MagicMock(return_value=mock_trace_context)
        mock_trace_context.__exit__ = MagicMock(return_value=False)
        mock_trace_context.progress = MagicMock()
        self.service.tracing_system.create_trace_context = MagicMock(return_value=mock_trace_context)

        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test",
            "query_params": {},
            "body": None
        }

        # Call the method
        response = self.service.handle_request(request)

        # Verify the response
        self.assertEqual(response, expected_response)
        
        # Verify the request router was called
        self.service.request_router.route_request.assert_called_once_with(request)
        
        # Verify the trace context was created and used
        self.service.tracing_system.create_trace_context.assert_called_once()
        mock_trace_context.__enter__.assert_called_once()
        mock_trace_context.__exit__.assert_called_once()
        mock_trace_context.progress.assert_called_once()

    def test_handle_request_invalid(self):
        """Test handling an invalid request."""
        # Mock the _validate_request method to return False
        self.service._validate_request = MagicMock(return_value=False)
        self.service._create_error_response = MagicMock(return_value={"status_code": 400})
        
        # Mock the tracing system
        self.service.tracing_system = MagicMock()
        mock_trace_context = MagicMock()
        mock_trace_context.__enter__ = MagicMock(return_value=mock_trace_context)
        mock_trace_context.__exit__ = MagicMock(return_value=False)
        self.service.tracing_system.create_trace_context = MagicMock(return_value=mock_trace_context)

        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test"
        }

        # Call the method
        response = self.service.handle_request(request)

        # Verify the response
        self.assertEqual(response["status_code"], 400)
        
        # Verify _create_error_response was called
        self.service._create_error_response.assert_called_once()

    def test_handle_request_exception(self):
        """Test handling a request that raises an exception."""
        # Mock the request router to raise an exception
        self.service.request_router.route_request = MagicMock(side_effect=Exception("Test exception"))
        self.service._create_error_response = MagicMock(return_value={"status_code": 500})
        
        # Mock the tracing system
        self.service.tracing_system = MagicMock()
        mock_trace_context = MagicMock()
        mock_trace_context.__enter__ = MagicMock(return_value=mock_trace_context)
        mock_trace_context.__exit__ = MagicMock(return_value=False)
        self.service.tracing_system.create_trace_context = MagicMock(return_value=mock_trace_context)

        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test",
            "query_params": {},
            "body": None
        }

        # Call the method
        response = self.service.handle_request(request)

        # Verify the response
        self.assertEqual(response["status_code"], 500)
        
        # Verify _create_error_response was called
        self.service._create_error_response.assert_called_once()

    def test_validate_request(self):
        """Test validating a request."""
        # Valid request
        valid_request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test"
        }
        self.assertTrue(self.service._validate_request(valid_request))
        
        # Invalid request - missing request_id
        invalid_request1 = {
            "method": "GET",
            "endpoint": "/test"
        }
        self.assertFalse(self.service._validate_request(invalid_request1))
        
        # Invalid request - missing method
        invalid_request2 = {
            "request_id": "test-request-id",
            "endpoint": "/test"
        }
        self.assertFalse(self.service._validate_request(invalid_request2))
        
        # Invalid request - missing endpoint
        invalid_request3 = {
            "request_id": "test-request-id",
            "method": "GET"
        }
        self.assertFalse(self.service._validate_request(invalid_request3))

    def test_create_error_response(self):
        """Test creating an error response."""
        # Test data
        request_id = "test-request-id"
        status_code = 400
        message = "Bad request"
        
        # Call the method
        response = self.service._create_error_response(request_id, status_code, message)
        
        # Verify the response
        self.assertEqual(response["request_id"], request_id)
        self.assertEqual(response["status_code"], status_code)
        self.assertEqual(response["status_message"], message)
        self.assertEqual(response["headers"]["content-type"], "application/json")
        self.assertEqual(response["body"]["error"], message)
        self.assertIn("timestamp", response)

    def test_emit_trace(self):
        """Test emitting a trace event."""
        # Mock the tracing system
        self.service.tracing_system = MagicMock()
        
        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        trace_level = "INFO"
        operation = "test-operation"
        stage = "start"
        request_id = "test-request-id"
        data = {"test": "data"}
        error = {"message": "error"}
        duration_ms = 100
        
        # Call the method
        self.service.emit_trace(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            stage=stage,
            request_id=request_id,
            data=data,
            error=error,
            duration_ms=duration_ms
        )
        
        # Verify the tracing system was called
        self.service.tracing_system.emit_trace.assert_called_once_with(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            stage=stage,
            request_id=request_id,
            data=data,
            error=error,
            duration_ms=duration_ms
        )

    def test_publish_status(self):
        """Test publishing a status update."""
        # Mock the broker adapter
        self.service.broker_adapter = MagicMock()
        
        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        status = "running"
        details = {"uptime": 100}
        
        # Call the method
        self.service.publish_status(entity_id, entity_type, status, details)
        
        # Verify the broker adapter was called
        self.service.broker_adapter.publish_status.assert_called_once_with(
            entity_id, entity_type, status, details
        )

    def test_publish_metrics(self):
        """Test publishing metrics."""
        # Mock the broker adapter
        self.service.broker_adapter = MagicMock()
        
        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        metrics = {"metric1": {"value": 100}}
        
        # Call the method
        self.service.publish_metrics(entity_id, entity_type, metrics)
        
        # Verify the broker adapter was called
        self.service.broker_adapter.publish_metrics.assert_called_once_with(
            entity_id, entity_type, metrics
        )

    def test_publish_registry(self):
        """Test publishing the entity registry."""
        # Mock the broker adapter
        self.service.broker_adapter = MagicMock()
        
        # Mock the entity registry
        entities = {"entity1": {"name": "Entity 1"}}
        self.service.entity_registry.get_all_entities = MagicMock(return_value=entities)
        
        # Call the method
        self.service.publish_registry()
        
        # Verify the broker adapter was called
        self.service.broker_adapter.publish_registry.assert_called_once_with(
            self.service.instance_id, entities
        )

    def test_get_trace_configuration(self):
        """Test getting the trace configuration."""
        # Mock the tracing system
        expected_config = {
            "enabled": True,
            "default_level": "INFO",
            "entity_levels": {"entity1": "DEBUG"}
        }
        self.service.tracing_system.get_configuration = MagicMock(return_value=expected_config)
        
        # Call the method
        config = self.service.get_trace_configuration()
        
        # Verify the result
        self.assertEqual(config, expected_config)
        
        # Test with no tracing system
        self.service.tracing_system = None
        config = self.service.get_trace_configuration()
        self.assertEqual(config["enabled"], False)
        self.assertEqual(config["default_level"], "INFO")
        self.assertEqual(config["entity_levels"], {})

    def test_get_entity_trace_configuration(self):
        """Test getting the trace configuration for a specific entity."""
        # Mock the tracing system
        expected_config = {
            "entity_id": "entity1",
            "enabled": True,
            "level": "DEBUG"
        }
        self.service.tracing_system.get_entity_configuration = MagicMock(return_value=expected_config)
        
        # Call the method
        config = self.service.get_entity_trace_configuration("entity1")
        
        # Verify the result
        self.assertEqual(config, expected_config)
        
        # Test with no tracing system
        self.service.tracing_system = None
        config = self.service.get_entity_trace_configuration("entity1")
        self.assertEqual(config["entity_id"], "entity1")
        self.assertEqual(config["enabled"], False)
        self.assertEqual(config["level"], "INFO")

    def test_update_trace_configuration(self):
        """Test updating the trace configuration."""
        # Mock the tracing system
        self.service.tracing_system.update_configuration = MagicMock(return_value=True)
        
        # Test data
        config = {
            "enabled": True,
            "default_level": "DEBUG",
            "entity_levels": {"entity1": "INFO"}
        }
        
        # Call the method
        result = self.service.update_trace_configuration(config)
        
        # Verify the result
        self.assertTrue(result)
        self.service.tracing_system.update_configuration.assert_called_once_with(config)
        
        # Test with no tracing system
        self.service.tracing_system = None
        result = self.service.update_trace_configuration(config)
        self.assertFalse(result)

    def test_create_trace_context(self):
        """Test creating a trace context."""
        # Mock the tracing system
        mock_context = MagicMock()
        self.service.tracing_system.create_trace_context = MagicMock(return_value=mock_context)
        
        # Test data
        entity_id = "test-entity"
        entity_type = "test-type"
        trace_level = "INFO"
        operation = "test-operation"
        request_id = "test-request-id"
        data = {"test": "data"}
        
        # Call the method
        context = self.service.create_trace_context(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            request_id=request_id,
            data=data
        )
        
        # Verify the result
        self.assertEqual(context, mock_context)
        self.service.tracing_system.create_trace_context.assert_called_once_with(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            request_id=request_id,
            data=data
        )
        
        # Test with no tracing system
        self.service.tracing_system = None
        context = self.service.create_trace_context(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            request_id=request_id,
            data=data
        )
        self.assertIsNotNone(context)


if __name__ == "__main__":
    unittest.main()
