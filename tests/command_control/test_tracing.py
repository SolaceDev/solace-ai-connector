"""Unit tests for the TracingSystem and TraceContext classes."""

import unittest
from unittest.mock import MagicMock, patch
import datetime

from src.solace_ai_connector.command_control.tracing import TracingSystem, TraceLevel, TraceContext


class TestTracingSystem(unittest.TestCase):
    """Test cases for the TracingSystem class."""

    def setUp(self):
        """Set up test fixtures."""
        self.broker_adapter = MagicMock()
        self.tracing_system = TracingSystem(self.broker_adapter)

    def test_init(self):
        """Test initialization of TracingSystem."""
        self.assertEqual(self.tracing_system.broker_adapter, self.broker_adapter)
        self.assertTrue(self.tracing_system.enabled)
        self.assertEqual(self.tracing_system.default_level, TraceLevel.INFO)
        self.assertEqual(self.tracing_system.entity_levels, {})

    def test_set_broker_adapter(self):
        """Test setting the broker adapter."""
        # Test data
        new_adapter = MagicMock()
        
        # Call the method
        self.tracing_system.set_broker_adapter(new_adapter)
        
        # Verify the broker adapter was set
        self.assertEqual(self.tracing_system.broker_adapter, new_adapter)

    def test_emit_trace(self):
        """Test emitting a trace event."""
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
        
        # Mock the _publish_trace method
        self.tracing_system._publish_trace = MagicMock()
        
        # Call the method
        self.tracing_system.emit_trace(
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
        
        # Verify _publish_trace was called
        self.tracing_system._publish_trace.assert_called_once()
        call_args = self.tracing_system._publish_trace.call_args[0]
        self.assertEqual(call_args[0], entity_id)
        self.assertEqual(call_args[1], trace_level)
        trace_event = call_args[2]
        self.assertEqual(trace_event["entity_id"], entity_id)
        self.assertEqual(trace_event["entity_type"], entity_type)
        self.assertEqual(trace_event["trace_level"], trace_level)
        self.assertEqual(trace_event["request_id"], request_id)
        self.assertEqual(trace_event["operation"], operation)
        self.assertEqual(trace_event["stage"], stage)
        self.assertEqual(trace_event["data"], data)
        self.assertEqual(trace_event["error"], error)
        self.assertEqual(trace_event["duration_ms"], duration_ms)
        self.assertIn("timestamp", trace_event)

    def test_emit_trace_disabled(self):
        """Test emitting a trace event when tracing is disabled."""
        # Disable tracing
        self.tracing_system.enabled = False
        
        # Mock the _publish_trace method
        self.tracing_system._publish_trace = MagicMock()
        
        # Call the method
        self.tracing_system.emit_trace(
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="INFO",
            operation="test-operation",
            stage="start"
        )
        
        # Verify _publish_trace was not called
        self.tracing_system._publish_trace.assert_not_called()

    def test_emit_trace_entity_level(self):
        """Test emitting a trace event with entity-specific level."""
        # Set entity-specific level
        self.tracing_system.entity_levels = {
            "test-entity": TraceLevel.ERROR
        }
        
        # Mock the _publish_trace method
        self.tracing_system._publish_trace = MagicMock()
        
        # Call the method with a lower level
        self.tracing_system.emit_trace(
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="INFO",
            operation="test-operation",
            stage="start"
        )
        
        # Verify _publish_trace was not called
        self.tracing_system._publish_trace.assert_not_called()
        
        # Call the method with a matching level
        self.tracing_system.emit_trace(
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="ERROR",
            operation="test-operation",
            stage="start"
        )
        
        # Verify _publish_trace was called
        self.tracing_system._publish_trace.assert_called_once()

    def test_emit_trace_invalid_level(self):
        """Test emitting a trace event with an invalid level."""
        # Mock the _publish_trace method
        self.tracing_system._publish_trace = MagicMock()
        
        # Call the method with an invalid level
        self.tracing_system.emit_trace(
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="INVALID",
            operation="test-operation",
            stage="start"
        )
        
        # Verify _publish_trace was called with INFO level
        self.tracing_system._publish_trace.assert_called_once()
        self.assertEqual(self.tracing_system._publish_trace.call_args[0][1], "INFO")

    def test_publish_trace(self):
        """Test publishing a trace event."""
        # Test data
        entity_id = "test-entity"
        level = "INFO"
        trace_event = {"test": "event"}
        
        # Call the method
        self.tracing_system._publish_trace(entity_id, level, trace_event)
        
        # Verify the broker adapter was called
        self.broker_adapter.publish_trace.assert_called_once_with(
            entity_id, level, trace_event
        )

    def test_publish_trace_no_adapter(self):
        """Test publishing a trace event with no broker adapter."""
        # Set the broker adapter to None
        self.tracing_system.broker_adapter = None
        
        # Test data
        entity_id = "test-entity"
        level = "INFO"
        trace_event = {"test": "event"}
        
        # Call the method
        self.tracing_system._publish_trace(entity_id, level, trace_event)
        
        # No assertion needed, just verifying it doesn't raise an exception

    def test_get_level_value(self):
        """Test getting the numeric value of a trace level."""
        # Test data
        debug = TraceLevel.DEBUG
        info = TraceLevel.INFO
        warn = TraceLevel.WARN
        error = TraceLevel.ERROR
        
        # Call the method
        debug_value = self.tracing_system._get_level_value(debug)
        info_value = self.tracing_system._get_level_value(info)
        warn_value = self.tracing_system._get_level_value(warn)
        error_value = self.tracing_system._get_level_value(error)
        
        # Verify the results
        self.assertEqual(debug_value, 0)
        self.assertEqual(info_value, 1)
        self.assertEqual(warn_value, 2)
        self.assertEqual(error_value, 3)
        
        # Verify the ordering
        self.assertLess(debug_value, info_value)
        self.assertLess(info_value, warn_value)
        self.assertLess(warn_value, error_value)

    def test_set_enabled(self):
        """Test enabling and disabling tracing."""
        # Call the method
        self.tracing_system.set_enabled(False)
        
        # Verify the result
        self.assertFalse(self.tracing_system.enabled)
        
        # Call the method again
        self.tracing_system.set_enabled(True)
        
        # Verify the result
        self.assertTrue(self.tracing_system.enabled)

    def test_set_default_level(self):
        """Test setting the default trace level."""
        # Call the method
        self.tracing_system.set_default_level("DEBUG")
        
        # Verify the result
        self.assertEqual(self.tracing_system.default_level, TraceLevel.DEBUG)
        
        # Call the method with an invalid level
        self.tracing_system.set_default_level("INVALID")
        
        # Verify the level was not changed
        self.assertEqual(self.tracing_system.default_level, TraceLevel.DEBUG)

    def test_set_entity_level(self):
        """Test setting the trace level for a specific entity."""
        # Call the method
        self.tracing_system.set_entity_level("test-entity", "DEBUG")
        
        # Verify the result
        self.assertEqual(self.tracing_system.entity_levels["test-entity"], TraceLevel.DEBUG)
        
        # Call the method with an invalid level
        self.tracing_system.set_entity_level("test-entity", "INVALID")
        
        # Verify the level was not changed
        self.assertEqual(self.tracing_system.entity_levels["test-entity"], TraceLevel.DEBUG)

    def test_get_configuration(self):
        """Test getting the current tracing configuration."""
        # Set up test data
        self.tracing_system.enabled = True
        self.tracing_system.default_level = TraceLevel.INFO
        self.tracing_system.entity_levels = {
            "entity1": TraceLevel.DEBUG,
            "entity2": TraceLevel.ERROR
        }
        
        # Call the method
        config = self.tracing_system.get_configuration()
        
        # Verify the result
        self.assertEqual(config["enabled"], True)
        self.assertEqual(config["default_level"], "INFO")
        self.assertEqual(config["entity_levels"], {
            "entity1": "DEBUG",
            "entity2": "ERROR"
        })

    def test_get_entity_configuration(self):
        """Test getting the tracing configuration for a specific entity."""
        # Set up test data
        self.tracing_system.enabled = True
        self.tracing_system.entity_levels = {
            "entity1": TraceLevel.DEBUG
        }
        
        # Call the method for an entity with a specific level
        config = self.tracing_system.get_entity_configuration("entity1")
        
        # Verify the result
        self.assertEqual(config["entity_id"], "entity1")
        self.assertEqual(config["enabled"], True)
        self.assertEqual(config["level"], "DEBUG")
        
        # Call the method for an entity with no specific level
        config = self.tracing_system.get_entity_configuration("entity2")
        
        # Verify the result
        self.assertEqual(config["entity_id"], "entity2")
        self.assertEqual(config["enabled"], True)
        self.assertEqual(config["level"], "INFO")  # Default level

    def test_update_configuration(self):
        """Test updating the tracing configuration."""
        # Test data
        config = {
            "enabled": False,
            "default_level": "DEBUG",
            "entity_levels": {
                "entity1": "ERROR",
                "entity2": "WARN"
            }
        }
        
        # Call the method
        result = self.tracing_system.update_configuration(config)
        
        # Verify the result
        self.assertTrue(result)
        self.assertFalse(self.tracing_system.enabled)
        self.assertEqual(self.tracing_system.default_level, TraceLevel.DEBUG)
        self.assertEqual(self.tracing_system.entity_levels["entity1"], TraceLevel.ERROR)
        self.assertEqual(self.tracing_system.entity_levels["entity2"], TraceLevel.WARN)

    def test_update_configuration_partial(self):
        """Test updating the tracing configuration with partial data."""
        # Set up initial state
        self.tracing_system.enabled = True
        self.tracing_system.default_level = TraceLevel.INFO
        self.tracing_system.entity_levels = {
            "entity1": TraceLevel.DEBUG
        }
        
        # Test data
        config = {
            "default_level": "ERROR"
        }
        
        # Call the method
        result = self.tracing_system.update_configuration(config)
        
        # Verify the result
        self.assertTrue(result)
        self.assertTrue(self.tracing_system.enabled)  # Unchanged
        self.assertEqual(self.tracing_system.default_level, TraceLevel.ERROR)  # Changed
        self.assertEqual(self.tracing_system.entity_levels["entity1"], TraceLevel.DEBUG)  # Unchanged

    def test_update_configuration_error(self):
        """Test updating the tracing configuration with an error."""
        # Mock the set_default_level method to raise an exception
        self.tracing_system.set_default_level = MagicMock(side_effect=Exception("Test exception"))
        
        # Test data
        config = {
            "default_level": "DEBUG"
        }
        
        # Call the method
        result = self.tracing_system.update_configuration(config)
        
        # Verify the result
        self.assertFalse(result)


class TestTraceContext(unittest.TestCase):
    """Test cases for the TraceContext class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracing_system = MagicMock()
        self.context = TraceContext(
            tracing_system=self.tracing_system,
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="INFO",
            operation="test-operation",
            request_id="test-request-id",
            data={"test": "data"}
        )

    def test_init(self):
        """Test initialization of TraceContext."""
        self.assertEqual(self.context.tracing_system, self.tracing_system)
        self.assertEqual(self.context.entity_id, "test-entity")
        self.assertEqual(self.context.entity_type, "test-type")
        self.assertEqual(self.context.trace_level, "INFO")
        self.assertEqual(self.context.operation, "test-operation")
        self.assertEqual(self.context.request_id, "test-request-id")
        self.assertEqual(self.context.data, {"test": "data"})
        self.assertIsNone(self.context.start_time)
        self.assertIsNone(self.context.error)

    def test_enter(self):
        """Test entering the context manager."""
        # Call the method
        result = self.context.__enter__()
        
        # Verify the result
        self.assertEqual(result, self.context)
        self.assertIsNotNone(self.context.start_time)
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once_with(
            entity_id="test-entity",
            entity_type="test-type",
            trace_level="INFO",
            operation="test-operation",
            stage="start",
            request_id="test-request-id",
            data={"test": "data"}
        )

    def test_exit_no_exception(self):
        """Test exiting the context manager with no exception."""
        # Set up the start time
        self.context.start_time = datetime.datetime.now()
        
        # Call the method
        result = self.context.__exit__(None, None, None)
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once()
        call_kwargs = self.tracing_system.emit_trace.call_args[1]
        self.assertEqual(call_kwargs["entity_id"], "test-entity")
        self.assertEqual(call_kwargs["entity_type"], "test-type")
        self.assertEqual(call_kwargs["trace_level"], "INFO")
        self.assertEqual(call_kwargs["operation"], "test-operation")
        self.assertEqual(call_kwargs["stage"], "completion")
        self.assertEqual(call_kwargs["request_id"], "test-request-id")
        self.assertEqual(call_kwargs["data"], {"test": "data"})
        self.assertIsNone(call_kwargs["error"])
        self.assertIsNotNone(call_kwargs["duration_ms"])

    def test_exit_with_exception(self):
        """Test exiting the context manager with an exception."""
        #  Set up the start time
        self.context.start_time = datetime.datetime.now()
        
        # Test data
        exc_type = ValueError
        exc_val = ValueError("Test exception")
        exc_tb = MagicMock()
        
        # Call the method
        result = self.context.__exit__(exc_type, exc_val, exc_tb)
        
        # Verify the result
        self.assertFalse(result)
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once()
        call_kwargs = self.tracing_system.emit_trace.call_args[1]
        self.assertEqual(call_kwargs["entity_id"], "test-entity")
        self.assertEqual(call_kwargs["entity_type"], "test-type")
        self.assertEqual(call_kwargs["trace_level"], "ERROR")
        self.assertEqual(call_kwargs["operation"], "test-operation")
        self.assertEqual(call_kwargs["stage"], "completion")
        self.assertEqual(call_kwargs["request_id"], "test-request-id")
        self.assertEqual(call_kwargs["data"], {"test": "data"})
        self.assertIsNotNone(call_kwargs["error"])
        self.assertEqual(call_kwargs["error"]["message"], "Test exception")
        self.assertEqual(call_kwargs["error"]["type"], "ValueError")
        self.assertIsNotNone(call_kwargs["duration_ms"])
        
        # Verify the error was stored
        self.assertIsNotNone(self.context.error)
        self.assertEqual(self.context.error["message"], "Test exception")
        self.assertEqual(self.context.error["type"], "ValueError")

    def test_progress(self):
        """Test emitting a progress trace event."""
        # Set up the start time
        self.context.start_time = datetime.datetime.now()
        
        # Test data
        progress_data = {"progress": 50}
        
        # Call the method
        self.context.progress(progress_data)
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once()
        call_kwargs = self.tracing_system.emit_trace.call_args[1]
        self.assertEqual(call_kwargs["entity_id"], "test-entity")
        self.assertEqual(call_kwargs["entity_type"], "test-type")
        self.assertEqual(call_kwargs["trace_level"], "INFO")
        self.assertEqual(call_kwargs["operation"], "test-operation")
        self.assertEqual(call_kwargs["stage"], "progress")
        self.assertEqual(call_kwargs["request_id"], "test-request-id")
        self.assertEqual(call_kwargs["data"], progress_data)
        self.assertIsNotNone(call_kwargs["duration_ms"])

    def test_progress_custom_stage(self):
        """Test emitting a progress trace event with a custom stage."""
        # Set up the start time
        self.context.start_time = datetime.datetime.now()
        
        # Test data
        progress_data = {"progress": 50}
        
        # Call the method
        self.context.progress(progress_data, "custom-stage")
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once()
        call_kwargs = self.tracing_system.emit_trace.call_args[1]
        self.assertEqual(call_kwargs["stage"], "custom-stage")

    def test_progress_no_data(self):
        """Test emitting a progress trace event with no data."""
        # Set up the start time
        self.context.start_time = datetime.datetime.now()
        
        # Call the method
        self.context.progress()
        
        # Verify emit_trace was called
        self.tracing_system.emit_trace.assert_called_once()
        call_kwargs = self.tracing_system.emit_trace.call_args[1]
        self.assertEqual(call_kwargs["data"], {"test": "data"})  # Original data


if __name__ == "__main__":
    unittest.main()
