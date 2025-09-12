# Implementation Plan: Multi-Session Request/Reply

This document outlines a comprehensive, step-by-step plan for implementing the multi-session request/reply feature. The implementation is divided into three phases: building the core infrastructure, integrating it into the existing framework, and outlining the testing and documentation strategy.

---

## Phase 1: Core Infrastructure (New Files)

This phase focuses on creating the foundational classes for session management in new, isolated files.

### Step 1.1: Create Custom Exceptions

-   **File:** `src/solace_ai_connector/common/exceptions.py` (New File)
-   **Content:**
    -   Define `SessionLimitExceededError(Exception)` for when `max_sessions` is reached.
    -   Define `SessionClosedError(Exception)` for when an operation is attempted on a closed or expired session.
    -   Define `SessionNotFoundError(ValueError)` for when a specified `session_id` does not exist.
-   **Rationale:** Centralizes custom exceptions for the feature, enabling clean, specific error handling in consumer code.

### Step 1.2: Define Session Configuration

-   **File:** `src/solace_ai_connector/common/session_config.py` (New File)
-   **Content:**
    -   Import `dataclass`, `Dict`, `Any` from `typing`.
    -   Create the `SessionConfig` dataclass with all fields specified in the detailed design, including `broker_config`, timeouts, and topic/queue prefixes.
    -   Implement a `to_controller_config()` method to transform the `SessionConfig` object into the dictionary format expected by `RequestResponseFlowController`.
    -   Implement a `validate()` method to ensure required fields (like `broker_config`) are present.
-   **Rationale:** Encapsulates all configuration for a single session into a strongly-typed, immutable object, improving code clarity and safety.

### Step 1.3: Implement the Session Registry

-   **File:** `src/solace_ai_connector/flow/session_registry.py` (New File)
-   **Content:**
    -   Import `threading`, `Dict`, `List`, and `RequestResponseSession` (as a forward type hint if needed).
    -   Create the `SessionRegistry` class.
    -   **`__init__`**: Initialize a `_sessions` dictionary, a `threading.RLock`, and a `_session_counter`.
    -   **`generate_session_id()`**: Implement a thread-safe method to generate unique session IDs.
    -   **`register_session(session)`**: Add a session to the `_sessions` dictionary under lock.
    -   **`unregister_session(session_id)`**: Remove and return a session from the dictionary under lock.
    -   **`get_session(session_id)`**: Retrieve a session by ID, raising `SessionNotFoundError` if it's not found.
    -   **`list_sessions()`**: Return a list of all session objects currently in the registry.
    -   **`clear()`**: Remove all sessions and return them, for use during shutdown.
-   **Rationale:** Provides a thread-safe container for managing the lifecycle of all active sessions, abstracting away the complexity of concurrent access.

### Step 1.4: Implement the Request/Response Session Wrapper

-   **File:** `src/solace_ai_connector/flow/request_response_session.py` (New File)
-   **Content:**
    -   Import `time`, `threading`, `weakref`, and necessary classes (`SessionConfig`, `RequestResponseFlowController`, `SessionClosedError`).
    -   Create the `RequestResponseSession` class.
    -   **`__init__(session_id, config, connector)`**:
        -   Store session metadata (`session_id`, `config`, timestamps).
        -   Initialize an `active_requests` set and a `threading.RLock` for tracking.
        -   Instantiate its own `RequestResponseFlowController` using the session-specific configuration.
    -   **`do_request_response(...)`**:
        -   Update `last_used_at` timestamp.
        -   Track the request by adding a unique ID to `active_requests`.
        -   Delegate the call to the internal `RequestResponseFlowController`.
        -   Use a `finally` block to ensure the request ID is removed from `active_requests` upon completion or failure.
    -   **`get_status()`**: Return a dictionary with detailed session status (ID, age, last use, active request count).
    -   **`cleanup()`**:
        -   Set an internal shutdown flag.
        -   Call a `cleanup()` method on the internal `RequestResponseFlowController` to release its resources (this method will be added in Phase 2). This will cause any waiting callers to fail immediately with a `SessionClosedError`.
-   **Rationale:** Encapsulates the resources and state of a single, isolated request/reply session.

### Step 1.5: Implement the Multi-Session Manager

-   **File:** `src/solace_ai_connector/flow/multi_session_request_response_manager.py` (New File)
-   **Content:**
    -   Import necessary classes (`SessionRegistry`, `RequestResponseSession`, `SessionConfig`, etc.) and modules (`threading`, `weakref`, `time`).
    -   Create the `MultiSessionRequestResponseManager` class.
    -   **`__init__(component, default_session_config, max_sessions)`**:
        -   Store a `weakref` to the parent component, default configuration, and limits.
        -   Instantiate the `SessionRegistry`.
    -   **`create_session(session_config)`**:
        -   Check against `max_sessions` and raise `SessionLimitExceededError` if the limit is reached.
        -   Merge the provided `session_config` with defaults.
        -   Create and register a new `RequestResponseSession`.
        -   Return the new `session_id`.
    -   **`destroy_session(session_id)`**: Unregister the session and call its `cleanup()` method.
    -   **`get_session(session_id)`**: Delegate to the `SessionRegistry`.
    -   **`list_sessions()`**: Iterate through sessions in the registry, call `get_status()` on each, and return a list of status dictionaries.
    -   **`shutdown()`**: Gracefully destroy all active sessions.
