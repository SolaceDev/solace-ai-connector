"""Command Control Service for the Solace AI Connector.

This module provides the central service for command and control functionality,
managing entity registration and request handling.
"""

import uuid
from typing import Any, Dict, List, Optional

from .entity_registry import EntityRegistry
from .request_router import RequestRouter
from .tracing import TracingSystem, TraceContext
from ..common.log import log


class CommandControlService:
    """Central service for command and control functionality.

    This class manages entity registration and coordinates request routing and
    response handling for the command and control system.
    """

    def __init__(self, connector=None):
        """Initialize the CommandControlService.

        Args:
            connector: The SolaceAiConnector instance this service belongs to.
        """
        self.connector = connector
        self.entity_registry = EntityRegistry()
        self.request_router = RequestRouter(self.entity_registry)
        self.instance_id = str(uuid.uuid4())
        self.broker_adapter = None

        # Initialize the tracing system without a broker adapter
        # We'll set it later when the broker adapter is available
        self.tracing_system = TracingSystem()

        log.info(
            "Command Control Service initialized with instance ID: %s", self.instance_id
        )

    def register_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        description: str,
        version: str,
        parent_entity_id: Optional[str] = None,
        endpoints: Optional[List[Dict[str, Any]]] = None,
        status_attributes: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[List[Dict[str, Any]]] = None,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Register a managed entity with the command and control system.

        Args:
            entity_id: Unique identifier for the entity.
            entity_type: Type of entity (e.g., 'flow', 'component', 'connector').
            entity_name: Human-readable name for the entity.
            description: Detailed description of the entity's purpose.
            version: Version information for the entity.
            parent_entity_id: Optional ID of the parent entity.
            endpoints: List of endpoints the entity exposes.
            status_attributes: List of status attributes the entity will report.
            metrics: List of metrics the entity will report.
            configuration: Configuration information for the entity.

        Returns:
            bool: True if registration was successful, False otherwise.
        """
        try:
            # Create the entity registration data
            entity_data = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "description": description,
                "version": version,
                "parent_entity_id": parent_entity_id,
                "endpoints": endpoints or [],
                "status_attributes": status_attributes or [],
                "metrics": metrics or [],
                "configuration": configuration or {},
            }

            # Register the entity with the registry
            success = self.entity_registry.register_entity(entity_data)

            if success:
                log.info("Entity registered: %s (%s)", entity_name, entity_id)
                # Publish notification about new entity registration
                self.publish_registry()

                # Emit a trace event for the registration
                self.emit_trace(
                    entity_id="command_control",
                    entity_type="service",
                    trace_level="INFO",
                    operation="register_entity",
                    stage="completion",
                    data={
                        "registered_entity": entity_id,
                        "entity_type": entity_type,
                        "entity_name": entity_name,
                    },
                )

                return True
            else:
                log.warning(
                    "Failed to register entity: %s (%s)", entity_name, entity_id
                )
                return False

        except Exception as e:
            log.error("Error registering entity %s: %s", entity_id, str(e))
            return False

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming command request.

        Args:
            request: The command request to handle.

        Returns:
            Dict[str, Any]: The response to the request.
        """
        request_id = request.get("request_id", "unknown")
        method = request.get("method", "")
        endpoint = request.get("endpoint", "")

        # Create a trace context for the request
        with self.create_trace_context(
            entity_id="command_control",
            entity_type="service",
            trace_level="INFO",
            operation=f"{method} {endpoint}",
            request_id=request_id,
            data={"request": request},
        ) as trace_ctx:
            try:
                # Validate the request format
                if not self._validate_request(request):
                    return self._create_error_response(
                        request_id, 400, "Invalid request format"
                    )

                # Route the request to the appropriate handler
                response = self.request_router.route_request(request)

                # Add trace data for the response
                trace_ctx.progress(data={"response": response})

                return response

            except Exception as e:
                log.error("Error handling request: %s", str(e))
                return self._create_error_response(
                    request_id, 500, f"Internal server error: {str(e)}"
                )

    def _validate_request(self, request: Dict[str, Any]) -> bool:
        """Validate that a request has the required fields.

        Args:
            request: The request to validate.

        Returns:
            bool: True if the request is valid, False otherwise.
        """
        required_fields = ["request_id", "method", "endpoint"]
        return all(field in request for field in required_fields)

    def _create_error_response(
        self, request_id: str, status_code: int, message: str
    ) -> Dict[str, Any]:
        """Create an error response.

        Args:
            request_id: The ID of the request that caused the error.
            status_code: The HTTP-like status code for the error.
            message: A human-readable error message.

        Returns:
            Dict[str, Any]: The error response.
        """
        import datetime

        return {
            "request_id": request_id,
            "status_code": status_code,
            "status_message": message,
            "headers": {"content-type": "application/json"},
            "body": {"error": message},
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def emit_trace(
        self,
        entity_id: str,
        entity_type: str,
        trace_level: str,
        operation: str,
        stage: str,
        request_id: Optional[str] = None,
        data: Any = None,
        error: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Emit a trace event.

        Args:
            entity_id: The ID of the entity emitting the trace.
            entity_type: The type of entity emitting the trace.
            trace_level: The trace level (DEBUG, INFO, WARN, ERROR).
            operation: The operation being performed.
            stage: The stage of the operation (start, progress, completion).
            request_id: Optional ID of the request being traced.
            data: Optional data specific to the operation.
            error: Optional error information.
            duration_ms: Optional duration in milliseconds.
        """
        if self.tracing_system:
            # Update the broker adapter if it's been set
            if self.broker_adapter and self.tracing_system.broker_adapter is None:
                self.tracing_system.set_broker_adapter(self.broker_adapter)
                
            self.tracing_system.emit_trace(
                entity_id=entity_id,
                entity_type=entity_type,
                trace_level=trace_level,
                operation=operation,
                stage=stage,
                request_id=request_id,
                data=data,
                error=error,
                duration_ms=duration_ms,
            )

    def publish_status(
        self, entity_id: str, entity_type: str, status: str, details: Dict[str, Any]
    ) -> None:
        """Publish a status update for an entity.

        Args:
            entity_id: The ID of the entity.
            entity_type: The type of entity.
            status: The current status of the entity.
            details: Additional status details.
        """
        if not self.broker_adapter:
            log.warning("No broker adapter available, cannot publish status")
            return

        self.broker_adapter.publish_status(entity_id, entity_type, status, details)

    def publish_metrics(
        self, entity_id: str, entity_type: str, metrics: Dict[str, Dict[str, Any]]
    ) -> None:
        """Publish metrics for an entity.

        Args:
            entity_id: The ID of the entity.
            entity_type: The type of entity.
            metrics: The metrics to publish.
        """
        if not self.broker_adapter:
            log.warning("No broker adapter available, cannot publish metrics")
            return

        self.broker_adapter.publish_metrics(entity_id, entity_type, metrics)

    def publish_registry(self) -> None:
        """Publish the current entity registry.

        This publishes a list of all registered entities and their endpoints.
        """
        if not self.broker_adapter:
            log.warning("No broker adapter available, cannot publish registry")
            return

        entities = self.entity_registry.get_all_entities()
        self.broker_adapter.publish_registry(self.instance_id, entities)

    def get_trace_configuration(self) -> Dict[str, Any]:
        """Get the current trace configuration.

        Returns:
            Dict[str, Any]: The current trace configuration.
        """
        if not self.tracing_system:
            return {"enabled": False, "default_level": "INFO", "entity_levels": {}}

        return self.tracing_system.get_configuration()

    def get_entity_trace_configuration(self, entity_id: str) -> Dict[str, Any]:
        """Get the trace configuration for a specific entity.

        Args:
            entity_id: The ID of the entity.

        Returns:
            Dict[str, Any]: The entity's trace configuration.
        """
        if not self.tracing_system:
            return {"entity_id": entity_id, "enabled": False, "level": "INFO"}

        return self.tracing_system.get_entity_configuration(entity_id)

    def update_trace_configuration(self, config: Dict[str, Any]) -> bool:
        """Update the trace configuration.

        Args:
            config: The new configuration.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        if not self.tracing_system:
            return False

        return self.tracing_system.update_configuration(config)

    def create_trace_context(
        self,
        entity_id: str,
        entity_type: str,
        trace_level: str,
        operation: str,
        request_id: Optional[str] = None,
        data: Any = None,
    ) -> Any:
        """Create a trace context for an operation.

        Args:
            entity_id: The ID of the entity emitting the trace.
            entity_type: The type of entity emitting the trace.
            trace_level: The trace level (DEBUG, INFO, WARN, ERROR).
            operation: The operation being performed.
            request_id: Optional ID of the request being traced.
            data: Optional data specific to the operation.

        Returns:
            TraceContext: A trace context for the operation.
        """
        if not self.tracing_system:
            # Return a dummy trace context if tracing is not available
            return TraceContext(
                tracing_system=TracingSystem(),
                entity_id=entity_id,
                entity_type=entity_type,
                trace_level=trace_level,
                operation=operation,
                request_id=request_id,
                data=data,
            )

        # Update the broker adapter if it's been set
        if self.broker_adapter and self.tracing_system.broker_adapter is None:
            self.tracing_system.set_broker_adapter(self.broker_adapter)

        # Use the tracing system's create_trace_context method directly
        return self.tracing_system.create_trace_context(
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            request_id=request_id,
            data=data,
        )
