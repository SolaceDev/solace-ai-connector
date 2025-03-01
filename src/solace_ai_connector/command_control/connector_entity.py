"""Connector Entity for the Command Control system.

This module provides the standard connector entity that exposes system-wide
endpoints for the command and control system.
"""

import logging
import platform
import os
import sys
import psutil
import datetime
from typing import Any, Dict, List, Optional

# Configure logger
log = logging.getLogger(__name__)


class ConnectorEntity:
    """Standard connector entity for the command control system.
    
    This class provides standard endpoints for connector management, flow management,
    component management, and system management.
    """

    def __init__(self, connector, command_control_service):
        """Initialize the ConnectorEntity.
        
        Args:
            connector: The SolaceAiConnector instance.
            command_control_service: The CommandControlService instance.
        """
        self.connector = connector
        self.command_control_service = command_control_service
        self.start_time = datetime.datetime.now()
        
        # Register the connector entity
        self.register()
        
    def register(self) -> bool:
        """Register the connector entity with the command control system.
        
        Returns:
            bool: True if registration was successful, False otherwise.
        """
        # Create the endpoints
        endpoints = self._create_endpoints()
        
        # Register with the command control service
        success = self.command_control_service.register_entity(
            entity_id="connector",
            entity_type="connector",
            entity_name=self.connector.instance_name,
            description="Solace AI Connector instance",
            version=self._get_version(),
            endpoints=endpoints,
            status_attributes=self._get_status_attributes(),
            metrics=self._get_metrics(),
            configuration=self._get_configuration()
        )
        
        if success:
            log.info("Connector entity registered with command control system")
        else:
            log.warning("Failed to register connector entity with command control system")
            
        return success
        
    def _create_endpoints(self) -> List[Dict[str, Any]]:
        """Create the standard endpoints for the connector entity.
        
        Returns:
            List[Dict[str, Any]]: A list of endpoint definitions.
        """
        return [
            # Connector Management
            {
                "path": "/connector",
                "methods": {
                    "GET": {
                        "description": "Get connector information",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "instance_name": {"type": "string"},
                                "version": {"type": "string"},
                                "uptime": {"type": "string"},
                                "platform": {"type": "string"},
                                "python_version": {"type": "string"}
                            }
                        },
                        "handler": self.handle_get_connector_info
                    }
                }
            },
            {
                "path": "/connector/status",
                "methods": {
                    "GET": {
                        "description": "Get connector status",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "flows_running": {"type": "integer"},
                                "flows_total": {"type": "integer"},
                                "memory_usage": {"type": "object"}
                            }
                        },
                        "handler": self.handle_get_connector_status
                    }
                }
            },
            {
                "path": "/connector/metrics",
                "methods": {
                    "GET": {
                        "description": "Get connector metrics",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object"
                        },
                        "handler": self.handle_get_connector_metrics
                    }
                }
            },
            {
                "path": "/connector/shutdown",
                "methods": {
                    "POST": {
                        "description": "Shutdown the connector gracefully",
                        "path_params": {},
                        "query_params": {},
                        "request_body_schema": {
                            "type": "object",
                            "properties": {
                                "force": {
                                    "type": "boolean",
                                    "description": "Force immediate shutdown"
                                }
                            }
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "message": {"type": "string"}
                            }
                        },
                        "handler": self.handle_shutdown_connector
                    }
                }
            },
            
            # Flow Management
            {
                "path": "/flows",
                "methods": {
                    "GET": {
                        "description": "List all flows",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "flows": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "status": {"type": "string"},
                                            "components": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        },
                        "handler": self.handle_list_flows
                    }
                }
            },
            {
                "path": "/flows/{flow_id}",
                "methods": {
                    "GET": {
                        "description": "Get flow information",
                        "path_params": {
                            "flow_id": {
                                "type": "string",
                                "description": "Flow ID",
                                "required": True
                            }
                        },
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "status": {"type": "string"},
                                "components": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "type": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "handler": self.handle_get_flow_info
                    }
                }
            },
            {
                "path": "/flows/{flow_id}/status",
                "methods": {
                    "GET": {
                        "description": "Get flow status",
                        "path_params": {
                            "flow_id": {
                                "type": "string",
                                "description": "Flow ID",
                                "required": True
                            }
                        },
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "details": {"type": "object"}
                            }
                        },
                        "handler": self.handle_get_flow_status
                    }
                }
            },
            
            # System Management
            {
                "path": "/system/health",
                "methods": {
                    "GET": {
                        "description": "Get system health",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "details": {"type": "object"}
                            }
                        },
                        "handler": self.handle_get_system_health
                    }
                }
            },
            {
                "path": "/system/metrics",
                "methods": {
                    "GET": {
                        "description": "Get system metrics",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object"
                        },
                        "handler": self.handle_get_system_metrics
                    }
                }
            },
            {
                "path": "/system/config",
                "methods": {
                    "GET": {
                        "description": "Get system configuration",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object"
                        },
                        "handler": self.handle_get_system_config
                    }
                }
            },
            
            # Trace Management
            {
                "path": "/system/trace",
                "methods": {
                    "GET": {
                        "description": "Get trace configuration",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "level": {"type": "string"}
                            }
                        },
                        "handler": self.handle_get_trace_config
                    },
                    "PUT": {
                        "description": "Update trace configuration",
                        "path_params": {},
                        "query_params": {},
                        "request_body_schema": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "level": {"type": "string"}
                            }
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "message": {"type": "string"}
                            }
                        },
                        "handler": self.handle_update_trace_config
                    }
                }
            }
        ]
        
    def _get_status_attributes(self) -> List[Dict[str, Any]]:
        """Get the status attributes for the connector entity.
        
        Returns:
            List[Dict[str, Any]]: A list of status attribute definitions.
        """
        return [
            {
                "name": "state",
                "description": "Current operational state",
                "type": "string",
                "possible_values": ["starting", "running", "stopping", "stopped", "error"]
            },
            {
                "name": "health",
                "description": "Health status",
                "type": "string",
                "possible_values": ["healthy", "degraded", "unhealthy"]
            }
        ]
        
    def _get_metrics(self) -> List[Dict[str, Any]]:
        """Get the metrics for the connector entity.
        
        Returns:
            List[Dict[str, Any]]: A list of metric definitions.
        """
        return [
            {
                "name": "memory_usage",
                "description": "Memory usage in bytes",
                "type": "gauge",
                "unit": "bytes"
            },
            {
                "name": "cpu_usage",
                "description": "CPU usage percentage",
                "type": "gauge",
                "unit": "percent"
            },
            {
                "name": "uptime",
                "description": "Uptime in seconds",
                "type": "gauge",
                "unit": "seconds"
            }
        ]
        
    def _get_configuration(self) -> Dict[str, Any]:
        """Get the configuration for the connector entity.
        
        Returns:
            Dict[str, Any]: The configuration definition.
        """
        # Filter out sensitive information
        filtered_config = {}
        if hasattr(self.connector, 'config'):
            for key, value in self.connector.config.items():
                # Skip passwords, keys, tokens, etc.
                if not isinstance(value, dict):
                    if not any(sensitive in str(key).lower() for sensitive in ["password", "secret", "key", "token"]):
                        filtered_config[key] = value
                else:
                    # Handle nested dictionaries
                    filtered_config[key] = {}
                    for subkey, subvalue in value.items():
                        if not any(sensitive in str(subkey).lower() for sensitive in ["password", "secret", "key", "token"]):
                            filtered_config[key][subkey] = subvalue
                
        return {
            "current_config": filtered_config,
            "mutable_paths": [],  # No config is mutable by default
            "config_schema": {}   # No schema by default
        }
        
    def _get_version(self) -> str:
        """Get the version of the connector.
        
        Returns:
            str: The version string.
        """
        # This is a placeholder - in a real implementation, you would get the actual version
        return "1.0.0"
        
    # Handler methods for connector management
    
    def handle_get_connector_info(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for connector information.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Connector information.
        """
        uptime = datetime.datetime.now() - self.start_time
        
        return {
            "instance_name": self.connector.instance_name,
            "version": self._get_version(),
            "uptime": str(uptime),
            "platform": platform.platform(),
            "python_version": sys.version
        }
        
    def handle_get_connector_status(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for connector status.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Connector status.
        """
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "status": "running",
            "flows_running": len(self.connector.flows),
            "flows_total": len(self.connector.flows),
            "memory_usage": {
                "rss": memory_info.rss,
                "vms": memory_info.vms
            }
        }
        
    def handle_get_connector_metrics(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for connector metrics.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Connector metrics.
        """
        process = psutil.Process(os.getpid())
        
        return {
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "memory_info": {
                "rss": process.memory_info().rss,
                "vms": process.memory_info().vms
            },
            "uptime_seconds": (datetime.datetime.now() - self.start_time).total_seconds()
        }
        
    def handle_shutdown_connector(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to shutdown the connector.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Shutdown status.
        """
        force = False
        if body and isinstance(body, dict):
            force = body.get("force", False)
            
        # Schedule the shutdown to happen after we've sent the response
        def delayed_shutdown():
            import time
            time.sleep(1)  # Give time for the response to be sent
            self.connector.stop()
            
        import threading
        shutdown_thread = threading.Thread(target=delayed_shutdown)
        shutdown_thread.daemon = True
        shutdown_thread.start()
        
        return {
            "status": "shutting_down",
            "message": "Connector is shutting down"
        }
        
    # Handler methods for flow management
    
    def handle_list_flows(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to list all flows.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: List of flows.
        """
        flows = []
        for flow in self.connector.flows:
            flows.append({
                "id": flow.name,
                "name": flow.name,
                "status": "running",  # Default status
                "components": len(flow.component_groups) if hasattr(flow, 'component_groups') else 0
            })
            
        return {"flows": flows}
        
    def handle_get_flow_info(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for flow information.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Flow information.
        """
        flow_id = path_params.get("flow_id")
        flow = self.connector.get_flow(flow_id)
        
        if not flow:
            return {
                "error": f"Flow {flow_id} not found"
            }
            
        components = []
        if hasattr(flow, 'component_groups'):
            for component_group in flow.component_groups:
                for component in component_group:
                    components.append({
                        "name": component.name,
                        "type": component.config.get("component_module", "unknown")
                    })
            
        return {
            "id": flow.name,
            "name": flow.name,
            "status": "running",  # Default status
            "components": components
        }
        
    def handle_get_flow_status(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for flow status.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Flow status.
        """
        flow_id = path_params.get("flow_id")
        flow = self.connector.get_flow(flow_id)
        
        if not flow:
            return {
                "error": f"Flow {flow_id} not found"
            }
            
        return {
            "status": "running",  # Default status
            "details": {
                "components": len(flow.component_groups) if hasattr(flow, 'component_groups') else 0
            }
        }
        
    # Handler methods for system management
    
    def handle_get_system_health(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for system health.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: System health.
        """
        # Check if all flows are running
        all_flows_running = True
        
        # Check memory usage
        process = psutil.Process(os.getpid())
        memory_percent = process.memory_percent()
        cpu_percent = process.cpu_percent()
        
        # Determine health status
        health_status = "healthy"
        if memory_percent > 90 or cpu_percent > 90:
            health_status = "degraded"
            
        if not all_flows_running:
            health_status = "unhealthy"
            
        return {
            "status": health_status,
            "details": {
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "all_flows_running": all_flows_running
            }
        }
        
    def handle_get_system_metrics(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for system metrics.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: System metrics.
        """
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu": {
                "percent": cpu_percent
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent
            }
        }
        
    def handle_get_system_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for system configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: System configuration.
        """
        # Filter out sensitive information
        filtered_config = {}
        if hasattr(self.connector, 'config'):
            for key, value in self.connector.config.items():
                # Skip passwords, keys, tokens, etc.
                if not isinstance(value, dict):
                    if not any(sensitive in str(key).lower() for sensitive in ["password", "secret", "key", "token"]):
                        filtered_config[key] = value
                else:
                    # Handle nested dictionaries
                    filtered_config[key] = {}
                    for subkey, subvalue in value.items():
                        if not any(sensitive in str(subkey).lower() for sensitive in ["password", "secret", "key", "token"]):
                            filtered_config[key][subkey] = subvalue
                
        return filtered_config
        
    # Handler methods for trace management
    
    def handle_get_trace_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for trace configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Trace configuration.
        """
        # This is a placeholder - in a real implementation, you would get the actual trace config
        return {
            "enabled": True,
            "level": "INFO"
        }
        
    def handle_update_trace_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to update trace configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Dict[str, Any]: Update status.
        """
        if not body or not isinstance(body, dict):
            return {
                "status": "error",
                "message": "Invalid request body"
            }
            
        enabled = body.get("enabled")
        level = body.get("level")
        
        # This is a placeholder - in a real implementation, you would update the actual trace config
        
        return {
            "status": "success",
            "message": "Trace configuration updated"
        }
