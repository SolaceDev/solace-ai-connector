# Simplified App Mode - Implementation Checklist

This checklist corresponds to the steps outlined in the `docs/simplified-app-implementation-plan.md`.

Coding rules:

- Follow Google Python Style Guide.
- Do not put in useless comments or comments that relate only to a change just made (e.g. `# added this line` or `# removed function bob()`).
- Do not include comments referencing the implementation plan (e.g. `# step 1.2.3`).

## 1. Phase 1: Core App and Flow Modifications

- [X] **1.1 Add `deep_merge` Utility:**
    - [X] 1.1.1 Add `deep_merge` function to `src/solace_ai_connector/common/utils.py`.
- [X] **1.2 Modify `App.__init__` (`flow/app.py`):**
    - [X] 1.2.1 Import `deep_merge`.
    - [X] 1.2.2 Check for `app_config` class attribute.
    - [X] 1.2.3 Perform `deep_merge` if `app_config` exists (YAML overrides code).
    - [X] 1.2.4 Store merged result in `self.app_info`.
    - [X] 1.2.5 Extract `config` block from merged `self.app_info` into `self.app_config`.
    - [X] 1.2.6 Derive `self.name` from merged `self.app_info`.
- [X] **1.3 Modify `App.create_flows` (`flow/app.py`):**
    - [X] 1.3.1 Add logic to detect simplified app configuration.
    - [X] 1.3.2 Call `_create_simplified_flow_config()` if simplified.
    - [X] 1.3.3 Call `self.create_flow()` with the generated config.
    - [X] 1.3.4 Keep existing logic for standard flows.
- [X] **1.4 Implement `App._create_simplified_flow_config` (`flow/app.py`):**
    - [X] 1.4.1 Create the private helper method.
    *   [X] 1.4.2 Construct flow dictionary.
    *   [X] 1.4.3 Add `broker_input` config if `input_enabled`.
    *   [X] 1.4.4 Add `subscription_router` config if `input_enabled` and >1 user component.
    *   [X] 1.4.5 Add user components config.
    *   [X] 1.4.6 Add `broker_output` config if `output_enabled`.
    *   [X] 1.4.7 Pass relevant `broker` config to implicit broker components.
    *   [X] 1.4.8 Collect and add all `subscriptions` to `broker_input` config.
    *   [X] 1.4.9 Pass user components list reference to `subscription_router` config.
    *   [X] 1.4.10 Return generated flow config dictionary.
- [X] **1.5 Modify `Flow.create_component_group` (`flow/flow.py`):**
    *   [X] 1.5.1 Check for `component_class` in component config.
    *   [X] 1.5.2 Use `component_class` for instantiation if present.
    *   [X] 1.5.3 Use `component_module` if `component_class` is not present.
- [X] **1.6 Modify `ComponentBase` (`components/component_base.py`):**
    *   [X] 1.6.1 Add `get_app()` method.
    *   [X] 1.6.2 Modify `get_config` lookup order: `component_config` -> `app.config` -> `self.config`.

## 2. Phase 2: Implement Subscription Router

- [X] **2.1 Create `SubscriptionRouter` Component (`flow/subscription_router.py`):**
    *   [X] 2.1.1 Create the new file `src/solace_ai_connector/flow/subscription_router.py`.
    *   [X] 2.1.2 Define `SubscriptionRouter` class inheriting `ComponentBase`.
    *   [X] 2.1.3 Define `info` dictionary.
    *   [X] 2.1.4 Implement `__init__`:
        *   [X] 2.1.4.1 Get user components config.
        *   [X] 2.1.4.2 Get references to instantiated user components.
        *   [X] 2.1.4.3 Build `self.component_targets` list with compiled regex.
    *   [X] 2.1.5 Implement `invoke`:
        *   [X] 2.1.5.1 Get message topic.
        *   [X] 2.1.5.2 Iterate `self.component_targets`.
        *   [X] 2.1.5.3 Use `re.match` to find the first matching component.
        *   [X] 2.1.5.4 Enqueue event to the target component's queue.
        *   [X] 2.1.5.5 Call `self.discard_current_message()`.
        *   [X] 2.1.5.6 Return `None`.
        *   [X] 2.1.5.7 Handle no match case (log, discard).

## 3. Phase 3: Adapt Broker Components and Add App Methods

