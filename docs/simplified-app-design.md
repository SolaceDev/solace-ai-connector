# Simplified App Mode - Software Design

## 1. Introduction

This document outlines the software design for the "Simplified App Mode" feature in the Solace AI Event Connector. The goal is to provide a streamlined configuration experience for applications whose primary function involves basic interactions with a Solace broker (receive, process, optionally send/request-reply), without requiring the user to explicitly define flows and broker components.

The framework will automatically generate the necessary flow structure based on a simplified application definition provided in the configuration.

## 2. Configuration Structure

Simplified apps are defined under the top-level `apps` list in the main configuration YAML. Each app definition replaces the need for an explicit `flows` list for simple use cases.

```yaml
apps:
  - name: my_simplified_app # Unique name for the app instance
    # Optional: Number of instances of this app definition (defaults to 1)
    # num_instances: 1
    broker:
      # Standard Solace Connection Details
      broker_type: solace # Or dev_broker
      broker_url: <protocol>://<host>:<port>
      broker_vpn: <vpn_name>
      broker_username: <username>
      broker_password: <password>
      # Optional: trust_store_path, reconnection_strategy, retry_interval, retry_count

      # Interaction Flags
      input_enabled: true # If true, listens for messages
      output_enabled: true # If true, allows sending messages
      request_reply_enabled: false # If true, enables self.do_broker_request_response()

      # Input Configuration (if input_enabled: true)
      queue_name: "my_app/input/queue" # The single queue this app listens on
      create_queue_on_start: true # Optional: Default true. Attempts to create the queue.
      # Optional: payload_encoding (default: utf-8), payload_format (default: json)
      # Optional: max_redelivery_count

      # Output Configuration (if output_enabled: true)
      # Optional: payload_encoding (default: utf-8), payload_format (default: json)
      # Optional: propagate_acknowledgements (default: true)

      # Request-Reply Configuration (if request_reply_enabled: true)
      # Optional: request_expiry_ms (default: 60000)
      # Optional: response_topic_prefix (default: "reply")
      # Optional: response_topic_suffix (default: "")
      # Optional: response_queue_prefix (default: "reply-queue")
      # Optional: user_properties_reply_topic_key (default: "__solace_ai_connector_broker_request_response_topic__")
      # Optional: user_properties_reply_metadata_key (default: "__solace_ai_connector_broker_request_reply_metadata__")
      # Optional: response_topic_insertion_expression (default: "")

    # Optional: App-level configuration accessible by components via get_config()
    config:
      param1: value1
      param2: value2

    # List of processing components for this app
    components:
      - name: process_order_component # Unique name within the app
        # Option 1: Specify module for external components
        component_module: process_order # Module name
        # Optional: component_package, component_base_path

        # Option 2: Specify class directly for components defined in the same
        # file as a custom App subclass (requires framework changes)
        # component_class: MyProcessOrderComponent # Actual class object

        num_instances: 2 # Optional: Default 1. Scales this specific component.
        # Optional: disabled (default: false)
        component_config:
          # Standard configuration for the 'process_order' component
          order_db_url: "mongodb://..."
        # Subscriptions this component handles (required if input_enabled: true)
        subscriptions:
          - topic: "orders/new/>"
            # qos: 1 # Optional: Default 1 (assumed for queue subscriptions)
          - topic: "orders/updates/>"
      - name: log_event_component
        component_module: log_message
        component_config:
          log_level: "INFO"
        subscriptions:
          - topic: "events/>"
```

## 3. Implicit Flow Generation

The `SolaceAiConnector` will detect app definitions that lack an explicit `flows` key but contain `broker` and `components` keys. For each such definition, it will implicitly generate a single `Flow` object.

**Generation Steps:**

