"""Tracing System for the Command Control system.

This module provides the tracing infrastructure for the command and control system,
allowing components to emit trace events for monitoring and debugging.
"""

import logging
import datetime
import uuid
from enum import Enum
from typing import Any, Dict, Optional

# Configure logger
log = logging.getLogger(__name__)


class TraceLevel(Enum):
    """Trace levels for the tracing system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class TracingSystem:
    """Manages trace event emission and configuration.
    
    This class provides methods for emitting trace events and managing trace
    configuration for the command and control system.
    """

    def __init__(self, broker_adapter=None):
        """Initialize the TracingSystem.
        
        Args:
            broker_adapter: The BrokerAdapter instance to use for publishing trace events.
        """
        self.broker_adapter = broker_adapter
        self.enabled = True
        self.default_level = TraceLevel.INFO
        self.entity_levels = {}  # Maps entity_id to trace level
        
        log.info("Tracing system initialized with default level: %s", self.default_level.value)

    def set_broker_adapter(self, broker_adapter):
        """Set the broker adapter for publishing trace events.
        
        Args:
            broker_adapter: The BrokerAdapter instance to use.
        """
        self.broker_adapter = broker_adapter

    def emit_trace(self,
                  entity_id: str,
                  entity_type: str,
                  trace_level: str,
                  operation: str,
                  stage: str,
                  request_id: Optional[str] = None,
                  data: Any = None,
                  error: Optional[Dict[str, Any]] = None,
                  duration_ms: Optional[int] = None):
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
        if not self.enabled:
            return
            
        # Check if this entity has a specific trace level set
        entity_level = self.entity_levels.get(entity_id, self.default_level)
        
        # Convert string trace level to enum if needed
        if isinstance(trace_level, str):
            try:
                trace_level = TraceLevel(trace_level)
            except ValueError:
                log.warning("Invalid trace level: %s, using INFO", trace_level)
                trace_level = TraceLevel.INFO
                
        # Skip if the trace level is lower than the configured level
        if self._get_level_value(trace_level) < self._get_level_value(entity_level):
            return
            
        # Generate a request ID if not provided
        if not request_id:
            request_id = str(uuid.uuid4())
            
        # Create the trace event
        trace_event = {
            'entity_id': entity_id,
            'entity_type': entity_type,
            'trace_level': trace_level.value,
            'request_id': request_id,
            'operation': operation,
            'stage': stage,
            'timestamp': datetime.datetime.now().isoformat(),
        }
        
        # Add optional fields if provided
        if data is not None:
            trace_event['data'] = data
            
        if error is not None:
            trace_event['error'] = error
            
        if duration_ms is not None:
            trace_event['duration_ms'] = duration_ms
            
        # Publish the trace event
        self._publish_trace(entity_id, trace_level.value, trace_event)
        
    def _publish_trace(self, entity_id: str, level: str, trace_event: Dict[str, Any]):
        """Publish a trace event using the broker adapter.
        
        Args:
            entity_id: The ID of the entity emitting the trace.
            level: The trace level as a string.
            trace_event: The trace event to publish.
        """
        if not self.broker_adapter:
            log.debug("No broker adapter available, trace event not published")
            return
            
        try:
            self.broker_adapter.publish_trace(entity_id, level, trace_event)
        except Exception as e:
            log.warning("Error publishing trace event: %s", str(e))
            
    def _get_level_value(self, level: TraceLevel) -> int:
        """Get the numeric value of a trace level for comparison.
        
        Args:
            level: The trace level to convert.
            
        Returns:
            int: The numeric value of the trace level.
        """
        level_values = {
            TraceLevel.DEBUG: 0,
            TraceLevel.INFO: 1,
            TraceLevel.WARN: 2,
            TraceLevel.ERROR: 3
        }
        return level_values.get(level, 0)
        
    def set_enabled(self, enabled: bool):
        """Enable or disable tracing.
        
        Args:
            enabled: Whether tracing should be enabled.
        """
        self.enabled = enabled
        log.info("Tracing %s", "enabled" if enabled else "disabled")
        
    def set_default_level(self, level: str):
        """Set the default trace level.
        
        Args:
            level: The trace level to set as default.
        """
        try:
            self.default_level = TraceLevel(level)
            log.info("Default trace level set to: %s", level)
        except ValueError:
            log.warning("Invalid trace level: %s, keeping current level: %s", 
                       level, self.default_level.value)
            
    def set_entity_level(self, entity_id: str, level: str):
        """Set the trace level for a specific entity.
        
        Args:
            entity_id: The ID of the entity.
            level: The trace level to set.
        """
        try:
            self.entity_levels[entity_id] = TraceLevel(level)
            log.info("Trace level for entity %s set to: %s", entity_id, level)
        except ValueError:
            log.warning("Invalid trace level: %s for entity %s", level, entity_id)
            
    def get_configuration(self):
        """Get the current tracing configuration.
        
        Returns:
            Dict[str, Any]: The current configuration.
        """
        entity_levels = {entity_id: level.value for entity_id, level in self.entity_levels.items()}
        
        return {
            'enabled': self.enabled,
            'default_level': self.default_level.value,
            'entity_levels': entity_levels
        }
        
    def get_entity_configuration(self, entity_id: str):
        """Get the tracing configuration for a specific entity.
        
        Args:
            entity_id: The ID of the entity.
            
        Returns:
            Dict[str, Any]: The entity's configuration.
        """
        level = self.entity_levels.get(entity_id, self.default_level)
        
        return {
            'entity_id': entity_id,
            'enabled': self.enabled,
            'level': level.value
        }
        
    def update_configuration(self, config: Dict[str, Any]):
        """Update the tracing configuration.
        
        Args:
            config: The new configuration.
            
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        try:
            if 'enabled' in config:
                self.set_enabled(bool(config['enabled']))
                
            if 'default_level' in config:
                self.set_default_level(config['default_level'])
                
            if 'entity_levels' in config and isinstance(config['entity_levels'], dict):
                for entity_id, level in config['entity_levels'].items():
                    self.set_entity_level(entity_id, level)
                    
            return True
        except Exception as e:
            log.error("Error updating trace configuration: %s", str(e))
            return False
            
    def create_trace_context(self,
                            entity_id: str,
                            entity_type: str,
                            trace_level: str,
                            operation: str,
                            request_id: Optional[str] = None,
                            data: Any = None) -> 'TraceContext':
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
        return TraceContext(
            tracing_system=self,
            entity_id=entity_id,
            entity_type=entity_type,
            trace_level=trace_level,
            operation=operation,
            request_id=request_id,
            data=data
        )


