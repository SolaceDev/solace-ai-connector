# Broker Request-Response Guide

This guide provides comprehensive documentation for the broker request-response capabilities in the Solace AI Connector. It covers both the default single-session mode and the advanced multi-session mode, enabling synchronous (blocking) and asynchronous (non-blocking) communication patterns.

## Table of Contents
1.  [Introduction](#introduction)
2.  [Modes of Operation](#modes-of-operation)
    -   [Single-Session Mode (Default)](#single-session-mode-default)
    -   [Multi-Session Mode (Advanced)](#multi-session-mode-advanced)
3.  [Choosing Between Modes](#choosing-between-modes)
4.  [API Reference](#api-reference)
    -   [`do_broker_request_response()`](#do_broker_request_response)
    -   [`create_request_response_session()`](#create_request_response_session)
    -   [`destroy_request_response_session()`](#destroy_request_response_session)
    -   [`list_request_response_sessions()`](#list_request_response_sessions)
5.  [Use Cases and Examples](#use-cases-and-examples)
    -   [Synchronous Request-Response](#synchronous-request-response)
    -   [Streaming Response](#streaming-response)
    -   [Asynchronous Request (Fire-and-Forget)](#asynchronous-request-fire-and-forget)
    -   [Dynamic Multi-Session Usage](#dynamic-multi-session-usage)
6.  [Error Handling and Troubleshooting](#error-handling-and-troubleshooting)

---

## 1. Introduction

The request-response feature allows a component to send a request message to a topic and receive a correlated response. The framework handles the complexity of correlation, reply topics, and timeouts.

This capability supports two main interaction patterns:
-   **Synchronous (Blocking):** The component sends a request and waits for a reply before continuing. This is the default behavior.
-   **Asynchronous (Non-Blocking):** The component sends a request and immediately continues processing without waiting for a reply. This is ideal for "fire-and-forget" scenarios.

## 2. Modes of Operation

Request-response can be configured in two primary modes.

### Single-Session Mode (Default)

This is the simplest and recommended approach for most use cases. A single, shared request-response session is created for the entire application, using the app's main broker configuration.

-   **Overview**: One shared session per app.
-   **Configuration**: Enabled at the app level in your `config.yaml`.
-   **Use Cases**: Standard request-response needs where all components in an app can share the same broker connection for requests.

#### Configuration

Enable this mode by setting `request_reply_enabled: true` in the `broker:` section of a simplified app.

```yaml
# config.yaml
apps:
  - name: my_requesting_app
    broker:
      broker_url: "${SOLACE_BROKER_URL}"
      broker_username: "${SOLACE_USERNAME}"
      broker_password: "${SOLACE_PASSWORD}"
      broker_vpn: "${SOLACE_VPN}"
      input_enabled: true
      # Enable the shared request-response session for this app
      request_reply_enabled: true
    components:
      - name: my_component
        component_module: my_requesting_component
        # ...
```

### Multi-Session Mode (Advanced)

This mode allows a single component to create and manage multiple, independent request-response sessions. Each session can have its own unique broker configuration (e.g., connect to different brokers or use different client settings).

-   **Overview**: A component manages multiple, independent sessions.
-   **Configuration**: Enabled at the component level in your `config.yaml`.
-   **Use Cases**: Multi-tenant scenarios, connecting to different broker environments from one component, or requiring isolated sessions for reliability.

#### Configuration

Enable this mode by adding a `multi_session_request_response` block to a component's configuration.

```yaml
# config.yaml
apps:
  - name: my_multi_session_app
    # ...
    flows:
      - name: my_flow
        components:
          - component_name: my_advanced_component
            component_module: my_advanced_component
            component_config:
              multi_session_request_response:
                enabled: true
                max_sessions: 10 # Optional: default is 50
                default_broker_config:
                  # Default connection details for new sessions
                  broker_url: "${SOLACE_BROKER_URL}"
                  broker_username: "${SOLACE_USERNAME}"
                  broker_password: "${SOLACE_PASSWORD}"
                  broker_vpn: "${SOLACE_VPN}"
```

---

## 3. Choosing Between Modes

| Feature | Single-Session Mode | Multi-Session Mode |
| :--- | :--- | :--- |
| **Configuration** | App-level (`request_reply_enabled: true`) | Component-level (`multi_session_request_response`) |
| **Session Management** | Automatic (managed by the framework) | Manual (via `create/destroy` API calls) |
| **Use Case** | Simple, default request-response needs. | Advanced, multi-tenant, multi-broker scenarios. |
| **Resource Overhead**| Low (one shared session per app) | Higher (one session per `create` call) |
| **Primary API** | `self.do_broker_request_response(message)` | `self.do_broker_request_response(message, session_id=...)` |

---

## 4. API Reference

These methods are available on your component instance (`self`).

### `do_broker_request_response()`

Performs the request-response operation. This is the primary method for both single-session and multi-session modes.

```python
self.do_broker_request_response(
    message,
    session_id: Optional[str] = None,
    stream: bool = False,
    streaming_complete_expression: Optional[str] = None,
    wait_for_response: bool = True
)
```

**Parameters:**

-   `message` (`Message`): The request message object containing the payload, topic, and optional user properties.
-   `session_id` (`str`, optional): The ID of a dynamic session to use. **If provided, multi-session mode is used.** If `None`, the default single-session mode is used.
-   `stream` (`bool`, optional): Set to `True` to indicate that the response will arrive in multiple parts (chunks). Defaults to `False`.
-   `streaming_complete_expression` (`str`, optional): **Required if `stream=True`**. An expression that evaluates to `True` on the final chunk of a streaming response.
-   `wait_for_response` (`bool`, optional):
    -   `True` (Default): The call blocks until a response is received or a timeout occurs.
    -   `False`: The call sends the request and returns `None` immediately ("fire-and-forget").

**Return Value:**

-   If `wait_for_response=False`: Returns `None`.
-   If `wait_for_response=True` and `stream=False`: Returns the single response `Message` object, or raises a `TimeoutError`.
-   If `wait_for_response=True` and `stream=True`: Returns a Python generator that yields tuples of `(chunk_message, is_last)`.

### `create_request_response_session()`

Creates a new, dynamic request-response session. **Only available in multi-session mode.**

```python
self.create_request_response_session(
    session_config_overrides: Optional[Dict[str, Any]] = None
) -> str
```
-   **`session_config_overrides`**: A dictionary of broker properties to override the defaults for this specific session.
-   **Returns**: A unique `session_id` (string) for the new session.

### `destroy_request_response_session()`

Destroys a dynamic session and cleans up its resources. **Only available in multi-session mode.** It is critical to call this to prevent resource leaks.

```python
self.destroy_request_response_session(session_id: str) -> bool
```
-   **`session_id`**: The ID of the session to destroy.
-   **Returns**: `True` if the session was found and destroyed, `False` otherwise.

### `list_request_response_sessions()`

Lists all active dynamic sessions managed by the component. **Only available in multi-session mode.**

```python
self.list_request_response_sessions() -> List[Dict[str, Any]]
```
-   **Returns**: A list of dictionaries, each containing status information about an active session.

---

## 5. Use Cases and Examples

### Synchronous Request-Response

The component sends a request and waits for a single reply.

```python
# In your component's invoke method
from solace_ai_connector.common.message import Message

request_message = Message(payload={"query": "user_profile", "id": 123}, topic="service/request")

try:
    # This call will block until a response is received or it times out
    response_message = self.do_broker_request_response(request_message)
    if response_message:
        log.info(f"Received response: {response_message.get_payload()}")
        return response_message.get_payload()
except TimeoutError:
    log.error("Request for user profile timed out.")
    return {"error": "timeout"}
```

### Streaming Response

The component receives multiple chunks of a response and aggregates them.

```python
# In your component's invoke method
request_message = Message(payload={"prompt": "Tell me a long story"}, topic="llm/request/stream")

# This expression will be evaluated on each response chunk.
# The stream ends when a chunk's payload contains `{"done": true}`.
streaming_complete_expr = "input.payload:done"

try:
    response_generator = self.do_broker_request_response(
        request_message,
        stream=True,
        streaming_complete_expression=streaming_complete_expr
    )

    full_story = ""
    for chunk_message, is_last in response_generator:
        chunk_payload = chunk_message.get_payload()
        full_story += chunk_payload.get("text", "")
        if is_last:
            log.info("Final chunk received. Story is complete.")
            break

    return {"story": full_story}
except TimeoutError:
    log.error("Streaming request timed out.")
    return {"error": "timeout"}
```

### Asynchronous Request (Fire-and-Forget)

This pattern allows a component to send a request and continue processing immediately, while a separate flow handles the reply.

**1. The Requesting Component**

The requesting component sets `wait_for_response=False`.

```python
# In a component in a "requester" app
def invoke(self, message, data):
    request_message = Message(payload={"command": "start_batch_job"}, topic="jobs/control")

    # This call returns immediately
    self.do_broker_request_response(
        request_message,
        wait_for_response=False
    )

    log.info("Sent 'start_batch_job' command and continued processing.")
    return None # End of this flow
```

**2. The Reply-Handling Flow**

A completely separate flow must be configured to listen for the asynchronous replies. The reply topic is determined by the request-response controller's configuration (e.g., `reply/...`).

```yaml
# In config.yaml, a separate app/flow to handle replies
apps:
  - name: "reply_handler_app"
    broker:
      broker_url: "${SOLACE_BROKER_URL}"
      broker_username: "${SOLACE_USERNAME}"
      broker_password: "${SOLACE_PASSWORD}"
      broker_vpn: "${SOLACE_VPN}"
      input_enabled: true
      queue_name: "async_replies_queue"
    components:
      - name: "reply_processor"
        component_module: "user_processor"
        subscriptions:
          # Subscribe to the reply topic pattern used by the request-response controller
          - topic: "reply/>"
        component_config:
          component_processing: |
            def process_reply(message):
                log.info(f"Received async reply: {message.get_payload()}")
                # Further processing of the reply...
                return None # End of flow
```

### Dynamic Multi-Session Usage

This example shows how a component can manage sessions for different tenants.

```python
# In an advanced component with multi-session mode enabled
def invoke(self, message, data):
    tenant_id = data.get("tenant_id")
    tenant_broker_url = self.get_tenant_broker_url(tenant_id) # Your logic to get tenant config

    # Create a session for this tenant if it doesn't exist
    session_id = self.kv_store_get(f"session_{tenant_id}")
    if not session_id:
        log.info(f"Creating new session for tenant {tenant_id}")
        session_id = self.create_request_response_session(
            session_config_overrides={"broker_url": tenant_broker_url}
        )
        self.kv_store_set(f"session_{tenant_id}", session_id)

    # Use the specific session for the request
    request_message = Message(payload=data.get("payload"), topic="tenant/service")
    try:
        response = self.do_broker_request_response(request_message, session_id=session_id)
        return response.get_payload()
    except Exception as e:
        log.error(f"Error on session {session_id} for tenant {tenant_id}: {e}")
        # Optionally, destroy and recreate the session on failure
        self.destroy_request_response_session(session_id)
        self.kv_store_set(f"session_{tenant_id}", None)
        raise
```

---

## 6. Error Handling and Troubleshooting

When using request-response, be prepared to handle the following:

-   `TimeoutError`: Raised if a response is not received within the configured `request_expiry_ms`.
-   `SessionLimitExceededError`: (Multi-session) Raised by `create_request_response_session` if `max_sessions` is reached.
-   `SessionNotFoundError`: (Multi-session) Raised if a `session_id` is provided to `do_broker_request_response` or `destroy_request_response_session` that does not exist.
-   `SessionClosedError`: (Multi-session) Raised if an operation is attempted on a session that has been closed or has expired.

**Common Issues:**

-   **Resource Leaks (Multi-Session):** Forgetting to call `destroy_request_response_session` will lead to orphaned connections, threads, and queues on the broker. Always ensure sessions are cleaned up, perhaps in a `finally` block or a component `cleanup` method.
-   **Incorrect `streaming_complete_expression`:** If this expression never evaluates to true, a streaming request will always time out. Ensure the replying service sets the flag correctly in the last message.
-   **No Reply Handler for Fire-and-Forget:** When using `wait_for_response=False`, ensure you have a separate flow subscribed to the correct reply topic to process the responses, or they will be discarded by the broker.
