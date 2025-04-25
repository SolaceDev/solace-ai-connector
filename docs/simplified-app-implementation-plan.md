# Simplified App Mode - Implementation Plan

This document outlines the step-by-step plan to implement the "Simplified App Mode" feature.

## Phase 1: Core App and Flow Modifications

1.  **Add `deep_merge` Utility:**
    *   Add the `deep_merge` function to `src/solace_ai_connector/common/utils.py` to handle merging code-defined and YAML configurations.

2.  **Modify `App.__init__` (`flow/app.py`):**
    *   Import `deep_merge`.
    *   Check for the presence of a class attribute `app_config`.
    *   If `app_config` exists, perform a `deep_merge` with the `app_info` passed from YAML, ensuring YAML values take precedence. Store the result in `self.app_info`.
    *   Extract the `config` block from the *merged* `self.app_info` into `self.app_config`.
    *   Ensure `self.name` is derived from the merged `self.app_info`.

3.  **Modify `App.create_flows` (`flow/app.py`):**
    *   Add logic to detect if `self.app_info` represents a simplified app (contains `broker` and `components`, lacks `flows`).
    *   If simplified, call a new helper method `_create_simplified_flow_config()` to generate the implicit flow configuration dictionary.
    *   Call `self.create_flow()` with the generated configuration.
    *   If not simplified, proceed with the existing logic to iterate through the `flows` list.

4.  **Implement `App._create_simplified_flow_config` (`flow/app.py`):**
    *   Create this private helper method.
    *   It should construct a dictionary representing a single flow configuration.
    *   Based on `self.app_info['broker']` flags (`input_enabled`, `output_enabled`) and the number of components in `self.app_info['components']`, add component configurations for:
        *   `broker_input` (if `input_enabled`)
        *   `subscription_router` (if `input_enabled` and >1 user component)
        *   User components (copy from `self.app_info['components']`)
        *   `broker_output` (if `output_enabled`)
    *   Pass relevant parts of the `broker` config to the implicit `broker_input` and `broker_output` component configs.
    *   Collect all `subscriptions` from all user components and add them to the `broker_input` config.
    *   Pass a reference to the user components list (`self.app_info['components']`) to the `subscription_router` config for routing rule creation.
    *   Return the generated flow configuration dictionary.

5.  **Modify `Flow.create_component_group` (`flow/flow.py`):**
    *   Check if `component_class` is present in the `component` config dictionary.
    *   If `component_class` exists and is a valid class, use it directly for instantiation instead of importing via `component_module`.
    *   If `component_class` is not present, use the existing `component_module` import logic.

