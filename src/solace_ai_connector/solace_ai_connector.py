"""Entry point for the Solace AI Event Connector"""

import threading
import queue
import traceback

from datetime import datetime
from typing import List
from .common.log import log, setup_log
from .common.utils import resolve_config_values
from .flow.flow import Flow
from .flow.timer_manager import TimerManager
from .common.event import Event, EventType
from .services.cache_service import CacheService, create_storage_backend
from .common.monitoring import Monitoring
from .command_control.command_control_service import CommandControlService
from .command_control.broker_adapter import BrokerAdapter
from .command_control.connector_entity import ConnectorEntity


class SolaceAiConnector:
    """Solace AI Connector"""

    def __init__(self, config, event_handlers=None, error_queue=None):
        self.config = config or {}
        self.flows: List[Flow] = []
        self.trace_queue = None
        self.trace_thread = None
        self.flow_input_queues = {}
        self.stop_signal = threading.Event()
        self.event_handlers = event_handlers or {}
        self.error_queue = error_queue if error_queue else queue.Queue()
        self.setup_logging()
        self.setup_trace()
        resolve_config_values(self.config)
        self.validate_config()
        self.instance_name = self.config.get("instance_name", "solace_ai_connector")
        self.timer_manager = TimerManager(self.stop_signal)
        self.cache_service = self.setup_cache_service()
        self.monitoring = Monitoring(config)

        # Initialize command control system if enabled
        self.command_control_service = None
        self.broker_adapter = None
        self.connector_entity = None
        self.command_control_enabled = self.config.get("command_control", {}).get(
            "enabled", False
        )

        # If command control is enabled, set it up and create the flows immediately
        if self.command_control_enabled:
            self.setup_command_control()
            self.create_command_control_flows()

    def run(self):
        """Run the Solace AI Event Connector"""
        log.info("Starting Solace AI Event Connector")
        try:
            self.create_flows()

            # Call the on_flow_creation event handler
            on_flow_creation = self.event_handlers.get("on_flow_creation")
            if on_flow_creation:
                on_flow_creation(self.flows)

            log.info("Solace AI Event Connector started successfully")
        except KeyboardInterrupt as e:
            log.info("Received keyboard interrupt - stopping")
            raise KeyboardInterrupt from e
        except Exception as e:
            log.error("Error during Solace AI Event Connector startup: %s", str(e))
            log.error("Traceback: %s", traceback.format_exc())
            raise e

    def create_flows(self):
        """Loop through the flows and create them"""
        try:
            for index, flow in enumerate(self.config.get("flows", [])):
                log.info("Creating flow %s", flow.get("name"))
                num_instances = flow.get("num_instances", 1)
                if num_instances < 1:
                    num_instances = 1
                for i in range(num_instances):
                    flow_instance = self.create_flow(flow, index, i)
                    flow_input_queue = flow_instance.get_flow_input_queue()
                    self.flow_input_queues[flow.get("name")] = flow_input_queue
                    self.flows.append(flow_instance)
            for flow in self.flows:
                flow.run()
        except KeyboardInterrupt as e:
            log.info("Received keyboard interrupt - stopping")
            raise KeyboardInterrupt from e
        except Exception as e:
            log.error("Error creating flows: %s", e)
            raise e

    def create_flow(self, flow: dict, index: int, flow_instance_index: int):
        """Create a single flow"""

        return Flow(
            flow_config=flow,
            flow_index=index,
            flow_instance_index=flow_instance_index,
            stop_signal=self.stop_signal,
            error_queue=self.error_queue,
            instance_name=self.instance_name,
            trace_queue=self.trace_queue,
            connector=self,
        )

    def send_message_to_flow(self, flow_name, message):
        """Send a message to a flow"""
        flow_input_queue = self.flow_input_queues.get(flow_name)
        if flow_input_queue:
            event = Event(EventType.MESSAGE, message)
            flow_input_queue.put(event)
        else:
            log.error("Can't send message to flow %s. Not found", flow_name)

    def wait_for_flows(self):
        """Wait for the flows to finish"""
        while not self.stop_signal.is_set():
            try:
                for flow in self.flows:
                    flow.wait_for_threads()
                break
            except KeyboardInterrupt as e:
                log.info("Received keyboard interrupt - stopping")
                raise KeyboardInterrupt from e

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info("Cleaning up Solace AI Event Connector")
        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception as e:
                log.error(f"Error cleaning up flow: {e}")
        self.flows.clear()

        # Clean up queues
        for queue_name, queue in self.flow_input_queues.items():
            try:
                while not queue.empty():
                    queue.get_nowait()
            except Exception as e:
                log.error(f"Error cleaning queue {queue_name}: {e}")
        self.flow_input_queues.clear()

        if hasattr(self, "trace_queue") and self.trace_queue:
            self.trace_queue.put(None)  # Signal the trace thread to stop
        if self.trace_thread:
            self.trace_thread.join()
        if hasattr(self, "cache_check_thread"):
            self.cache_check_thread.join()
        if hasattr(self, "error_queue"):
            self.error_queue.put(None)

        self.timer_manager.cleanup()
        log.info("Cleanup completed")

    def setup_logging(self):
        """Setup logging"""

        log_config = self.config.get("log", {})
        stdout_log_level = log_config.get("stdout_log_level", "INFO")
        log_file_level = log_config.get("log_file_level", "INFO")
        log_file = log_config.get("log_file", "solace_ai_connector.log")
        log_format = log_config.get("log_format", "pipe-delimited")

        # Get logback values
        logback = log_config.get("logback", {})

        setup_log(
            log_file,
            stdout_log_level,
            log_file_level,
            log_format,
            logback,
        )

    def setup_trace(self):
        """Setup trace"""
        trace_config = self.config.get("trace", {})
        trace_file = trace_config.get("trace_file", None)
        if trace_file:
            log.info("Setting up trace to file %s", trace_file)
            # Create a trace queue
            self.trace_queue = queue.Queue()
            # Start a new thread to handle trace messages
            self.trace_thread = threading.Thread(
                target=self.handle_trace, args=(trace_file,), daemon=True
            )
            self.trace_thread.start()

    def handle_trace(self, trace_file):
        """Handle trace messages - this is a separate thead"""

        # Create the trace file
        with open(trace_file, "a", encoding="utf-8") as f:
            while True:
                # Get the next trace message
                try:
                    trace_message = self.trace_queue.get(timeout=1)
                    # Write the trace message to the file with a timestamp
                    timestamp = datetime.now().isoformat()
                    f.write(f"{timestamp}: {trace_message}\n")
                    f.flush()

                except queue.Empty:
                    if self.stop_signal.is_set():
                        break
                    continue

    def validate_config(self):
        """Just some quick validation of the config for now"""
        if not self.config:
            raise ValueError("No config provided")

        if not self.config.get("flows"):
            raise ValueError("No flows defined in configuration file")

        if not self.config.get("log"):
            log.warning("No log config provided - using defaults")

        # Loop through the flows and validate them
        for index, flow in enumerate(self.config.get("flows", [])):
            if not flow.get("name"):
                raise ValueError(f"Flow name not provided in flow {index}")

            if not flow.get("components"):
                raise ValueError(f"Flow components list not provided in flow {index}")

            # Verify that the components list is a list
            if not isinstance(flow.get("components"), list):
                raise ValueError(f"Flow components is not a list in flow {index}")

            # Loop through the components and validate them
            for component_index, component in enumerate(flow.get("components", [])):
                if not component.get("component_name"):
                    raise ValueError(
                        f"component_name not provided in flow {index}, component {component_index}"
                    )

                if not component.get("component_module"):
                    raise ValueError(
                        f"component_module not provided in flow {index}, "
                        f"component {component_index}"
                    )

    def get_flows(self):
        """Return the flows"""
        return self.flows

    def get_flow(self, flow_name):
        """Return a specific flow by name"""
        for flow in self.flows:
            if flow.name == flow_name:
                return flow
        return None

    def setup_cache_service(self):
        """Setup the cache service"""
        cache_config = self.config.get("cache", {})
        backend_type = cache_config.get("backend", "memory")
        backend = create_storage_backend(backend_type)
        return CacheService(backend)

    def stop(self):
        """Stop the Solace AI Event Connector"""
        log.info("Stopping Solace AI Event Connector")
        self.stop_signal.set()

        # Stop core services first
        self.timer_manager.stop()  # Stop the timer manager first
        self.cache_service.stop()  # Stop the cache service

        if self.trace_thread:
            self.trace_thread.join()

    def setup_command_control(self):
        """Set up the command control system."""
        log.info("Setting up command control system")

        # Create the command control service first without a broker adapter
        self.command_control_service = CommandControlService(self)

        # Create the broker adapter and pass the command control service
        self.broker_adapter = BrokerAdapter(self, self.command_control_service)

        # Now set the broker adapter on the command control service using the setter method
        self.command_control_service.set_broker_adapter(self.broker_adapter)

        # Set up the command handler
        self.broker_adapter.set_command_handler(self.handle_command)

        # Create the connector entity
        self.connector_entity = ConnectorEntity(self, self.command_control_service)

        log.info("Command control system initialized")

    def create_command_control_flows(self):
        """Create the command and response flows for the command control system."""
        if not self.command_control_service or not self.broker_adapter:
            log.warning(
                "Command control service not initialized, skipping flow creation"
            )
            return

        log.info("Creating command control flows")

        cc_config = self.config.get("command_control", {})
        cc_broker_config = cc_config.get("broker", {})

        # Create command flow configuration
        command_flow_config = {
            "name": "command_control_command_flow",
            "components": [
                {
                    "component_name": "command_input",
                    "component_module": "broker_input",
                    "component_config": {
                        "broker_type": cc_broker_config.get("broker_type", "solace"),
                        "broker_url": cc_broker_config.get("broker_url"),
                        "broker_username": cc_broker_config.get("broker_username"),
                        "broker_password": cc_broker_config.get("broker_password"),
                        "broker_vpn": cc_broker_config.get("broker_vpn"),
                        "broker_queue_name": cc_broker_config.get(
                            "command_control_queue", "command_control"
                        ),
                        "broker_subscriptions": [
                            {
                                "topic": f"{self.broker_adapter.namespace}/{self.broker_adapter.topic_prefix}/>",
                                "qos": 1,
                            }
                        ],
                        "payload_encoding": "utf-8",
                        "payload_format": "json",
                    },
                },
                {
                    "component_name": "command_handler",
                    "component_module": "handler_callback",
                    "component_config": {
                        "invoke_handler": self.broker_adapter.handle_message
                    },
                },
            ],
        }

        # Create response flow configuration
        response_flow_config = {
            "name": "command_control_response_flow",
            "components": [
                {
                    "component_name": "response_output",
                    "component_module": "broker_output",
                    "component_config": {
                        "broker_type": cc_broker_config.get("broker_type", "solace"),
                        "broker_url": cc_broker_config.get("broker_url"),
                        "broker_username": cc_broker_config.get("broker_username"),
                        "broker_password": cc_broker_config.get("broker_password"),
                        "broker_vpn": cc_broker_config.get("broker_vpn"),
                        "payload_encoding": "utf-8",
                        "payload_format": "json",
                    },
                }
            ],
        }

        # Create the flows
        command_flow = self.create_flow(command_flow_config, len(self.flows), 0)
        response_flow = self.create_flow(response_flow_config, len(self.flows) + 1, 0)

        # Add the flows to the list
        self.flows.append(command_flow)
        self.flows.append(response_flow)

        # Store the flow input queues
        self.flow_input_queues[command_flow_config["name"]] = (
            command_flow.get_flow_input_queue()
        )
        self.flow_input_queues[response_flow_config["name"]] = (
            response_flow.get_flow_input_queue()
        )

        # Start the flows
        command_flow.run()
        response_flow.run()

        # Set up the broker adapter with the flow names
        self.broker_adapter.setup_command_flow(command_flow_config["name"])
        self.broker_adapter.setup_response_flow(response_flow_config["name"])

        log.info("Command control flows created and started")

    def handle_command(self, request):
        """Handle a command request.

        Args:
            request: The command request to handle.
        """
        if not self.command_control_service:
            log.warning("Command control service not initialized, ignoring command")
            return

        # Process the request
        response = self.command_control_service.handle_request(request)

        # Add the reply_to_topic_prefix to the response
        response["reply_to_topic_prefix"] = request.get("reply_to_topic_prefix")

        # Publish the response
        if self.broker_adapter:
            self.broker_adapter.publish_response(response)

    def get_command_control_service(self):
        """Get the command control service.

        Returns:
            The command control service, or None if not enabled.
        """
        return self.command_control_service