1.  **App Initialization:** The `App` class constructor will identify simplified app configurations.
2.  **Flow Creation:** Instead of iterating through a `flows` list in the config, it will create a single `Flow` instance named after the app (e.g., `my_simplified_app_flow`).
3.  **Component Instantiation:** The `Flow` object will instantiate the necessary components based on the `broker` flags and the `components` list:
    *   **BrokerInput:** If `input_enabled: true`.
    *   **SubscriptionRouter:** If `input_enabled: true` and more than one component is defined in `app.components`.
    *   **User Components:** All components listed in `app.components`.
    *   **BrokerOutput:** If `output_enabled: true`.
4.  **Component Linking:** The components will be linked sequentially:
    *   `BrokerInput` -> `SubscriptionRouter` (or directly to the single user component if only one exists).
    *   `SubscriptionRouter` -> User Component(s) input queues.
    *   User Component(s) -> `BrokerOutput`.

## 4. Component Details

### 4.1. Implicit `BrokerInput`

*   **Trigger:** Created if `app.broker.input_enabled` is `true`.
*   **Configuration:** Uses settings from the `app.broker` section (connection details, `queue_name`, `payload_encoding`, `payload_format`, `create_queue_on_start`, `max_redelivery_count`).
*   **Functionality:**
    *   Connects to the specified Solace broker.
    *   Creates/binds to the single queue defined in `app.broker.queue_name`.
    *   Collects *all* topic subscriptions defined under *all* components in `app.components` and applies them to this single queue.
    *   Receives messages from the queue.
    *   Decodes the payload.
    *   Adds acknowledgement/negative-acknowledgement callbacks.
    *   Passes the resulting `Message` object to the next component (either `SubscriptionRouter` or the single user component).
*   **Class:** Uses the existing `src.solace_ai_connector.components.inputs_outputs.broker_input.BrokerInput`.

### 4.2. Implicit `SubscriptionRouter`

*   **Trigger:** Created if `app.broker.input_enabled` is `true` AND `len(app.components) > 1`.
*   **Configuration:** None required directly; it inspects the `app.components` configuration.
*   **Functionality:**
    *   Receives a `Message` object from `BrokerInput`.
    *   Retrieves the message's destination topic (`message.topic`).
    *   Iterates through the user-defined components (`app.components`) *in the order they are listed in the YAML*.
    *   For each component, checks if the message topic matches any of the `subscriptions` defined for that component using standard Solace wildcard matching (`*`, `>`).
    *   Enqueues the `Message` to the input queue of the *first* component whose subscriptions match.
    *   If no component's subscriptions match, the message is logged as unroutable and potentially dropped or sent to an error handler (TBD - initially, log and drop).
*   **Class:** A new class, potentially `src.solace_ai_connector.flow.SubscriptionRouter`, inheriting from `ComponentBase`. Its `invoke` method performs the routing logic.

### 4.3. User-Defined Components

