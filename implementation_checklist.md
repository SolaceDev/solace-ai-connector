# Implementation Checklist: Multi-Session Request/Reply

This checklist breaks down the implementation plan into actionable, trackable steps.

## Phase 1: Core Infrastructure (New Files)

1.  [x] **Create Custom Exceptions (`src/solace_ai_connector/common/exceptions.py`)**
    -   [x] Define `SessionLimitExceededError(Exception)`.
    -   [x] Define `SessionClosedError(Exception)`.
    -   [x] Define `SessionNotFoundError(ValueError)`.

2.  [x] **Define Session Configuration (`src/solace_ai_connector/common/session_config.py`)**
    -   [x] Create `SessionConfig` dataclass.
    -   [x] Implement `to_controller_config()` method.
    -   [x] Implement `validate()` method.

3.  [x] **Implement the Session Registry (`src/solace_ai_connector/flow/session_registry.py`)**
    -   [x] Create `SessionRegistry` class with `_sessions` dict, `RLock`, and `_session_counter`.
    -   [x] Implement `generate_session_id()`.
    -   [x] Implement `register_session(session)`.
    -   [x] Implement `unregister_session(session_id)`.
    -   [x] Implement `get_session(session_id)`.
    -   [x] Implement `list_sessions()`.
    -   [x] Implement `clear()`.

4.  [x] **Implement the Request/Response Session Wrapper (`src/solace_ai_connector/flow/request_response_session.py`)**
    -   [x] Create `RequestResponseSession` class.
    -   [x] In `__init__`, store metadata and instantiate `RequestResponseFlowController`.
    -   [x] Implement `do_request_response(...)` with request tracking.
    -   [x] Implement `is_expired()`.
    -   [x] Implement `get_status()`.
    -   [x] Implement `cleanup()` to release resources and fail waiting callers.

5.  [x] **Implement the Multi-Session Manager (`src/solace_ai_connector/flow/multi_session_request_response_manager.py`)**
    -   [x] Create `MultiSessionRequestResponseManager` class.
    -   [x] In `__init__`, store component `weakref`, config, limits, and instantiate `SessionRegistry`.
    -   [x] Implement and start the background `_cleanup_thread`.
    -   [x] Implement `create_session(session_config)` with `max_sessions` check.
    -   [x] Implement `destroy_session(session_id)`.
    -   [x] Implement `get_session(session_id)`.
    -   [x] Implement `list_sessions()` to return detailed status dictionaries.
    -   [x] Implement `shutdown()` to stop the thread and clean up all sessions.

## Phase 2: Integration (Modifying Existing Files)

6.  [ ] **Modify `RequestResponseFlowController` (`src/solace_ai_connector/flow/request_response_flow_controller.py`)**
    -   [ ] Add a `cleanup()` method that calls `self.flow.cleanup()`.
    -   [ ] Add a shutdown flag (`self._is_shutdown`).
    -   [ ] Check the shutdown flag in `do_broker_request_response` and raise `SessionClosedError` if set.

7.  [ ] **Modify `ComponentBase` (`src/solace_ai_connector/components/component_base.py`)**
    -   [ ] In `__init__`, add `self._multi_session_manager = None`.
    -   [ ] Create and call `_setup_multi_session_request_response()` from `__init__`.
    -   [ ] Add public API method `create_request_response_session(...)`.
    -   [ ] Add public API method `destroy_request_response_session(...)`.
    -   [ ] Add public API method `list_request_response_sessions()`.
    -   [ ] Modify `do_broker_request_response(...)` to accept `session_id` and handle both new and legacy paths.
    -   [ ] Modify `cleanup()` to call `self._multi_session_manager.shutdown()` if it exists.

## Phase 3: Testing and Documentation

8.  [ ] **Unit Tests**
    -   [ ] Test `SessionRegistry` for thread safety.
    -   [ ] Test `RequestResponseSession` for correct initialization and cleanup.
    -   [ ] Test `MultiSessionRequestResponseManager` for `max_sessions` enforcement, session expiration, and shutdown.
    -   [ ] Test `ComponentBase` API methods for correct delegation.

9.  [ ] **Integration Tests**
    -   [ ] Create a multi-session test (create, use, list, destroy).
    -   [ ] Create a session expiration test.
    -   [ ] Create a backward compatibility test using legacy config.

10. [ ] **Documentation**
    -   [ ] Update `llm.txt` developer guides for modified files.
    -   [ ] Add a new section to the main project developer guide for the feature.
    -   [ ] Update `BrokerRequestResponse` `info` dictionary to mark it as internal.
