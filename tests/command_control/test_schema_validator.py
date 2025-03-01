"""Unit tests for the SchemaValidator class."""

import unittest
from unittest.mock import MagicMock, patch

from src.solace_ai_connector.command_control.schema_validator import SchemaValidator


class TestSchemaValidator(unittest.TestCase):
    """Test cases for the SchemaValidator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = SchemaValidator()

    def test_validate_path_params_valid(self):
        """Test validating valid path parameters."""
        # Test data
        params = {
            "id": "123",
            "name": "test"
        }
        schema = {
            "id": {
                "type": "string",
                "required": True
            },
            "name": {
                "type": "string",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_path_params(params, schema)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_path_params_missing_required(self):
        """Test validating path parameters with a missing required parameter."""
        # Test data
        params = {
            "name": "test"
        }
        schema = {
            "id": {
                "type": "string",
                "required": True
            },
            "name": {
                "type": "string",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_path_params(params, schema)
        
        # Verify the result
        self.assertEqual(result, "Required path parameter 'id' is missing")

    def test_validate_path_params_invalid_type(self):
        """Test validating path parameters with an invalid type."""
        # Test data
        params = {
            "id": "abc",
            "count": "not-a-number"
        }
        schema = {
            "id": {
                "type": "string",
                "required": True
            },
            "count": {
                "type": "number",
                "required": True
            }
        }
        
        # Call the method
        result = self.validator.validate_path_params(params, schema)
        
        # Verify the result
        self.assertEqual(result, "Path parameter 'count' must be a number")

    def test_validate_path_params_no_schema(self):
        """Test validating path parameters with no schema."""
        # Test data
        params = {
            "id": "123",
            "name": "test"
        }
        
        # Call the method
        result = self.validator.validate_path_params(params, None)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_query_params_valid(self):
        """Test validating valid query parameters."""
        # Test data
        params = {
            "filter": "all",
            "page": "1"
        }
        schema = {
            "filter": {
                "type": "string",
                "required": True,
                "enum": ["all", "active", "inactive"]
            },
            "page": {
                "type": "integer",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_query_params(params, schema)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_query_params_missing_required(self):
        """Test validating query parameters with a missing required parameter."""
        # Test data
        params = {
            "page": "1"
        }
        schema = {
            "filter": {
                "type": "string",
                "required": True
            },
            "page": {
                "type": "integer",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_query_params(params, schema)
        
        # Verify the result
        self.assertEqual(result, "Required query parameter 'filter' is missing")

    def test_validate_query_params_invalid_type(self):
        """Test validating query parameters with an invalid type."""
        # Test data
        params = {
            "filter": "all",
            "page": "not-a-number"
        }
        schema = {
            "filter": {
                "type": "string",
                "required": True
            },
            "page": {
                "type": "integer",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_query_params(params, schema)
        
        # Verify the result
        self.assertEqual(result, "Query parameter 'page' must be an integer")

    def test_validate_query_params_invalid_enum(self):
        """Test validating query parameters with an invalid enum value."""
        # Test data
        params = {
            "filter": "invalid",
            "page": "1"
        }
        schema = {
            "filter": {
                "type": "string",
                "required": True,
                "enum": ["all", "active", "inactive"]
            },
            "page": {
                "type": "integer",
                "required": False
            }
        }
        
        # Call the method
        result = self.validator.validate_query_params(params, schema)
        
        # Verify the result
        self.assertEqual(result, "Query parameter 'filter' must be one of: ['all', 'active', 'inactive']")

    def test_validate_query_params_no_schema(self):
        """Test validating query parameters with no schema."""
        # Test data
        params = {
            "filter": "all",
            "page": "1"
        }
        
        # Call the method
        result = self.validator.validate_query_params(params, None)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_request_body_valid(self):
        """Test validating a valid request body."""
        # Test data
        body = {
            "name": "Test",
            "age": 30,
            "active": True
        }
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_request_body_missing_required(self):
        """Test validating a request body with a missing required property."""
        # Test data
        body = {
            "age": 30,
            "active": True
        }
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertEqual(result, "Required property 'name' is missing from request body")

    def test_validate_request_body_invalid_type(self):
        """Test validating a request body with an invalid property type."""
        # Test data
        body = {
            "name": "Test",
            "age": "thirty",
            "active": True
        }
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertEqual(result, "Property 'age' must be an integer")

    def test_validate_request_body_invalid_body_type(self):
        """Test validating a request body with an invalid body type."""
        # Test data
        body = "not-an-object"
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertEqual(result, "Request body must be an object")

    def test_validate_request_body_required_but_missing(self):
        """Test validating a request body that is required but not provided."""
        # Test data
        body = None
        schema = {
            "required": True,
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertEqual(result, "Request body is required but not provided")

    def test_validate_request_body_not_required_and_missing(self):
        """Test validating a request body that is not required and not provided."""
        # Test data
        body = None
        schema = {
            "required": False,
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, schema)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_request_body_no_schema(self):
        """Test validating a request body with no schema."""
        # Test data
        body = {
            "name": "Test",
            "age": 30
        }
        
        # Call the method
        result = self.validator.validate_request_body(body, None)
        
        # Verify the result
        self.assertIsNone(result)

    def test_validate_response_body(self):
        """Test validating a response body."""
        # Mock the validate_request_body method
        self.validator.validate_request_body = MagicMock(return_value=None)
        
        # Test data
        body = {"result": "success"}
        schema = {"type": "object"}
        
        # Call the method
        result = self.validator.validate_response_body(body, schema)
        
        # Verify the result
        self.assertIsNone(result)
        
        # Verify validate_request_body was called
        self.validator.validate_request_body.assert_called_once_with(body, schema)


if __name__ == "__main__":
    unittest.main()