*   **Definition:** Listed under `app.components`. Can be specified using `component_module` (for external components) or `component_class` (for components defined in the same file as a custom `App` subclass). `component_class` takes precedence if both are provided.
*   **Configuration:** Standard component configuration under `component_config`. `subscriptions` list is added here.
*   **Instantiation:** Instantiated by the implicit `Flow`. If `num_instances > 1`, multiple instances are created, sharing the same input queue (leveraging Python's `queue.Queue` multi-consumer capability).
*   **Input:** Receives `Message` objects from the `SubscriptionRouter` (or `BrokerInput` if it's the only component).
*   **Processing:** Executes its `invoke` method.
*   **Output:**
    *   The **return value** of `invoke` is automatically passed to the `BrokerOutput` component (if `output_enabled: true`). The return value should conform to the `BrokerOutput` input schema (`{"payload": ..., "topic": ..., "user_properties": ...}`).
    *   Can optionally call `self.get_app().send_message(payload, topic, user_properties)` multiple times to send additional messages via `BrokerOutput` (if `output_enabled: true`).
*   **Request-Reply:** Can call `self.do_broker_request_response(message, stream, streaming_complete_expression)` if `request_reply_enabled: true`.
*   **Class:** Standard component classes inheriting from `ComponentBase`.

### 4.4. Implicit `BrokerOutput`

*   **Trigger:** Created if `app.broker.output_enabled` is `true`.
*   **Configuration:** Uses settings from the `app.broker` section (connection details, `payload_encoding`, `payload_format`, `propagate_acknowledgements`).
*   **Functionality:**
    *   Connects to the *same* Solace broker instance as `BrokerInput`.
    *   Receives `Message` objects whose `message.previous` attribute contains the output data (`{"payload": ..., "topic": ..., "user_properties": ...}`) returned by a user component.
    *   Also receives messages directly via a mechanism linked to `app.send_message()`.
    *   Encodes the payload.
    *   Sends the message to the specified topic on the broker.
    *   Handles acknowledgement propagation if configured.
*   **Class:** Uses the existing `src.solace_ai_connector.components.inputs_outputs.broker_output.BrokerOutput`.

## 5. Routing Logic (`SubscriptionRouter`)

The `SubscriptionRouter` implements the core logic for directing messages to the correct user component based on topic subscriptions.

```python
# Simplified pseudocode for SubscriptionRouter.invoke
class SubscriptionRouter(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(...)
        self.component_targets = [] # List of tuples: (component_instance, list_of_subscription_regex)
        self._build_targets()

    def _build_targets(self):
        app_components_config = self.get_app().get_config("components", [])
        flow_components = self.get_app().flows[0].component_groups # Assuming single implicit flow

        # Map config order to actual component instances
        component_map = {}
        component_group_idx = 1 # Skip BrokerInput (idx 0)
        if len(app_components_config) > 1:
             component_group_idx = 2 # Skip BrokerInput and Router (idx 0, 1)

        for comp_config in app_components_config:
             comp_name = comp_config.get("name")
             # Find the corresponding component group in the flow
             # This assumes component groups in flow match order in config
             if component_group_idx < len(flow_components):
                 component_map[comp_name] = flow_components[component_group_idx][0] # Get the primary instance for routing
                 component_group_idx += 1
             else:
                 log.error(f"Mismatch finding component instance for {comp_name}")


        for comp_config in app_components_config:
            comp_name = comp_config.get("name")
            component_instance = component_map.get(comp_name)
            if not component_instance:
                 continue # Should not happen if mapping is correct

            subscriptions = comp_config.get("subscriptions", [])
            regex_list = []
            for sub in subscriptions:
                topic = sub.get("topic")
                if topic:
                    # Convert Solace wildcard topic to regex
                    regex = topic.replace("*", "[^/]+").replace(">", ".*?") # Non-greedy match for '>'
                    regex_list.append(f"^{regex}$") # Anchor regex

            if regex_list:
                self.component_targets.append((component_instance, regex_list))


    def invoke(self, message: Message, data: Any):
        msg_topic = message.get_topic()
        if not msg_topic:
            log.warning(f"{self.log_identifier} Message has no topic, cannot route.")
            self.discard_current_message() # Discard if unroutable
            return None

        for target_component, regex_list in self.component_targets:
            for regex_pattern in regex_list:
                if re.match(regex_pattern, msg_topic):
                    # Found target, enqueue to the component's input queue
                    log.debug(f"{self.log_identifier} Routing message with topic '{msg_topic}' to component '{target_component.name}'")
                    target_component.enqueue(Event(EventType.MESSAGE, message))
                    # Do NOT call self.send_message() here, routing is the final step
                    # Prevent default post_invoke processing by discarding
                    self.discard_current_message()
                    return None # Signal that processing is done here

        log.warning(f"{self.log_identifier} No matching subscription found for topic '{msg_topic}'. Discarding message.")
        self.discard_current_message() # Discard if unroutable
        return None
```
**Note:** The `_build_targets` logic needs careful implementation to correctly map the component configuration order to the actual instantiated component objects within the implicit flow.

## 6. Output Mechanisms

Simplified apps support two ways for user components to produce output messages:

1.  **Return Value:** The primary mechanism. If `output_enabled` is true, the return value of the component's `invoke` method is expected to be a dictionary matching the `BrokerOutput` input schema (`{"payload": ..., "topic": ..., "user_properties": ...}`). The framework automatically passes this to the implicit `BrokerOutput` component.
2.  **`app.send_message()`:** User components can access their parent `App` object via `self.get_app()`. The `App` class will provide a `send_message(payload, topic, user_properties)` method. Calling this method (if `output_enabled` is true) will directly enqueue the message details to the implicit `BrokerOutput` component. This allows a component to send multiple output messages for a single input message.

These mechanisms are independent and can be used concurrently.

## 7. Request-Reply Handling

*   **Trigger:** Enabled if `app.broker.request_reply_enabled` is `true`.
*   **Mechanism:** The framework leverages the existing `RequestResponseFlowController`. When a simplified app is created with `request_reply_enabled: true`:
    *   A dedicated `RequestResponseFlowController` instance is created and associated with the `App` instance.
    *   This controller is configured using the *same* broker connection details found in `app.broker`. Specific request-reply settings (expiry, prefixes, keys) are also taken from `app.broker`.
    *   The controller internally creates its own implicit `broker_request_response` component instance.
*   **Usage:** User components within the simplified app can call `self.do_broker_request_response(message, stream, streaming_complete_expression)`. This call is delegated to the app's dedicated `RequestResponseFlowController`.
*   **Simplification:** This uses a single set of broker credentials for input, output, and request-reply within the simplified app context.

## 8. Scalability (`num_instances`)

*   **App Level:** `num_instances` at the `app` level creates multiple independent instances of the entire simplified app definition (including its implicit `BrokerInput`, `BrokerOutput`, etc.). This is the standard app scaling.
*   **Component Level:** `num_instances` specified *within* a component definition (e.g., `app.components[0].num_instances: 2`) scales *only that specific processing component*.
    *   The implicit `Flow` creates multiple instances of that component class.
    *   All instances of that scaled component share the *same* input `queue.Queue`. Python's queue handles multiple consumers.
    *   The `SubscriptionRouter` routes the message to the shared input queue of the target component group. One of the available component instances will pick it up.
    *   This allows parallel processing of messages for a specific step without increasing the number of broker connections.
    *   The implicit `BrokerInput` and `BrokerOutput` remain single instances for the app definition.

## 9. Configuration Sources (Code vs. YAML)

*   **Merging:** Configuration parameters can be defined statically within a component's code (e.g., in `__init__`) and also provided in the YAML configuration file.
*   **Precedence:** If a configuration parameter exists in both the code and the YAML file, the **YAML value takes precedence** and overrides the code-defined value. The `ComponentBase.get_config` method needs to correctly handle this hierarchy (check YAML `component_config`, then `app.config`, then flow/component defaults).
*   **Loading Code Config:** The framework doesn't automatically discover arbitrary code-based config. Components should define their defaults in their `__init__` or rely on the `default` values specified in their `info` dictionary's `config_parameters`. The YAML provides the overrides.

## 10. Error Handling

*   **Component Exceptions:** Exceptions raised within a user component's `invoke` method are handled consistently with the existing framework:
    *   The exception is caught by the `ComponentBase.run` loop.
    *   `handle_negative_acknowledgements` is called on the original input message, triggering a NACK back to the broker via `BrokerInput` (typically `REJECTED` unless overridden).
    *   `handle_error` is called, which formats an error message and puts it onto the main connector `error_queue` (if configured).
*   **Broker Connection Errors:** Connection errors within the implicit `BrokerInput`, `BrokerOutput`, or `RequestResponseFlowController` components are handled by the underlying `SolaceMessaging` service according to the configured reconnection strategy (`app.broker.reconnection_strategy`, etc.).

## 11. Class Changes

*   **`SolaceAiConnector` (`solace_ai_connector.py`):**
    *   Modify `create_apps` (or add logic before it) to detect simplified app configurations (presence of `broker` and `components`, absence of `flows`).
    *   Instantiate `App` objects differently for simplified vs. standard apps, passing necessary info for implicit flow generation.
*   **`App` (`flow/app.py`):**
    *   Modify `__init__` to accept and store the simplified configuration structure.
    *   Modify `create_flows` to implement the implicit flow generation logic when a simplified config is detected. It should create a single `Flow` and populate it with `BrokerInput`, `SubscriptionRouter` (if needed), user components, and `BrokerOutput`. It needs to handle instantiation using `component_class` if provided, otherwise use `component_module`.
    *   Add a `send_message(payload, topic, user_properties)` method that interacts with the implicit `BrokerOutput`'s input queue (needs a reference stored).
    *   Store a reference to the `RequestResponseFlowController` if `request_reply_enabled` is true.
*   **`Flow` (`flow/flow.py`):**
    *   May need minor adjustments to accommodate being created implicitly, potentially passing component definitions differently.
    *   The `create_component_group` method needs to accept either a `component_module` or a `component_class` from the `App` layer.
    *   Needs to correctly link the `SubscriptionRouter` if present.
*   **`ComponentBase` (`components/component_base.py`):**
    *   Add `get_app()` method to return `self.parent_app`.
    *   Ensure `get_config` correctly checks `app.config` in its hierarchy.
    *   The `invoke` call within `process_event` needs to handle the case where `invoke` returns `None` (as `SubscriptionRouter` will) without trying to call `process_post_invoke`. The `discard_current_message` flag handles this.
*   **`BrokerInput` (`components/inputs_outputs/broker_input.py`):**
    *   Needs to accept a list of *all* subscriptions from the app config and apply them to its queue.
*   **`BrokerOutput` (`components/inputs_outputs/broker_output.py`):**
    *   Needs a mechanism (likely modifying its `enqueue` or adding a new method) to accept messages sent via `app.send_message()` in addition to those coming from the previous component's return value.

## 12. New Classes

*   **`SubscriptionRouter` (`flow/subscription_router.py`):**
    *   Inherits from `ComponentBase`.
    *   `__init__`: Takes app config, identifies target components and their subscriptions, pre-compiles topic regex patterns.
    *   `invoke`: Implements the routing logic described in Section 5. Receives message, checks topic against regex list, enqueues to the first matching component's input queue, calls `discard_current_message()`.

## 13. Example (Revisiting YAML)

```yaml
# config.yaml
log:
  stdout_log_level: INFO

apps:
  - name: simple_processor
    broker:
      broker_type: solace
      broker_url: "ws://localhost:8080"
      broker_vpn: "default"
      broker_username: "user"
      broker_password: "password"

      input_enabled: true
      output_enabled: true
      request_reply_enabled: false

      queue_name: "simple_processor/input"
      create_queue_on_start: true
      payload_format: "json"

    config:
      processing_threshold: 100

    components:
      - name: main_processor
        component_module: my_custom_processor # Or component_class: MyCustomProcessor
        num_instances: 1
        component_config:
          db_connection: "..."
        subscriptions:
          - topic: "data/input/>"
```

This configuration would implicitly create a flow:
`BrokerInput` (listening on `simple_processor/input`, subscribed to `data/input/>`) -> `MyCustomProcessor` (instance 1) -> `BrokerOutput`.

## 14. Open Questions / Future Considerations

*   **Unroutable Message Handling:** Define behavior for messages arriving at `BrokerInput` whose topics don't match any component subscriptions (currently log and discard). Send to error queue? Configurable dead message queue?
*   **Code-based Configuration Loading:** How exactly would the framework discover and load configuration defined purely in Python code if YAML isn't the primary driver? This needs more definition if pursued.
*   **Schema Definition:** Explore easier ways for simple components (potentially defined in the same file as the app) to declare input/output schemas.
*   **Dynamic Updates:** How would changes to simplified app configurations be handled in a running connector? (Currently requires restart).
```