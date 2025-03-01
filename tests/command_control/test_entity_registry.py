"""Unit tests for the EntityRegistry class."""

import unittest
import re
from unittest.mock import MagicMock, patch

from src.solace_ai_connector.command_control.entity_registry import EntityRegistry


class TestEntityRegistry(unittest.TestCase):
    """Test cases for the EntityRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = EntityRegistry()

    def test_init(self):
        """Test initialization of EntityRegistry."""
        self.assertEqual(self.registry.entities, {})
        self.assertEqual(self.registry.endpoints, {})
        self.assertEqual(self.registry.endpoint_patterns, {})

    def test_register_entity(self):
        """Test registering an entity."""
        # Test data
        entity_data = {
            "entity_id": "test-entity",
            "entity_type": "test-type",
            "entity_name": "Test Entity",
            "description": "Test description",
            "version": "1.0.0",
            "endpoints": [
                {
                    "path": "/test",
                    "methods": {
                        "GET": {
                            "description": "Get test",
                            "handler": lambda: "test"
                        }
                    }
                }
            ]
        }

        # Mock the _register_endpoint method
        self.registry._register_endpoint = MagicMock()

        # Call the method
        result = self.registry.register_entity(entity_data)

        # Verify the result
        self.assertTrue(result)
        
        # Verify the entity was added to the registry
        self.assertIn("test-entity", self.registry.entities)
        self.assertEqual(self.registry.entities["test-entity"], entity_data)
        
        # Verify _register_endpoint was called for each endpoint
        self.registry._register_endpoint.assert_called_once_with(
            "test-entity", entity_data["endpoints"][0]
        )

    def test_register_entity_no_id(self):
        """Test registering an entity with no ID."""
        # Test data
        entity_data = {
            "entity_type": "test-type",
            "entity_name": "Test Entity"
        }

        # Call the method
        result = self.registry.register_entity(entity_data)

        # Verify the result
        self.assertFalse(result)
        
        # Verify no entity was added to the registry
        self.assertEqual(self.registry.entities, {})

    def test_register_entity_exception(self):
        """Test registering an entity that raises an exception."""
        # Test data
        entity_data = {
            "entity_id": "test-entity",
            "entity_type": "test-type",
            "entity_name": "Test Entity",
            "endpoints": [{"invalid": "endpoint"}]
        }

        # Mock the _register_endpoint method to raise an exception
        self.registry._register_endpoint = MagicMock(side_effect=Exception("Test exception"))

        # Call the method
        result = self.registry.register_entity(entity_data)

        # Verify the result
        self.assertFalse(result)
        
        # Verify the entity was not added to the registry
        self.assertNotIn("test-entity", self.registry.entities)

    def test_register_endpoint(self):
        """Test registering an endpoint."""
        # Test data
        entity_id = "test-entity"
        endpoint = {
            "path": "/test/{param}",
            "methods": {
                "GET": {
                    "description": "Get test",
                    "handler": lambda: "test"
                }
            }
        }

        # Call the method
        self.registry._register_endpoint(entity_id, endpoint)

        # Verify the endpoint was registered
        pattern_str = next(iter(self.registry.endpoints.keys()))
        self.assertIn(pattern_str, self.registry.endpoint_patterns)
        
        # Verify the endpoint data
        endpoint_data = self.registry.endpoints[pattern_str]
        self.assertEqual(endpoint_data[0], entity_id)
        self.assertEqual(endpoint_data[1], "/test/{param}")
        self.assertEqual(endpoint_data[2], endpoint["methods"])

    def test_register_endpoint_no_path(self):
        """Test registering an endpoint with no path."""
        # Test data
        entity_id = "test-entity"
        endpoint = {
            "methods": {
                "GET": {
                    "description": "Get test",
                    "handler": lambda: "test"
                }
            }
        }

        # Call the method
        self.registry._register_endpoint(entity_id, endpoint)

        # Verify no endpoint was registered
        self.assertEqual(self.registry.endpoints, {})
        self.assertEqual(self.registry.endpoint_patterns, {})

    def test_register_endpoint_no_methods(self):
        """Test registering an endpoint with no methods."""
        # Test data
        entity_id = "test-entity"
        endpoint = {
            "path": "/test"
        }

        # Call the method
        self.registry._register_endpoint(entity_id, endpoint)

        # Verify no endpoint was registered
        self.assertEqual(self.registry.endpoints, {})
        self.assertEqual(self.registry.endpoint_patterns, {})

    def test_path_template_to_regex(self):
        """Test converting a path template to a regex pattern."""
        # Test data
        path_template = "/test/{param1}/sub/{param2}"
        
        # Call the method
        pattern = self.registry._path_template_to_regex(path_template)
        
        # Verify the pattern
        self.assertIsInstance(pattern, re.Pattern)
        
        # Test matching
        match = pattern.match("/test/value1/sub/value2")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("param1"), "value1")
        self.assertEqual(match.group("param2"), "value2")
        
        # Test non-matching
        self.assertIsNone(pattern.match("/test/value1/other/value2"))
        self.assertIsNone(pattern.match("/test/value1/sub"))

    def test_get_entity(self):
        """Test getting an entity by ID."""
        # Test data
        entity_data = {
            "entity_id": "test-entity",
            "entity_name": "Test Entity"
        }
        self.registry.entities["test-entity"] = entity_data
        
        # Call the method
        result = self.registry.get_entity("test-entity")
        
        # Verify the result
        self.assertEqual(result, entity_data)
        
        # Test getting a non-existent entity
        self.assertIsNone(self.registry.get_entity("non-existent"))

    def test_get_all_entities(self):
        """Test getting all entities."""
        # Test data
        entity1 = {"entity_id": "entity1", "entity_name": "Entity 1"}
        entity2 = {"entity_id": "entity2", "entity_name": "Entity 2"}
        self.registry.entities = {
            "entity1": entity1,
            "entity2": entity2
        }
        
        # Call the method
        result = self.registry.get_all_entities()
        
        # Verify the result
        self.assertEqual(result, {"entity1": entity1, "entity2": entity2})

    def test_find_endpoint_handler_exact_match(self):
        """Test finding an endpoint handler with an exact match."""
        # Test data
        handler_info = {
            "description": "Test handler",
            "handler": lambda: "test"
        }
        self.registry.endpoints = {
            r"^/test$": ("test-entity", "/test", {"GET": handler_info})
        }
        self.registry.endpoint_patterns = {
            r"^/test$": re.compile(r"^/test$")
        }
        
        # Call the method
        result_handler, result_params, result_entity = self.registry.find_endpoint_handler("/test", "GET")
        
        # Verify the result
        self.assertEqual(result_handler, handler_info)
        self.assertEqual(result_params, {})
        self.assertEqual(result_entity, "test-entity")

    def test_find_endpoint_handler_with_params(self):
        """Test finding an endpoint handler with path parameters."""
        # Test data
        handler_info = {
            "description": "Test handler",
            "handler": lambda: "test"
        }
        pattern_str = r"^/test/(?P<id>[^/]+)$"
        self.registry.endpoints = {
            pattern_str: ("test-entity", "/test/{id}", {"GET": handler_info})
        }
        self.registry.endpoint_patterns = {
            pattern_str: re.compile(pattern_str)
        }
        
        # Call the method
        result_handler, result_params, result_entity = self.registry.find_endpoint_handler("/test/123", "GET")
        
        # Verify the result
        self.assertEqual(result_handler, handler_info)
        self.assertEqual(result_params, {"id": "123"})
        self.assertEqual(result_entity, "test-entity")

    def test_find_endpoint_handler_method_not_supported(self):
        """Test finding an endpoint handler with an unsupported method."""
        # Test data
        handler_info = {
            "description": "Test handler",
            "handler": lambda: "test"
        }
        self.registry.endpoints = {
            r"^/test$": ("test-entity", "/test", {"GET": handler_info})
        }
        self.registry.endpoint_patterns = {
            r"^/test$": re.compile(r"^/test$")
        }
        
        # Call the method
        result_handler, result_params, result_entity = self.registry.find_endpoint_handler("/test", "POST")
        
        # Verify the result
        self.assertIsNone(result_handler)
        self.assertEqual(result_params, {})
        self.assertEqual(result_entity, "test-entity")

    def test_find_endpoint_handler_no_match(self):
        """Test finding an endpoint handler with no matching path."""
        # Test data
        handler_info = {
            "description": "Test handler",
            "handler": lambda: "test"
        }
        self.registry.endpoints = {
            r"^/test$": ("test-entity", "/test", {"GET": handler_info})
        }
        self.registry.endpoint_patterns = {
            r"^/test$": re.compile(r"^/test$")
        }
        
        # Call the method
        result_handler, result_params, result_entity = self.registry.find_endpoint_handler("/other", "GET")
        
        # Verify the result
        self.assertIsNone(result_handler)
        self.assertIsNone(result_params)
        self.assertIsNone(result_entity)

    def test_deregister_entity(self):
        """Test deregistering an entity."""
        # Test data
        entity_data = {
            "entity_id": "test-entity",
            "entity_name": "Test Entity"
        }
        self.registry.entities = {
            "test-entity": entity_data
        }
        pattern_str1 = r"^/test1$"
        pattern_str2 = r"^/test2$"
        self.registry.endpoints = {
            pattern_str1: ("test-entity", "/test1", {"GET": {}}),
            pattern_str2: ("other-entity", "/test2", {"GET": {}})
        }
        self.registry.endpoint_patterns = {
            pattern_str1: re.compile(pattern_str1),
            pattern_str2: re.compile(pattern_str2)
        }
        
        # Call the method
        result = self.registry.deregister_entity("test-entity")
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify the entity was removed
        self.assertNotIn("test-entity", self.registry.entities)
        
        # Verify the endpoints were removed
        self.assertNotIn(pattern_str1, self.registry.endpoints)
        self.assertIn(pattern_str2, self.registry.endpoints)
        self.assertNotIn(pattern_str1, self.registry.endpoint_patterns)
        self.assertIn(pattern_str2, self.registry.endpoint_patterns)

    def test_deregister_entity_not_found(self):
        """Test deregistering a non-existent entity."""
        # Call the method
        result = self.registry.deregister_entity("non-existent")
        
        # Verify the result
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