6.  **Modify `ComponentBase` (`components/component_base.py`):**
    *   Add the `get_app()` method: `return self.parent_app`.
    *   Modify `get_config`: Change the lookup order to:
        1. `self.component_config.get(key)`
        2. `self.parent_app.get_config(key)` (if `self.parent_app` exists)
        3. `self.config.get(key, default)` (This `self.config` holds the component's entry from the flow/app config, potentially including things like `num_instances` etc., less likely to contain component-specific operational params).

## Phase 2: Implement Subscription Router

1.  **Create `SubscriptionRouter` Component (`flow/subscription_router.py`):**
    *   Create the new file.
    *   Define the `SubscriptionRouter` class inheriting from `ComponentBase`.
    *   Define the `info` dictionary for the component.
    *   Implement `__init__`:
        *   Get the user components configuration list (passed via `component_config`).
        *   Get references to the actual instantiated user component objects from the flow (`self.get_app().flows[0].component_groups`). This requires careful mapping based on order/name.
        *   Build `self.component_targets` list: `[(component_instance, list_of_compiled_regex)]`. Convert Solace wildcards in subscription topics to regex.
    *   Implement `invoke`:
        *   Get the incoming message topic.
        *   Iterate through `self.component_targets`.
        *   Use `re.match` to find the first component whose regex list matches the topic.
        *   Enqueue the original `Event` to the matched component's input queue (`target_component.enqueue(event)`).
        *   Call `self.discard_current_message()` to prevent further processing in `ComponentBase` and signal ACK.
        *   Return `None`.
        *   If no match, log a warning and call `self.discard_current_message()`.

## Phase 3: Adapt Broker Components and Add App Methods

1.  **Modify `BrokerInput` (`components/inputs_outputs/broker_input.py`):**
    *   Ensure `__init__` correctly reads the `broker_subscriptions` list passed via its `component_config` (originating from `App._create_simplified_flow_config`).
    *   Ensure the underlying `SolaceMessaging.bind_to_queue` (or equivalent) applies all these subscriptions to the single queue it manages.
    *  Make sure that all changes are backward compatible with the existing `BrokerInput` functionality.

2.  **Implement `App.send_message` (`flow/app.py`):**
    *   Add the method `send_message(self, payload: Any, topic: str, user_properties: Optional[Dict] = None)`.
    *   Check if `output_enabled` is true in `self.app_info['broker']`. Log warning and return if false.
    *   Find the implicit `BrokerOutput` component instance within the app's flow (likely the last component in the first/only flow).
    *   If found:
        *   Create the output data dictionary: `{"payload": payload, "topic": topic, "user_properties": user_properties or {}}`.
        *   Import `Message`, `Event`, `EventType` locally within the method.
        *   Create a `Message` object, put `output_data` into `message.previous`.
        *   Create an `Event(EventType.MESSAGE, msg)`.
        *   Call `broker_output_component.enqueue(event)`.
    *   If `BrokerOutput` not found, log an error.

3.  **Modify `BrokerOutput` (`components/inputs_outputs/broker_output.py`):**
    *   Make sure that all changes are backward compatible with the existing `BrokerOutput` functionality.
    *   Review the `send_message` method (which handles messages coming from the *previous* component via `message.previous`).
    *   Ensure the logic correctly handles the `Message` object created by `App.send_message`, extracting data from `message.previous`. No explicit changes might be needed if `send_message` already relies solely on `message.previous`. Double-check the data extraction path. *Self-correction:* The base `run` loop calls `invoke`, then `process_post_invoke` which calls `send_message`. Messages from `App.send_message` arrive via `enqueue` directly. We need `BrokerOutput.process_event` to handle these.
    *   Modify `BrokerOutput.process_event`:
        *   If `event.event_type == EventType.MESSAGE`:
            *   Extract the `message` from `event.data`.
            *   Call `self.send_message(message)` (the existing method that processes `message.previous`).
            *   Acknowledge the message (`message.call_acknowledgements()`) as it didn't go through an `invoke`.

## Phase 4: Request-Reply and Validation

1.  **Integrate `RequestResponseFlowController` (`flow/app.py`):**
    *   In `App.__init__`, after merging config, check if `self.app_info['broker'].get('request_reply_enabled', False)` is true.
    *   If true:
        *   Instantiate `RequestResponseFlowController`, passing the relevant `broker` config section as `broker_config` and other necessary parameters (`request_expiry_ms`, etc.) extracted from `self.app_info['broker']`. Pass `self.connector`.
        *   Store the controller instance, e.g., `self.request_response_controller`.
    *   Modify `ComponentBase.do_broker_request_response`: Ensure it accesses the controller via `self.get_app().request_response_controller`.

2.  **Update `SolaceAiConnector.validate_config` (`solace_ai_connector.py`):**
    *   Modify the validation logic to accept the simplified app structure:
        *   If an `app` entry exists:
            *   It must have `name`.
            *   It must have either `flows` OR (`broker` AND `components`).
            *   If `broker` and `components` are present (simplified mode):
                *   Validate the structure of `broker` (presence of required connection details, flags).
                *   Validate `components` is a list.
                *   Validate each entry in `components` has `name` and either `component_module` or `component_class`. Validate `subscriptions` if `input_enabled`.
            *   If `flows` is present (standard mode):
                *   Proceed with existing flow validation (`_validate_flows`).

## Phase 5: Documentation and Testing

1.  **Update Documentation:**
    *   Review and update `simplified-app-plan.md` and `simplified-app-design.md` based on implementation details.
    *   Create user documentation (`docs/simplified-apps.md` or similar) explaining the feature, configuration options (YAML and code-based), and usage. Include examples.

2.  **Write Unit Tests:**
    *   Test `App.__init__` config merging logic.
    *   Test `App._create_simplified_flow_config` for various flag combinations.
    *   Test `Flow.create_component_group` handling `component_class`.
    *   Test `SubscriptionRouter` routing logic with various topics and subscriptions.
    *   Test `ComponentBase.get_config` hierarchy.

3.  **Write Integration Tests:**
    *   Create a test configuration YAML that loads `examples/simple_echo_app.py` using `app_module`.
    *   Send messages to the input topic and verify echoed messages on the output topic.
    *   Create a test YAML that overrides parts of the `simple_echo_app.py` configuration (e.g., `echo_topic`) and verify the override works.
    *   Create a test for a simplified app with multiple components and verify `SubscriptionRouter` works.
    *   Create a test using `app.send_message()` and verify output.
    *   Create a test using `request_reply_enabled` and `self.do_broker_request_response()` in a simplified app component.
    *   Test `num_instances` at the component level within a simplified app.

4.  **Refactor and Review:**
    *   Clean up code, add comments, and ensure consistency.
    *   Perform code reviews.
