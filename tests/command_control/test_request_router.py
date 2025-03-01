"""Unit tests for the RequestRouter class."""

import unittest
from unittest.mock import MagicMock, patch

from src.solace_ai_connector.command_control.request_router import RequestRouter


class TestRequestRouter(unittest.TestCase):
    """Test cases for the RequestRouter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.entity_registry = MagicMock()
        self.router = RequestRouter(self.entity_registry)

    def test_init(self):
        """Test initialization of RequestRouter."""
        self.assertEqual(self.router.entity_registry,  self.entity_registry)
        self.assertIsNotNone(self.router.schema_validator)

    def test_route_request_success(self):
        """Test routing a request successfully."""
        # Mock the entity registry
        handler_info = {
            "handler": MagicMock(return_value={"result": "success"})
        }
        path_params = {"id": "123"}
        entity_id = "test-entity"
        self.entity_registry.find_endpoint_handler = MagicMock(
            return_value=(handler_info, path_params, entity_id)
        )
        
        # Mock the entity
        entity = {"entity_id": entity_id, "entity_name": "Test Entity"}
        self.entity_registry.get_entity = MagicMock(return_value=entity)
        
        # Mock the validation
        self.router._validate_parameters = MagicMock(return_value=None)
        
        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test/123",
            "query_params": {"filter": "all"},
            "body": None,
            "timestamp": "2023-01-01T00:00:00Z",
            "source": "test"
        }
        
        # Call the method
        response = self.router.route_request(request)
        
        # Verify the response
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["body"], {"result": "success"})
        
        # Verify the entity registry was called
        self.entity_registry.find_endpoint_handler.assert_called_once_with(
            "/test/123", "GET"
        )
        
        # Verify the entity was retrieved
        self.entity_registry.get_entity.assert_called_once_with(entity_id)
        
        # Verify the validation was called
        self.router._validate_parameters.assert_called_once_with(
            handler_info, path_params, {"filter": "all"}, None
        )
        
        # Verify the handler was called
        handler_info["handler"].assert_called_once()
        call_kwargs = handler_info["handler"].call_args[1]
        self.assertEqual(call_kwargs["path_params"], path_params)
        self.assertEqual(call_kwargs["query_params"], {"filter": "all"})
        self.assertEqual(call_kwargs["body"], None)
        self.assertIn("context", call_kwargs)
        self.assertEqual(call_kwargs["context"]["request_id"], "test-request-id")
        self.assertEqual(call_kwargs["context"]["entity_id"], entity_id)
        self.assertEqual(call_kwargs["context"]["entity"], entity)
        self.assertEqual(call_kwargs["context"]["timestamp"], "2023-01-01T00:00:00Z")
        self.assertEqual(call_kwargs["context"]["source"], "test")

    def test_route_request_no_handler(self):
        """Test routing a request with no handler found."""
        # Mock the entity registry
        self.entity_registry.find_endpoint_handler = MagicMock(
            return_value=(None, None, None)
        )
        
        # Mock the _create_error_response method
        self.router._create_error_response = MagicMock(
            return_value={"status_code": 404, "body": {"error": "Not found"}}
        )
        
        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test/123"
        }
        
        # Call the method
        response = self.router.route_request(request)
        
        # Verify the response
        self.assertEqual(response["status_code"], 404)
        
        # Verify the entity registry was called
        self.entity_registry.find_endpoint_handler.assert_called_once_with(
            "/test/123", "GET"
        )
        
        # Verify _create_error_response was called
        self.router._create_error_response.assert_called_once_with(
            "test-request-id", 404, "No handler found for GET /test/123"
        )

    def test_route_request_no_entity(self):
        """Test routing a request with no entity found."""
        # Mock the entity registry
        handler_info = {
            "handler": MagicMock(return_value={"result": "success"})
        }
        path_params = {"id": "123"}
        entity_id = "test-entity"
        self.entity_registry.find_endpoint_handler = MagicMock(
            return_value=(handler_info, path_params, entity_id)
        )
        
        # Mock the entity registry to return None for the entity
        self.entity_registry.get_entity = MagicMock(return_value=None)
        
        # Mock the _create_error_response method
        self.router._create_error_response = MagicMock(
            return_value={"status_code": 500, "body": {"error": "Entity not found"}}
        )
        
        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test/123"
        }
        
        # Call the method
        response = self.router.route_request(request)
        
        # Verify the response
        self.assertEqual(response["status_code"], 500)
        
        # Verify the entity registry was called
        self.entity_registry.find_endpoint_handler.assert_called_once_with(
            "/test/123", "GET"
        )
        
        # Verify the entity was retrieved
        self.entity_registry.get_entity.assert_called_once_with(entity_id)
        
        # Verify _create_error_response was called
        self.router._create_error_response.assert_called_once_with(
            "test-request-id", 500, f"Entity {entity_id} not found"
        )

    def test_route_request_validation_error(self):
        """Test routing a request with validation errors."""
        # Mock the entity registry
        handler_info = {
            "handler": MagicMock(return_value={"result": "success"})
        }
        path_params = {"id": "123"}
        entity_id = "test-entity"
        self.entity_registry.find_endpoint_handler = MagicMock(
            return_value=(handler_info, path_params, entity_id)
        )
        
        # Mock the entity
        entity = {"entity_id": entity_id, "entity_name": "Test Entity"}
        self.entity_registry.get_entity = MagicMock(return_value=entity)
        
        # Mock the validation to return an error
        validation_error = "Invalid parameter"
        self.router._validate_parameters = MagicMock(return_value=validation_error)
        
        # Mock the _create_error_response method
        self.router._create_error_response = MagicMock(
            return_value={"status_code": 400, "body": {"error": validation_error}}
        )
        
        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test/123",
            "query_params": {"filter": "all"},
            "body": None
        }
        
        # Call the method
        response = self.router.route_request(request)
        
        # Verify the response
        self.assertEqual(response["status_code"], 400)
        
        # Verify the validation was called
        self.router._validate_parameters.assert_called_once_with(
            handler_info, path_params, {"filter": "all"}, None
        )
        
        # Verify _create_error_response was called
        self.router._create_error_response.assert_called_once_with(
            "test-request-id", 400, f"Parameter validation failed: {validation_error}"
        )
        
        # Verify the handler was not called
        handler_info["handler"].assert_not_called()

    def test_route_request_handler_exception(self):
        """Test routing a request where the handler raises an exception."""
        # Mock the entity registry
        handler_info = {
            "handler": MagicMock(side_effect=Exception("Test exception"))
        }
        path_params = {"id": "123"}
        entity_id = "test-entity"
        self.entity_registry.find_endpoint_handler = MagicMock(
            return_value=(handler_info, path_params, entity_id)
        )
        
        # Mock the entity
        entity = {"entity_id": entity_id, "entity_name": "Test Entity"}
        self.entity_registry.get_entity = MagicMock(return_value=entity)
        
        # Mock the validation
        self.router._validate_parameters = MagicMock(return_value=None)
        
        # Mock the _create_error_response method
        self.router._create_error_response = MagicMock(
            return_value={"status_code": 500, "body": {"error": "Internal server error"}}
        )
        
        # Test data
        request = {
            "request_id": "test-request-id",
            "method": "GET",
            "endpoint": "/test/123"
        }
        
        # Call the method
        response = self.router.route_request(request)
        
        # Verify the response
        self.assertEqual(response["status_code"], 500)
        
        # Verify the handler was called
        handler_info["handler"].assert_called_once()
        
        # Verify _create_error_response was called
        self.router._create_error_response.assert_called_once_with(
            "test-request-id", 500, "Error processing request: Test exception"
        )

    def test_validate_parameters(self):
        """Test validating parameters."""
        # Mock the schema validator
        self.router.schema_validator.validate_path_params = MagicMock(return_value=None)
        self.router.schema_validator.validate_query_params = MagicMock(return_value=None)
        self.router.schema_validator.validate_request_body = MagicMock(return_value=None)
        
        # Test data
        handler_info = {
            "path_params": {"id": {"type": "string", "required": True}},
            "query_params": {"filter": {"type": "string"}},
            "request_body_schema": {"type": "object"}
        }
        path_params = {"id": "123"}
        query_params = {"filter": "all"}
        body = {"data": "test"}
        
        # Call the method
        result = self.router._validate_parameters(handler_info, path_params, query_params, body)
        
        # Verify the result
        self.assertIsNone(result)
        
        # Verify the schema validator was called
        self.router.schema_validator.validate_path_params.assert_called_once_with(
            path_params, handler_info["path_params"]
        )
        self.router.schema_validator.validate_query_params.assert_called_once_with(
            query_params, handler_info["query_params"]
        )
        self.router.schema_validator.validate_request_body.assert_called_once_with(
            body, handler_info["request_body_schema"]
        )

    def test_validate_parameters_path_error(self):
        """Test validating parameters with a path parameter error."""
        # Mock the schema validator
        path_error = "Invalid path parameter"
        self.router.schema_validator.validate_path_params = MagicMock(return_value=path_error)
        
        # Test data
        handler_info = {
            "path_params": {"id": {"type": "string", "required": True}}
        }
        path_params = {}
        
        # Call the method
        result = self.router._validate_parameters(handler_info, path_params, {}, None)
        
        # Verify the result
        self.assertEqual(result, path_error)

    def test_validate_parameters_query_error(self):
        """Test validating parameters with a query parameter error."""
        # Mock the schema validator
        self.router.schema_validator.validate_path_params = MagicMock(return_value=None)
        query_error = "Invalid query parameter"
        self.router.schema_validator.validate_query_params = MagicMock(return_value=query_error)
        
        # Test data
        handler_info = {
            "path_params": {"id": {"type": "string", "required": True}},
            "query_params": {"filter": {"type": "string", "enum": ["all", "active"]}}
        }
        path_params = {"id": "123"}
        query_params = {"filter": "invalid"}
        
        # Call the method
        result = self.router._validate_parameters(handler_info, path_params, query_params, None)
        
        # Verify the result
        self.assertEqual(result, query_error)

    def test_validate_parameters_body_error(self):
        """Test validating parameters with a request body error."""
        # Mock the schema validator
        self.router.schema_validator.validate_path_params = MagicMock(return_value=None)
        self.router.schema_validator.validate_query_params = MagicMock(return_value=None)
        body_error = "Invalid request body"
        self.router.schema_validator.validate_request_body = MagicMock(return_value=body_error)
        
        # Test data
        handler_info = {
            "path_params": {"id": {"type": "string", "required": True}},
            "query_params": {"filter": {"type": "string"}},
            "request_body_schema": {"type": "object", "required": ["name"]}
        }
        path_params = {"id": "123"}
        query_params = {"filter": "all"}
        body = {}
        
        # Call the method
        result = self.router._validate_parameters(handler_info, path_params, query_params, body)
        
        # Verify the result
        self.assertEqual(result, body_error)

    def test_create_response(self):
        """Test creating a response."""
        # Test data
        request_id = "test-request-id"
        status_code = 200
        status_message = "OK"
        body = {"result": "success"}
        
        # Call the method
        response = self.router._create_response(request_id, status_code, status_message, body)
        
        # Verify the response
        self.assertEqual(response["request_id"], request_id)
        self.assertEqual(response["status_code"], status_code)
        self.assertEqual(response["status_message"], status_message)
        self.assertEqual(response["headers"]["content-type"], "application/json")
        self.assertEqual(response["body"], body)
        self.assertIn("timestamp", response)

    def test_create_error_response(self):
        """Test creating an error response."""
        # Test data
        request_id = "test-request-id"
        status_code = 400
        message = "Bad request"
        
        # Call the method
        response = self.router._create_error_response(request_id, status_code, message)
        
        # Verify the response
        self.assertEqual(response["request_id"], request_id)
        self.assertEqual(response["status_code"], status_code)
        self.assertEqual(response["status_message"], message)
        self.assertEqual(response["body"]["error"], message)


if __name__ == "__main__":
    unittest.main()
