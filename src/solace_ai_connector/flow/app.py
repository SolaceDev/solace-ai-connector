"""App class for the Solace AI Event Connector"""

from typing import List, Dict, Any, Optional
import os

from ..common.log import log
from .flow import Flow
from ..common.utils import deep_merge # Import deep_merge


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
        # 1.2.2 Check if this is a custom App subclass with code-defined config
        code_config = None
        if hasattr(self.__class__, "app_config") and isinstance(self.__class__.app_config, dict):
            log.debug(f"Found code-defined app_config in {self.__class__.__name__}")
            code_config = self.__class__.app_config

        # 1.2.3 Merge configurations: YAML (app_info) overrides code_config
        if code_config:
            # Perform a deep merge, giving precedence to app_info (YAML)
            merged_app_info = deep_merge(code_config, app_info)
            log.debug(f"Merged app config for {merged_app_info.get('name', 'unnamed app')}")
        else:
            merged_app_info = app_info

        # 1.2.4 Store the final merged config
        self.app_info = merged_app_info
        # 1.2.5 Extract app_config for get_config() - this is the 'config' block within the app definition
        self.app_config = self.app_info.get("config", {})
        self.app_index = app_index
        # 1.2.6 Derive name from merged config
        self.name = self.app_info.get("name", f"app_{app_index}")
        self.num_instances = self.app_info.get("num_instances", 1)
        self.flows: List[Flow] = []
        self.stop_signal = stop_signal
        self.error_queue = error_queue
        self.instance_name = instance_name
        self.trace_queue = trace_queue
        self.connector = connector
        self.flow_input_queues = {}

        # Create flows for this app using the merged configuration
        self.create_flows()

    def create_flows(self):
        """Create flows for this app"""
        try:
            for index, flow in enumerate(self.app_info.get("flows", [])):
                log.info(f"Creating flow {flow.get('name')} in app {self.name}")
                num_instances = flow.get("num_instances", 1)
                if num_instances < 1:
                    num_instances = 1
                for i in range(num_instances):
                    flow_instance = self.create_flow(flow, index, i)
                    flow_input_queue = flow_instance.get_flow_input_queue()
                    self.flow_input_queues[flow.get("name")] = flow_input_queue
                    self.flows.append(flow_instance)
        except Exception as e:
            log.error(f"Error creating flows for app {self.name}: {e}")
            raise e

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
        log.info(f"Cleaning up app: {self.name}")
        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception as e:
                log.error(f"Error cleaning up flow in app {self.name}: {e}")
        self.flows.clear()
        self.flow_input_queues.clear()

    def get_config(self, key=None, default=None):
        """
        Get a configuration value from the app's 'config' block.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        # self.app_config holds the 'config:' block from the merged app_info
        return self.app_config.get(key, default)

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