-   **Rationale:** Serves as the primary API for the feature, managing the entire lifecycle of all sessions associated with a component.

---

## Phase 2: Integration (Modifying Existing Files)

This phase integrates the new session management infrastructure into the core framework by modifying existing files.

### Step 2.1: Modify `RequestResponseFlowController`

-   **File:** `src/solace_ai_connector/flow/request_response_flow_controller.py`
-   **Changes:**
    1.  Add a `cleanup()` method. This method will call `self.flow.cleanup()`, which will propagate the cleanup down to the underlying `BrokerRequestResponse` component and its broker connection.
    2.  Add a shutdown flag (e.g., `self._is_shutdown = threading.Event()`). The `cleanup` method will set this event.
    3.  In `do_broker_request_response`, check this flag at the beginning. If set, immediately raise `SessionClosedError` to ensure callers fail fast.
-   **Rationale:** Provides a clean entry point for tearing down the resources (internal flow, broker connection) associated with a single session.

### Step 2.2: Modify `ComponentBase`

-   **File:** `src/solace_ai_connector/components/component_base.py`
-   **Changes:**
    1.  **`__init__`**: Add `self._multi_session_manager = None` and call a new private method, `self._setup_multi_session_request_response()`.
    2.  **New Method `_setup_multi_session_request_response()`**: This method will read the `multi_session_request_response` block from the component's YAML configuration. If `enabled: true`, it will instantiate the `MultiSessionRequestResponseManager` and assign it to `self._multi_session_manager`.
    3.  **New Public API Methods**:
        -   `create_request_response_session(session_config)`: Delegates to `self._multi_session_manager.create_session()`.
        -   `destroy_request_response_session(session_id)`: Delegates to `self._multi_session_manager.destroy_session()`.
        -   `list_request_response_sessions()`: Delegates to `self._multi_session_manager.list_sessions()`.
    4.  **Modify `do_broker_request_response(...)`**:
        -   Add `session_id=None` to the method signature.
        -   **If `session_id` is provided**: Check for the existence of `_multi_session_manager`, get the session, and delegate the call to `session.do_request_response(...)`.
        -   **If `session_id` is `None` (Backward Compatibility)**: Keep the existing logic that checks for the app-level controller first, then falls back to the component-level controller.
    5.  **Modify `cleanup()`**: If `self._multi_session_manager` exists, call `self._multi_session_manager.shutdown()` to ensure all dynamic sessions are cleaned up when the component is destroyed.
-   **Rationale:** Exposes the new session management API on every component and integrates it seamlessly with the existing request/reply mechanism, ensuring full backward compatibility.

---

## Phase 3: Testing and Documentation

This phase outlines the necessary steps for validation and user-facing documentation.

### Step 3.1: Unit Tests

-   **`SessionRegistry`**: Test for thread safety by having multiple threads concurrently create, access, and destroy sessions.
-   **`RequestResponseSession`**: Verify correct `RequestResponseFlowController` initialization and ensure its `cleanup()` method is called.
-   **`MultiSessionRequestResponseManager`**:
    -   Verify that `max_sessions` is correctly enforced.
    -   Test the `shutdown()` method to confirm all sessions are destroyed.
-   **`ComponentBase`**: Test the new API methods to ensure they delegate correctly to the manager.

### Step 3.2: Integration Tests

-   Create a test with a component that:
    1.  Creates two separate sessions with different broker configurations.
    2.  Sends a request on session 1 and verifies the response.
    3.  Sends a request on session 2 and verifies the response.
    4.  Lists sessions and verifies the status contains two active sessions.
    5.  Destroys session 1.
    6.  Verifies that attempting to use session 1 raises `SessionNotFoundError` or `SessionClosedError`.
    7.  Verifies that session 2 remains fully functional.
-   Create a test for backward compatibility by calling `do_broker_request_response` without a `session_id` on a component with the legacy configuration.

### Step 3.3: Documentation

-   Update the `llm.txt` developer guides for `component_base.py` and the `flow` directory to document the new feature and its API.
-   Add a new section to the main project developer guide explaining how to configure and use the multi-session request/reply feature, with both YAML and Python examples.
-   Update the `info` dictionary for `BrokerRequestResponse` to clearly mark it as an internal component not intended for direct use in user-defined flows.
