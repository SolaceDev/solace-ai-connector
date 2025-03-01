"""Entity Registry for the Command Control system.

This module provides the registry for managed entities in the command and control system.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Pattern

# Configure logger
log = logging.getLogger(__name__)


class EntityRegistry:
    """Registry for managed entities in the command and control system.
    
    This class stores entity metadata and maps endpoints to handler functions.
    """

    def __init__(self):
        """Initialize the EntityRegistry."""
        # Dictionary of registered entities by ID
        self.entities = {}
        
        # Dictionary mapping endpoint paths to entity IDs and methods
        # Format: {path_pattern: (entity_id, path_template, {method: handler_info})}
        self.endpoints = {}
        
        # Compiled regex patterns for endpoint matching
        self.endpoint_patterns = {}

    def register_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Register an entity with the registry.
        
        Args:
            entity_data: The entity data to register.
            
        Returns:
            bool: True if registration was successful, False otherwise.
        """
        try:
            entity_id = entity_data.get('entity_id')
            
            if not entity_id:
                log.error("Cannot register entity without entity_id")
                return False
                
            # Register the entity's endpoints
            endpoints = entity_data.get('endpoints', [])
            
            # First try to register all endpoints
            for endpoint in endpoints:
                try:
                    self._register_endpoint(entity_id, endpoint)
                except Exception as e:
                    # If any endpoint registration fails, clean up any registered endpoints
                    # and return False
                    log.error("Error registering endpoint for entity %s: %s", entity_id, str(e))
                    
                    # Remove any endpoints that were registered for this entity
                    patterns_to_remove = []
                    for pattern_str, (eid, _, _) in self.endpoints.items():
                        if eid == entity_id:
                            patterns_to_remove.append(pattern_str)
                            
                    for pattern_str in patterns_to_remove:
                        self.endpoints.pop(pattern_str, None)
                        self.endpoint_patterns.pop(pattern_str, None)
                        
                    return False
            
            # Only store the entity data after all endpoints have been successfully registered
            self.entities[entity_id] = entity_data
            return True
            
        except Exception as e:
            log.error("Error registering entity: %s", str(e))
            return False

    def _register_endpoint(self, entity_id: str, endpoint: Dict[str, Any]) -> None:
        """Register an endpoint for an entity.
        
        Args:
            entity_id: The ID of the entity.
            endpoint: The endpoint data to register.
        """
        path = endpoint.get('path')
        if not path:
            log.warning("Endpoint missing path, skipping registration")
            return
            
        methods = endpoint.get('methods', {})
        if not methods:
            log.warning("Endpoint %s has no methods, skipping registration", path)
            return
            
        # Convert path template to regex pattern for matching
        path_pattern = self._path_template_to_regex(path)
        pattern_str = path_pattern.pattern
        
        # Store the endpoint information
        self.endpoints[pattern_str] = (entity_id, path, methods)
        self.endpoint_patterns[pattern_str] = path_pattern
        
        log.debug("Registered endpoint %s for entity %s with methods %s", 
                 path, entity_id, list(methods.keys()))

    def _path_template_to_regex(self, path_template: str) -> Pattern:
        """Convert a path template to a regex pattern.
        
        Args:
            path_template: The path template (e.g., "/flows/{flow_id}").
            
        Returns:
            Pattern: A compiled regex pattern for matching paths.
        """
        # Replace {param} with named capture groups
        pattern = re.sub(r'\{([^}]+)\}', r'(?P<\1>[^/]+)', path_template)
        # Ensure the pattern matches the entire path
        pattern = f'^{pattern}$'
        return re.compile(pattern)

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get an entity by ID.
        
        Args:
            entity_id: The ID of the entity to get.
            
        Returns:
            Optional[Dict[str, Any]]: The entity data, or None if not found.
        """
        return self.entities.get(entity_id)

    def get_all_entities(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered entities.
        
        Returns:
            Dict[str, Dict[str, Any]]: A dictionary of all entities by ID.
        """
        return self.entities

    def find_endpoint_handler(self, 
                             path: str, 
                             method: str) -> Tuple[Optional[Dict[str, Any]], 
                                                  Optional[Dict[str, str]], 
                                                  Optional[str]]:
        """Find the handler for an endpoint path and method.
        
        Args:
            path: The endpoint path.
            method: The HTTP method (GET, POST, PUT, DELETE).
            
        Returns:
            Tuple containing:
                - The handler info if found, None otherwise
                - A dictionary of path parameters extracted from the path
                - The entity ID that owns the endpoint
        """
        for pattern_str, pattern in self.endpoint_patterns.items():
            match = pattern.match(path)
            if match:
                entity_id, path_template, methods = self.endpoints[pattern_str]
                
                # Extract path parameters
                path_params = match.groupdict()
                
                # Check if the method is supported
                if method in methods:
                    handler_info = methods[method]
                    return handler_info, path_params, entity_id
                    
                log.warning("Method %s not supported for endpoint %s", 
                           method, path_template)
                return None, path_params, entity_id
                
        log.warning("No endpoint found matching path: %s", path)
        return None, None, None

    def deregister_entity(self, entity_id: str) -> bool:
        """Deregister an entity from the registry.
        
        Args:
            entity_id: The ID of the entity to deregister.
            
        Returns:
            bool: True if deregistration was successful, False otherwise.
        """
        if entity_id not in self.entities:
            log.warning("Entity %s not found, cannot deregister", entity_id)
            return False
            
        # Remove the entity
        entity_data = self.entities.pop(entity_id)
        
        # Remove the entity's endpoints
        patterns_to_remove = []
        for pattern_str, (eid, _, _) in self.endpoints.items():
            if eid == entity_id:
                patterns_to_remove.append(pattern_str)
                
        for pattern_str in patterns_to_remove:
            self.endpoints.pop(pattern_str)
            self.endpoint_patterns.pop(pattern_str)
            
        log.info("Entity %s deregistered with %d endpoints", 
                entity_id, len(patterns_to_remove))
        return True