- [X] **3.1 Modify `BrokerInput` (`components/inputs_outputs/broker_input.py`):**
    *   [X] 3.1.1 Ensure `__init__` reads `broker_subscriptions` from `component_config`.
    *   [X] 3.1.2 Ensure `bind_to_queue` applies all subscriptions.
    *   [X] 3.1.3 Verify backward compatibility.
- [X] **3.2 Implement `App.send_message` (`flow/app.py`):**
    *   [X] 3.2.1 Add `send_message` method.
    *   [X] 3.2.2 Check `output_enabled` flag.
    *   [X] 3.2.3 Find implicit `BrokerOutput` component instance.
    *   [X] 3.2.4 Create output data dictionary.
    *   [X] 3.2.5 Import `Message`, `Event`, `EventType` locally.
    *   [X] 3.2.6 Create `Message` object with data in `message.previous`.
    *   [X] 3.2.7 Create `Event`.
    *   [X] 3.2.8 Call `broker_output_component.enqueue(event)`.
    *   [X] 3.2.9 Handle `BrokerOutput` not found error.
- [X] **3.3 Modify `BrokerOutput` (`components/inputs_outputs/broker_output.py`):**
    *   [X] 3.3.1 Verify backward compatibility.
    *   [X] 3.3.2 Modify `process_event`: (Self-correction: No change needed due to `ComponentBase` handling)
        *   [X] 3.3.2.1 If `event.event_type == EventType.MESSAGE`:
            *   [X] 3.3.2.1.1 Extract `message`.
            *   [X] 3.3.2.1.2 Call `self.send_message(message)`.
            *   [X] 3.3.2.1.3 Call `message.call_acknowledgements()`.

## 4. Phase 4: Request-Reply and Validation

- [X] **4.1 Integrate `RequestResponseFlowController` (`flow/app.py`):**
    *   [X] 4.1.1 In `App.__init__`, check `request_reply_enabled` flag.
    *   [X] 4.1.2 If true, instantiate `RequestResponseFlowController` with relevant `broker` config.
    *   [X] 4.1.3 Store controller instance (e.g., `self.request_response_controller`).
    *   [X] 4.1.4 Modify `ComponentBase.do_broker_request_response` to use `self.get_app().request_response_controller`.
- [X] **4.2 Update `SolaceAiConnector.validate_config` (`solace_ai_connector.py`):**
    *   [X] 4.2.1 Modify validation logic for `app` entries.
    *   [X] 4.2.2 Check for `name`.
    *   [X] 4.2.3 Check for either `flows` OR (`broker` AND `components`).
    *   [X] 4.2.4 If simplified mode:
        *   [X] 4.2.4.1 Validate `broker` structure.
        *   [X] 4.2.4.2 Validate `components` is a list.
        *   [X] 4.2.4.3 Validate each component entry (`name`, `component_module`/`component_class`, `subscriptions`).
    *   [X] 4.2.5 If standard mode:
        *   [X] 4.2.5.1 Use existing `_validate_flows`.

## 5. Phase 5: Documentation and Testing

- [ ] **5.1 Update Documentation:**
    *   [ ] 5.1.1 Review and update `simplified-app-plan.md`.
    *   [ ] 5.1.2 Review and update `simplified-app-design.md`.
    *   [ ] 5.1.3 Create user documentation (`docs/simplified-apps.md`).
- [ ] **5.2 Write Unit Tests:**
    *   [ ] 5.2.1 Test `App.__init__` merging.
    *   [ ] 5.2.2 Test `App._create_simplified_flow_config`.
    *   [ ] 5.2.3 Test `Flow.create_component_group` with `component_class`.
    *   [ ] 5.2.4 Test `SubscriptionRouter` routing.
    *   [ ] 5.2.5 Test `ComponentBase.get_config` hierarchy.
- [ ] **5.3 Write Integration Tests:**
    *   [ ] 5.3.1 Test loading `simple_echo_app.py` via `app_module`.
    *   [ ] 5.3.2 Test YAML override of code config.
    *   [ ] 5.3.3 Test multi-component simplified app (`SubscriptionRouter`).
    *   [ ] 5.3.4 Test `app.send_message()`.
    *   [ ] 5.3.5 Test `request_reply_enabled` and `do_broker_request_response`.
    *   [ ] 5.3.6 Test component-level `num_instances`.
- [ ] **5.4 Refactor and Review:**
    *   [ ] 5.4.1 Clean up code.
    *   [ ] 5.4.2 Add comments.
    *   [ ] 5.4.3 Ensure consistency.
    *   [ ] 5.4.4 Perform code reviews.
