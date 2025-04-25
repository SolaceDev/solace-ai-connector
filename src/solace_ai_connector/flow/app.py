"""App class for the Solace AI Event Connector"""

from typing import List, Dict, Any, Optional
import os
from copy import deepcopy  # Import deepcopy

from ..common.log import log
from .flow import Flow
from ..common.utils import deep_merge  # Import deep_merge
from .request_response_flow_controller import RequestResponseFlowController


class App:
    """
    App class for the Solace AI Event Connector.
    An app is a collection of flows that are logically grouped together.
    """

    def __init__(
        self,
        app_info: Dict[str, Any],
        app_index: int,
        stop_signal,
        error_queue=None,
        instance_name=None,
        trace_queue=None,
        connector=None,
    ):
        """
        Initialize the App.

        Args:
            app_info: Info and configuration for the app (typically from YAML).
            app_index: Index of the app in the list of apps
            stop_signal: Signal to stop the app
            error_queue: Queue for error messages
            instance_name: Name of the connector instance
            trace_queue: Queue for trace messages
            connector: Reference to the parent connector
        """
        # Check if this is a custom App subclass with code-defined config
        code_config = None
        # Use 'app_config' as the standard name for code-defined config as well
        if hasattr(self.__class__, "app_config") and isinstance(
            self.__class__.app_config, dict
        ):
            log.debug("Found code-defined app_config in %s", self.__class__.__name__)
            code_config = self.__class__.app_config

        # Merge configurations: YAML (app_info) overrides code_config
        if code_config:
            # Perform a deep merge, giving precedence to app_info (YAML)
            merged_app_info = deep_merge(code_config, app_info)
            log.debug(
                "Merged app config for %s", merged_app_info.get("name", "unnamed app")
            )
        else:
            merged_app_info = app_info

        # Store the final merged config
        self.app_info = merged_app_info
        # Extract app_config for get_config() - this is the 'app_config' block within the app definition
        self.app_config = self.app_info.get(
            "app_config", {}
        )  # <-- Changed "config" to "app_config"
        self.app_index = app_index
        # Derive name from merged config
        self.name = self.app_info.get("name", f"app_{app_index}")
        self.num_instances = self.app_info.get("num_instances", 1)
        self.flows: List[Flow] = []
        self.stop_signal = stop_signal
        self.error_queue = error_queue
        self.instance_name = instance_name
        self.trace_queue = trace_queue
        self.connector = connector
        self.flow_input_queues = {}
        self._broker_output_component = None  # Cache for send_message
        self.request_response_controller = None  # Initialize RRC attribute

        broker_config = self.app_info.get("broker", {})
        if broker_config.get("request_reply_enabled", False):
            log.info(
                "Request-reply enabled for app '%s'. Initializing controller.",
                self.name,
            )
            try:
                # Instantiate RequestResponseFlowController
                # Pass the broker config section and the connector reference
                self.request_response_controller = RequestResponseFlowController(
                    config={
                        "broker_config": broker_config
                    },  # Pass broker config under 'broker_config' key
                    connector=self.connector,
                )
                # Store controller instance (already done by assignment above)
            except Exception as e:
                log.error(
                    "Failed to initialize RequestResponseFlowController for app '%s': %s",
                    self.name,
                    e,
                    exc_info=True,
                )
                # Decide if this should be a fatal error for the app
                raise e

        # Create flows for this app using the merged configuration
        self.create_flows()

    def create_flows(self):
        """Create flows for this app"""
        try:
            # Detect simplified app configuration
            is_simplified = (
                "broker" in self.app_info
                and "components" in self.app_info
                and "flows" not in self.app_info
            )

            if is_simplified:
                # Call helper to generate implicit flow config
                log.info("Creating simplified app flow for %s", self.name)
                flow_config = self._create_simplified_flow_config()
                # Create the single implicit flow
                flow_instance = self.create_flow(flow_config, 0, 0)
                flow_input_queue = flow_instance.get_flow_input_queue()
                self.flow_input_queues[flow_config.get("name")] = flow_input_queue
                self.flows.append(flow_instance)
            else:
                # Keep existing logic for standard flows defined in 'flows' list
                for index, flow in enumerate(self.app_info.get("flows", [])):
                    log.info(
                        "Creating flow %s in app %s", flow.get("name"), self.name
                    )
                    num_instances = flow.get("num_instances", 1)
                    if num_instances < 1:
                        num_instances = 1
                    for i in range(num_instances):
                        flow_instance = self.create_flow(flow, index, i)
                        flow_input_queue = flow_instance.get_flow_input_queue()
                        self.flow_input_queues[flow.get("name")] = flow_input_queue
                        self.flows.append(flow_instance)
        except Exception as e:
            log.error("Error creating flows for app %s: %s", self.name, e)
            raise e

    def _create_simplified_flow_config(self) -> Dict[str, Any]:
        """Creates the implicit flow configuration for a simplified app."""
        broker_config = self.app_info.get("broker", {})
        user_components = self.app_info.get("components", [])
        flow_components = []

        # Add BrokerInput if enabled
        if broker_config.get("input_enabled", False):
            # Collect all subscriptions from user components
            all_subscriptions = [
                sub for comp in user_components for sub in comp.get("subscriptions", [])
            ]
            if not all_subscriptions:
                log.warning(
                    "Simplified app '%s' has input_enabled=true but no subscriptions defined in components.",
                    self.name,
                )

            input_comp_config = {
                "component_name": f"{self.name}_broker_input",
                "component_module": "broker_input",
                # Pass relevant broker config keys to BrokerInput's component_config
                "component_config": {
                    "broker_type": broker_config.get("broker_type"),
                    "dev_mode": broker_config.get("dev_mode"),
                    "broker_url": broker_config.get("broker_url"),
                    "broker_username": broker_config.get("broker_username"),
                    "broker_password": broker_config.get("broker_password"),
                    "broker_vpn": broker_config.get("broker_vpn"),
                    "reconnection_strategy": broker_config.get("reconnection_strategy"),
                    "retry_interval": broker_config.get("retry_interval"),
                    "retry_count": broker_config.get("retry_count"),
                    "trust_store_path": broker_config.get("trust_store_path"),
                    "broker_queue_name": broker_config.get(
                        "queue_name"
                    ),  # Use the main queue name
                    "create_queue_on_start": broker_config.get(
                        "create_queue_on_start", True
                    ),
                    "payload_encoding": broker_config.get("payload_encoding", "utf-8"),
                    "payload_format": broker_config.get("payload_format", "json"),
                    "max_redelivery_count": broker_config.get("max_redelivery_count"),
                    "broker_subscriptions": all_subscriptions,  # Pass collected subscriptions
                },
            }
            flow_components.append(input_comp_config)

        # Add SubscriptionRouter if needed (input enabled and more than one user component)
        if broker_config.get("input_enabled", False) and len(user_components) > 1:
            router_comp_config = {
                "component_name": f"{self.name}_router",
                "component_module": "subscription_router",  # Assuming this module exists
                # Router needs access to the app's component list for routing rules
                "component_config": {
                    # Pass the original user components list as defined in the app config
                    "app_components_config_ref": self.app_info.get("components", [])
                },
            }
            flow_components.append(router_comp_config)

        # Add User Components (make a deep copy to avoid modification issues)
        flow_components.extend(deepcopy(user_components))

        # Add BrokerOutput if enabled
        if broker_config.get("output_enabled", False):
            output_comp_config = {
                "component_name": f"{self.name}_broker_output",
                "component_module": "broker_output",
                # Pass relevant broker config keys to BrokerOutput's component_config
                "component_config": {
                    "broker_type": broker_config.get("broker_type"),
                    "dev_mode": broker_config.get("dev_mode"),
                    "broker_url": broker_config.get("broker_url"),
                    "broker_username": broker_config.get("broker_username"),
                    "broker_password": broker_config.get("broker_password"),
                    "broker_vpn": broker_config.get("broker_vpn"),
                    "reconnection_strategy": broker_config.get("reconnection_strategy"),
                    "retry_interval": broker_config.get("retry_interval"),
                    "retry_count": broker_config.get("retry_count"),
                    "trust_store_path": broker_config.get("trust_store_path"),
                    "payload_encoding": broker_config.get("payload_encoding", "utf-8"),
                    "payload_format": broker_config.get("payload_format", "json"),
                    "propagate_acknowledgements": broker_config.get(
                        "propagate_acknowledgements", True
                    ),
                    # Add other relevant output-specific configs if needed
                },
            }
            flow_components.append(output_comp_config)

        # Construct the final flow dictionary
        return {"name": f"{self.name}_implicit_flow", "components": flow_components}

    def create_flow(self, flow: dict, index: int, flow_instance_index: int) -> Flow:
        """
        Create a single flow.

        Args:
            flow: Flow configuration
            index: Index of the flow in the list of flows
            flow_instance_index: Index of the flow instance

        Returns:
            Flow: The created flow
        """
        return Flow(
            flow_config=flow,
            flow_index=index,
            flow_instance_index=flow_instance_index,
            stop_signal=self.stop_signal,
            error_queue=self.error_queue,
            instance_name=self.instance_name,
            trace_queue=self.trace_queue,
            connector=self.connector,
            app=self,
        )

    def run(self):
        """Run all flows in the app"""
        for flow in self.flows:
            flow.run()

    def wait_for_flows(self):
        """Wait for all flows to complete"""
        for flow in self.flows:
            flow.wait_for_threads()

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info("Cleaning up app: %s", self.name)
        # Clean up the request response controller if it exists
        if self.request_response_controller:
            try:
                # Assuming RRC has a cleanup method or similar
                # If not, cleanup might involve stopping its internal flow/app
                # For now, we rely on the connector cleaning up all apps/flows
                pass  # RRC's internal app/flow will be cleaned by connector.cleanup()
            except Exception as e:
                log.error(
                    "Error cleaning up RequestResponseFlowController in app %s: %s",
                    self.name,
                    e,
                )
            self.request_response_controller = None

        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception as e:
                log.error("Error cleaning up flow in app %s: %s", self.name, e)
        self.flows.clear()
        self.flow_input_queues.clear()
        self._broker_output_component = None  # Clear cache

    def get_config(self, key=None, default=None):
        """
        Get a configuration value from the app's 'app_config' block.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        # self.app_config holds the 'app_config:' block from the merged app_info
        return self.app_config.get(key, default)

    def send_message(
        self, payload: Any, topic: str, user_properties: Optional[Dict] = None
    ):
        """
        Sends a message via the implicit BrokerOutput component of a simplified app.

        Args:
            payload: The message payload.
            topic: The destination topic.
            user_properties: Optional dictionary of user properties.
        """
        # Import locally to avoid circular dependency issues at module level
        from ..common.message import Message
        from ..common.event import Event, EventType

        # Check if output is enabled for this app
        if not self.app_info.get("broker", {}).get("output_enabled", False):
            log.warning(
                "App '%s' attempted to send a message, but 'output_enabled' is false. Message discarded.",
                self.name,
            )
            return

        # Find the BrokerOutput component instance (cache it after first find)
        if self._broker_output_component is None:
            broker_output_instance = None
            # Simplified apps have only one flow
            if self.flows:
                flow = self.flows[0]
                # BrokerOutput is typically the last component in the implicit flow
                if flow.component_groups:
                    last_group = flow.component_groups[-1]
                    if last_group:
                        # Check if the last component is indeed BrokerOutput
                        comp = last_group[0]  # Get the first instance in the group
                        if comp.module_info.get("class_name") == "BrokerOutput":
                            broker_output_instance = comp
                        else:
                            # Check component_module as fallback (less reliable)
                            if comp.config.get("component_module") == "broker_output":
                                broker_output_instance = comp

            if broker_output_instance:
                self._broker_output_component = broker_output_instance
            else:
                log.error(
                    "App '%s' could not find the implicit BrokerOutput component to send a message.",
                    self.name,
                )
                return

        # Create the output data structure expected by BrokerOutput
        output_data = {
            "payload": payload,
            "topic": topic,
            "user_properties": user_properties or {},
        }

        # Create a Message object and place the output data in 'previous'
        # This mimics how data flows from a preceding component to BrokerOutput
        msg = Message()
        msg.set_previous(output_data)

        # Create an Event to enqueue
        event = Event(EventType.MESSAGE, msg)

        # Enqueue the event to the BrokerOutput component
        try:
            log.debug(
                "App '%s' sending message via implicit BrokerOutput to topic '%s'",
                self.name,
                topic,
            )
            self._broker_output_component.enqueue(event)
        except Exception as e:
            log.error(
                "App '%s' failed to enqueue message to BrokerOutput: %s",
                self.name,
                e,
                exc_info=True,
            )

    @classmethod
    def create_from_flows(
        cls, flows: List[Dict[str, Any]], app_name: str, **kwargs
    ) -> "App":
        """
        Create an app from a list of flows (for backward compatibility).

        Args:
            flows: List of flow configurations
            app_name: Name for the app
            **kwargs: Additional arguments for App constructor

        Returns:
            App: The created app
        """
        app_info = {"name": app_name, "flows": flows}
        # Note: This path won't automatically merge with code_config unless
        # a specific subclass is used that defines it.
        return cls(app_info=app_info, **kwargs)
