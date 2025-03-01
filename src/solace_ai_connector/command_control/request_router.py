"""Request Router for the Command Control system.

This module provides the routing functionality for command requests.
"""

import logging
import datetime
from typing import Any, Dict, Optional

from .schema_validator import SchemaValidator

# Configure logger
log = logging.getLogger(__name__)


class RequestRouter:
    """Routes incoming requests to the appropriate entity and handler.
    
    This class parses request paths, extracts parameters, and invokes
    the appropriate handler function.
    """

    def __init__(self, entity_registry):
        """Initialize the RequestRouter.
        
        Args:
            entity_registry: The EntityRegistry instance to use for routing.
        """
        self.entity_registry = entity_registry
        self.schema_validator = SchemaValidator()

    def route_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route a request to the appropriate handler.
        
        Args:
            request: The request to route.
            
        Returns:
            Dict[str, Any]: The response from the handler.
        """
        request_id = request.get('request_id', 'unknown')
        method = request.get('method')
        endpoint = request.get('endpoint')
        query_params = request.get('query_params', {})
        body = request.get('body')
        
        log.info("Routing request %s: %s %s", request_id, method, endpoint)
        
        # Find the handler for this endpoint and method
        handler_info, path_params, entity_id = self.entity_registry.find_endpoint_handler(
            endpoint, method)
            
        if not handler_info:
            return self._create_error_response(
                request_id, 
                404, 
                f"No handler found for {method} {endpoint}"
            )
            
        # Get the handler function
        handler_func = handler_info.get('handler')
        if not handler_func or not callable(handler_func):
            return self._create_error_response(
                request_id, 
                500, 
                f"Invalid handler for {method} {endpoint}"
            )
            
        # Validate parameters
        validation_result = self._validate_parameters(
            handler_info, path_params, query_params, body)
            
        if validation_result:
            return self._create_error_response(
                request_id, 
                400, 
                f"Parameter validation failed: {validation_result}"
            )
            
        try:
            # Call the handler function
            entity = self.entity_registry.get_entity(entity_id)
            if not entity:
                return self._create_error_response(
                    request_id, 
                    500, 
                    f"Entity {entity_id} not found"
                )
                
            # Prepare the context for the handler
            context = {
                'request_id': request_id,
                'entity_id': entity_id,
                'entity': entity,
                'timestamp': request.get('timestamp'),
                'source': request.get('source')
            }
            
            # Call the handler
            result = handler_func(
                path_params=path_params,
                query_params=query_params,
                body=body,
                context=context
            )
            
            # Create the response
            return self._create_response(request_id, 200, "OK", result)
            
        except Exception as e:
            log.error("Error calling handler for %s %s: %s", 
                     method, endpoint, str(e), exc_info=True)
            return self._create_error_response(
                request_id, 
                500, 
                f"Error processing request: {str(e)}"
            )

    def _validate_parameters(self, 
                            handler_info: Dict[str, Any],
                            path_params: Dict[str, str],
                            query_params: Dict[str, str],
                            body: Any) -> Optional[str]:
        """Validate request parameters against the handler's schema.
        
        Args:
            handler_info: The handler information.
            path_params: The path parameters.
            query_params: The query parameters.
            body: The request body.
            
        Returns:
            Optional[str]: An error message if validation fails, None otherwise.
        """
        # Validate path parameters
        path_param_schema = handler_info.get('path_params', {})
        path_validation_error = self.schema_validator.validate_path_params(
            path_params, path_param_schema)
        if path_validation_error:
            return path_validation_error
            
        # Validate query parameters
        query_param_schema = handler_info.get('query_params', {})
        query_validation_error = self.schema_validator.validate_query_params(
            query_params, query_param_schema)
        if query_validation_error:
            return query_validation_error
            
        # Validate request body
        body_schema = handler_info.get('request_body_schema')
        if body_schema:
            body_validation_error = self.schema_validator.validate_request_body(
                body, body_schema)
            if body_validation_error:
                return body_validation_error
                
        return None

    def _create_response(self, 
                        request_id: str,
                        status_code: int,
                        status_message: str,
                        body: Any) -> Dict[str, Any]:
        """Create a response object.
        
        Args:
            request_id: The ID of the request.
            status_code: The HTTP-like status code.
            status_message: A human-readable status message.
            body: The response body.
            
        Returns:
            Dict[str, Any]: The response object.
        """
        return {
            'request_id': request_id,
            'status_code': status_code,
            'status_message': status_message,
            'headers': {
                'content-type': 'application/json'
            },
            'body': body,
            'timestamp': datetime.datetime.now().isoformat()
        }

    def _create_error_response(self, 
                              request_id: str,
                              status_code: int,
                              message: str) -> Dict[str, Any]:
        """Create an error response.
        
        Args:
            request_id: The ID of the request.
            status_code: The HTTP-like status code.
            message: A human-readable error message.
            
        Returns:
            Dict[str, Any]: The error response.
        """
        return self._create_response(
            request_id,
            status_code,
            message,
            {'error': message}
        )
