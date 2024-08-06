import threading
import queue
import traceback
import pprint
from abc import abstractmethod
from ..common.log import log
from ..common.utils import resolve_config_values
from ..common.utils import get_source_expression
from ..transforms.transforms import Transforms
from ..common.message import Message
from ..common.trace_message import TraceMessage
from ..common.event import Event, EventType

DEFAULT_QUEUE_TIMEOUT_MS = 200
DEFAULT_QUEUE_MAX_DEPTH = 5


class ComponentBase:
    def __init__(self, module_info, **kwargs):
        self.module_info = module_info
        self.config = kwargs.pop("config", {})
        self.index = kwargs.pop("index", None)
        self.flow_name = kwargs.pop("flow_name", None)
        self.flow_lock_manager = kwargs.pop("flow_lock_manager", None)
        self.flow_kv_store = kwargs.pop("flow_kv_store", None)
        self.stop_signal = kwargs.pop("stop_signal", None)
        self.sibling_component = kwargs.pop("sibling_component", None)
        self.component_index = kwargs.pop("component_index", None)
        self.error_queue = kwargs.pop("error_queue", None)
        self.instance_name = kwargs.pop("instance_name", None)
        self.storage_manager = kwargs.pop("storage_manager", None)
        self.trace_queue = kwargs.pop("trace_queue", False)
        self.connector = kwargs.pop("connector", None)
        self.timer_manager = kwargs.pop("timer_manager", None)
        self.cache_service = kwargs.pop("cache_service", None)

        self.component_config = self.config.get("component_config") or {}
        self.name = self.config.get("component_name", "<unnamed>")

        resolve_config_values(self.component_config)

        self.next_component = None
        self.thread = None
        self.queue_timeout_ms = DEFAULT_QUEUE_TIMEOUT_MS
        self.need_acknowledgement = False
        self.stop_thread_event = threading.Event()
        self.current_message = None
        self.current_message_has_been_discarded = False

        self.log_identifier = f"[{self.instance_name}.{self.flow_name}.{self.name}] "

        # Remove this since it will dump out some secrets
        # log.debug(
        #     "%sCreating component %s with config %s",
        #     self.log_identifier,
        #     self.name,
        #     self.config,
        # )
        self.validate_config()
        self.setup_transforms()
        self.setup_communications()

    def create_thread_and_run(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        return self.thread

    def run(self):
        while not self.stop_signal.is_set():
            event = None
            try:
                event = self.get_next_event()
                if event is not None:
                    if self.trace_queue:
                        self.trace_event(event)
                    self.process_event(event)
            except Exception as e:
                log.error(
                    "%sComponent has crashed: %s\n%s",
                    self.log_identifier,
                    e,
                    traceback.format_exc(),
                )
                if self.error_queue:
                    self.handle_error(e, event)

        self.stop_component()

    def get_next_event(self):
        # Check if there is a get_next_message defined by a
        # component that inherits from this class - this is
        # for backwards compatibility with older components
        sub_method = self.__class__.__dict__.get("get_next_message")

        if sub_method is not None and callable(sub_method):
            # Call the sub-classes get_next_message method and wrap it in an event
            message = self.get_next_message()  # pylint: disable=assignment-from-none
            if message is not None:
                return Event(EventType.MESSAGE, message)
            return None
        while not self.stop_signal.is_set():
            try:
                timeout = self.queue_timeout_ms or DEFAULT_QUEUE_TIMEOUT_MS
                event = self.input_queue.get(timeout=timeout / 1000)
                log.debug(
                    "%sComponent received event %s from input queue",
                    self.log_identifier,
                    event,
                )
                return event
            except queue.Empty:
                pass
        return None

    def get_next_message(self):
        return None

    def process_event(self, event):
        if event.event_type == EventType.MESSAGE:
            message = event.data
            self.current_message = message
            data = self.process_pre_invoke(message)

            if self.trace_queue:
                self.trace_data(data)

            self.current_message_has_been_discarded = False
            result = self.invoke(message, data)

            if self.current_message_has_been_discarded:
                message.call_acknowledgements()
            elif result is not None:
                self.process_post_invoke(result, message)
            self.current_message = None
        elif event.event_type == EventType.TIMER:
            self.handle_timer_event(event.data)
        else:
            log.warning(
                "%sUnknown event type: %s", self.log_identifier, event.event_type
            )

    def process_pre_invoke(self, message):
        self.apply_input_transforms(message)
        return self.get_input_data(message)

    def process_post_invoke(self, result, message):
        message.set_previous(result)
        callback = (  # pylint: disable=assignment-from-none
            self.get_acknowledgement_callback()
        )
        if callback is not None:
            message.add_acknowledgement(callback)

        # Finally send the message to the next component - or if this is the last component,
        # the component will override send_message and do whatever it needs to do with the message
        log.debug(
            "%sSending message from %s: %s", self.log_identifier, self.name, message
        )
        self.send_message(message)

    @abstractmethod
    def invoke(self, message, data):
        pass

    def handle_timer_event(self, timer_data):
        # This method can be overridden by components that need to handle timer events
        pass

    def discard_current_message(self):
        # If the message is to be discarded, we need to acknowledge any previous components
        self.current_message_has_been_discarded = True

    def get_acknowledgement_callback(self):
        # This should be overridden by the component if it needs to acknowledge messages
        return None

    def get_input_data(self, message):
        component_input = self.config.get("component_input") or {
            "source_expression": "previous"
        }
        source_expression = get_source_expression(component_input)

        # This should be overridden by the component if it needs to extract data from the message
        return message.get_data(source_expression, self)

    def get_input_queue(self):
        return self.input_queue

    def apply_input_transforms(self, message):
        self.transforms.transform(message, calling_object=self)

    def send_message(self, message):
        if self.next_component is None:
            # This is the last component in the flow
            log.debug(
                "%sComponent %s is the last component in the flow, so not sending message",
                self.log_identifier,
                self.name,
            )
            message.call_acknowledgements()
            return
        event = Event(EventType.MESSAGE, message)
        self.next_component.enqueue(event)

    def send_to_flow(self, flow_name, message):
        if self.connector:
            self.connector.send_message_to_flow(flow_name, message)

    def enqueue(self, event):
        do_loop = True
        while not self.stop_signal.is_set() and do_loop:
            try:
                self.input_queue.put(event, timeout=1)
                do_loop = False
            except queue.Full:
                pass

    def get_config(self, key=None, default=None):
        val = self.component_config.get(key, None)
        if val is None:
            val = self.config.get(key, default)
        if callable(val):
            if self.current_message is None:
                raise ValueError(
                    f"Component {self.log_identifier} is trying to use an `invoke` config "
                    "that contains a 'source_expression()' in a context that does not "
                    "have a message available. This is likely a bug in the "
                    "component's configuration."
                )
            val = val(self.current_message)
        return val

    def resolve_callable_config(self, config, message):
        # If the value is callable, call it with the message
        # If it is a dictionary, then resolve any callable values in the dictionary (recursively)
        if isinstance(config, dict):
            for key, value in config.items():
                config[key] = self.resolve_callable_config(value, message)
        elif callable(config):
            config = config(message)
        return config

    def set_next_component(self, next_component):
        self.next_component = next_component

    def get_next_component(self):
        return self.next_component

    def get_lock(self, lock_name):
        return self.flow_lock_manager.get_lock(lock_name)

    def kv_store_get(self, key):
        return self.flow_kv_store.get(key)

    def kv_store_set(self, key, value):
        self.flow_kv_store.set(key, value)

    def setup_communications(self):
        self.queue_max_depth = self.config.get(
            "component_queue_max_depth", DEFAULT_QUEUE_MAX_DEPTH
        )
        self.need_acknowledgement = False
        self.next_component = None

        if self.sibling_component:
            self.input_queue = self.sibling_component.get_input_queue()
        else:
            self.input_queue = queue.Queue(maxsize=self.queue_max_depth)

    def setup_transforms(self):
        self.transforms = Transforms(
            self.config.get("input_transforms", []), log_identifier=self.log_identifier
        )

    def validate_config(self):
        config_params = self.module_info.get("config_parameters", [])
        # Loop through the parameters and make sure they are all present if they are required
        # and set the default if it is not present
        for param in config_params:
            name = param.get("name", None)
            if name is None:
                raise ValueError(
                    f"config_parameters schema for module {self.config.get('component_module')} "
                    "does not have a name: {param}"
                )
            required = param.get("required", False)
            if required and name not in self.component_config:
                raise ValueError(
                    f"Config parameter {name} is required but not present in component {self.name}"
                )
            default = param.get("default", None)
            if default is not None and name not in self.component_config:
                self.component_config[name] = default

    def trace_event(self, event):
        trace_message = TraceMessage(
            location=self.log_identifier,
            message=f"Received event: {event}",
            trace_type="Event Received",
        )
        self.trace_queue.put(trace_message)

    def trace_data(self, data):
        trace_string = pprint.pformat(data, indent=4)
        self.trace_queue.put(
            TraceMessage(
                message=trace_string,
                location=self.log_identifier,
                trace_type="Component Input Data",
            )
        )

    def handle_error(self, exception, event):
        error_message = {
            "error": {
                "text": str(exception),
                "exception": type(exception).__name__,
            },
            "location": {
                "instance": self.instance_name,
                "flow": self.flow_name,
                "component": self.name,
                "component_index": self.component_index,
            },
        }
        if event and event.event_type == EventType.MESSAGE:
            message = event.data
            if message:
                error_message["message"] = {
                    "payload": message.get_payload(),
                    "topic": message.get_topic(),
                    "user_properties": message.get_user_properties(),
                    "user_data": message.get_user_data(),
                    "previous": message.get_previous(),
                }
                message.call_acknowledgements()
            else:
                error_message["message"] = "No message available"

        self.error_queue.put(
            Event(
                EventType.MESSAGE,
                Message(
                    payload=error_message,
                    user_properties=message.get_user_properties() if message else {},
                ),
            )
        )

    def add_timer(self, delay_ms, timer_id, interval_ms=None, payload=None):
        if self.timer_manager:
            self.timer_manager.add_timer(delay_ms, self, timer_id, interval_ms, payload)

    def cancel_timer(self, timer_id):
        if self.timer_manager:
            self.timer_manager.cancel_timer(self, timer_id)

    def stop_component(self):
        # This should be overridden by the component if needed
        pass

    def cleanup(self):
        """Clean up resources used by the component"""
        log.debug("%sCleaning up component", self.log_identifier)
        self.stop_component()
        if hasattr(self, "input_queue"):
            while not self.input_queue.empty():
                try:
                    self.input_queue.get_nowait()
                except queue.Empty:
                    break
