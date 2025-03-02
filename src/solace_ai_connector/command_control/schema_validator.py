"""Schema Validator for the Command Control system.

This module provides validation for request and response schemas.
"""

from typing import Any, Dict, Optional

from ..common.log import log


class SchemaValidator:
    """Validates requests and responses against schemas.
    
    This class provides methods for validating parameters, request bodies,
    and response bodies against JSON schemas.
    """

    def __init__(self):
        """Initialize the SchemaValidator."""
        pass

    def validate_path_params(self, 
                            params: Dict[str, str], 
                            schema: Dict[str, Any]) -> Optional[str]:
        """Validate path parameters against a schema.
        
        Args:
            params: The path parameters to validate.
            schema: The schema to validate against.
            
        Returns:
            Optional[str]: An error message if validation fails, None otherwise.
        """
        if not schema:
            return None
            
        # Check for required parameters
        for param_name, param_schema in schema.items():
            if param_schema.get('required', False) and param_name not in params:
                return f"Required path parameter '{param_name}' is missing"
                
        # Validate parameter types
        for param_name, param_value in params.items():
            if param_name in schema:
                param_schema = schema[param_name]
                param_type = param_schema.get('type', 'string')
                
                # Validate type
                if param_type == 'number':
                    try:
                        float(param_value)
                    except ValueError:
                        return f"Path parameter '{param_name}' must be a number"
                elif param_type == 'integer':
                    try:
                        int(param_value)
                    except ValueError:
                        return f"Path parameter '{param_name}' must be an integer"
                elif param_type == 'boolean':
                    if param_value.lower() not in ['true', 'false', '1', '0']:
                        return f"Path parameter '{param_name}' must be a boolean"
                        
        return None

    def validate_query_params(self, 
                             params: Dict[str, str], 
                             schema: Dict[str, Any]) -> Optional[str]:
        """Validate query parameters against a schema.
        
        Args:
            params: The query parameters to validate.
            schema: The schema to validate against.
            
        Returns:
            Optional[str]: An error message if validation fails, None otherwise.
        """
        if not schema:
            return None
            
        # Check for require parameters
        for param_name, param_schema in schema.items():
            if param_schema.get('required', False) and param_name not in params:
                return f"Required query parameter '{param_name}' is missing"
                
        # Validate parameter types
        for param_name, param_value in params.items():
            if param_name in schema:
                param_schema = schema[param_name]
                param_type = param_schema.get('type', 'string')
                
                # Validate type
                if param_type == 'number':
                    try:
                        float(param_value)
                    except ValueError:
                        return f"Query parameter '{param_name}' must be a number"
                elif param_type == 'integer':
                    try:
                        int(param_value)
                    except ValueError:
                        return f"Query parameter '{param_name}' must be an integer"
                elif param_type == 'boolean':
                    if param_value.lower() not in ['true', 'false', '1', '0']:
                        return f"Query parameter '{param_name}' must be a boolean"
                        
                # Validate enum values
                if 'enum' in param_schema and param_value not in param_schema['enum']:
                    return f"Query parameter '{param_name}' must be one of: {param_schema['enum']}"
                    
        return None

    def validate_request_body(self, 
                             body: Any, 
                             schema: Dict[str, Any]) -> Optional[str]:
        """Validate a request body against a schema.
        
        Args:
            body: The request body to validate.
            schema: The schema to validate against.
            
        Returns:
            Optional[str]: An error message if validation fails, None otherwise.
        """
        if not schema:
            return None
            
        # If body is required but not provided
        if schema.get('required', False) and body is None:
            return "Request body is required but not provided"
            
        # If body is not required and not provided, skip validation
        if body is None:
            return None
            
        # Validate body type
        body_type = schema.get('type')
        if body_type:
            if body_type == 'object' and not isinstance(body, dict):
                return "Request body must be an object"
            elif body_type == 'array' and not isinstance(body, list):
                return "Request body must be an array"
            elif body_type == 'string' and not isinstance(body, str):
                return "Request body must be a string"
            elif body_type == 'number' and not isinstance(body, (int, float)):
                return "Request body must be a number"
            elif body_type == 'integer' and not isinstance(body, int):
                return "Request body must be an integer"
            elif body_type == 'boolean' and not isinstance(body, bool):
                return "Request body must be a boolean"
                
        # Validate required properties for objects
        if body_type == 'object' and isinstance(body, dict):
            required_props = schema.get('required', [])
            for prop in required_props:
                if prop not in body:
                    return f"Required property '{prop}' is missing from request body"
                    
            # Validate property types
            properties = schema.get('properties', {})
            for prop_name, prop_value in body.items():
                if prop_name in properties:
                    prop_schema = properties[prop_name]
                    prop_type = prop_schema.get('type')
                    
                    if prop_type == 'object' and not isinstance(prop_value, dict):
                        return f"Property '{prop_name}' must be an object"
                    elif prop_type == 'array' and not isinstance(prop_value, list):
                        return f"Property '{prop_name}' must be an array"
                    elif prop_type == 'string' and not isinstance(prop_value, str):
                        return f"Property '{prop_name}' must be a string"
                    elif prop_type == 'number' and not isinstance(prop_value, (int, float)):
                        return f"Property '{prop_name}' must be a number"
                    elif prop_type == 'integer' and not isinstance(prop_value, int):
                        return f"Property '{prop_name}' must be an integer"
                    elif prop_type == 'boolean' and not isinstance(prop_value, bool):
                        return f"Property '{prop_name}' must be a boolean"
                        
        return None

    def validate_response_body(self, 
                              body: Any, 
                              schema: Dict[str, Any]) -> Optional[str]:
        """Validate a response body against a schema.
        
        Args:
            body: The response body to validate.
            schema: The schema to validate against.
            
        Returns:
            Optional[str]: An error message if validation fails, None otherwise.
        """
        # Response validation is similar to request validation
        return self.validate_request_body(body, schema)