class TraceContext:
    """Context manager for tracing operations.
    
    This class provides a context manager for tracing operations, automatically
    emitting start and completion trace events with timing information.
    """
    
    def __init__(self, 
                tracing_system: TracingSystem,
                entity_id: str,
                entity_type: str,
                trace_level: str,
                operation: str,
                request_id: Optional[str] = None,
                data: Any = None):
        """Initialize the TraceContext.
        
        Args:
            tracing_system: The TracingSystem instance to use.
            entity_id: The ID of the entity emitting the trace.
            entity_type: The type of entity emitting the trace.
            trace_level: The trace level (DEBUG, INFO, WARN, ERROR).
            operation: The operation being performed.
            request_id: Optional ID of the request being traced.
            data: Optional data specific to the operation.
        """
        self.tracing_system = tracing_system
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.trace_level = trace_level
        self.operation = operation
        self.request_id = request_id or str(uuid.uuid4())
        self.data = data
        self.start_time = None
        self.error = None
        
    def __enter__(self):
        """Enter the context manager, emitting a start trace event.
        
        Returns:
            TraceContext: The trace context instance.
        """
        self.start_time = datetime.datetime.now()
        
        # Emit start trace event
        self.tracing_system.emit_trace(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            trace_level=self.trace_level,
            operation=self.operation,
            stage="start",
            request_id=self.request_id,
            data=self.data
        )
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, emitting a completion trace event.
        
        Args:
            exc_type: The exception type if an exception was raised.
            exc_val: The exception value if an exception was raised.
            exc_tb: The exception traceback if an exception was raised.
            
        Returns:
            bool: False to propagate exceptions, True to suppress them.
        """
        end_time = datetime.datetime.now()
        duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
        
        # Capture error information if an exception occurred
        error = None
        if exc_type is not None:
            error = {
                'message': str(exc_val),
                'type': exc_type.__name__,
                'traceback': str(exc_tb)
            }
            self.error = error
            
        # Emit completion trace event
        self.tracing_system.emit_trace(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            trace_level=self.trace_level if error is None else TraceLevel.ERROR.value,
            operation=self.operation,
            stage="completion",
            request_id=self.request_id,
            data=self.data,
            error=error,
            duration_ms=duration_ms
        )
        
        # Propagate exceptions
        return False
        
    def progress(self, data: Any = None, stage: str = "progress"):
        """Emit a progress trace event.
        
        Args:
            data: Optional data specific to the progress update.
            stage: The progress stage name.
        """
        current_time = datetime.datetime.now()
        duration_ms = int((current_time - self.start_time).total_seconds() * 1000)
        
        # Emit progress trace event
        self.tracing_system.emit_trace(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            trace_level=self.trace_level,
            operation=self.operation,
            stage=stage,
            request_id=self.request_id,
            data=data or self.data,
            duration_ms=duration_ms
        )
