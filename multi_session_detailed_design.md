# Multi-Session Request/Reply Detailed Design Document

## File Structure and Class Locations

### New Files to Create:

```
src/solace_ai_connector/flow/
├── multi_session_request_response_manager.py    # Main manager class
├── request_response_session.py                  # Individual session wrapper
└── session_registry.py                          # Thread-safe session registry

src/solace_ai_connector/common/
└── session_config.py                           # Session configuration classes
```

### Modified Files:

```
src/solace_ai_connector/components/
└── component_base.py                           # Add multi-session API methods

src/solace_ai_connector/flow/
└── request_response_flow_controller.py         # Minor modifications for session support
```

## Detailed Class Design

### 1. MultiSessionRequestResponseManager
**Location**: `src/solace_ai_connector/flow/multi_session_request_response_manager.py`

```python
class MultiSessionRequestResponseManager:
    """
    Manages multiple independent request/response sessions for a component.
    
    State Management:
    - session_registry: SessionRegistry instance
    - component_ref: WeakReference to parent component
    - default_broker_config: Default broker configuration
    - cleanup_thread: Background thread for session cleanup
    - _lock: Threading lock for thread safety
    """
    
    def __init__(self, component, default_broker_config=None):
        self.component_ref = weakref.ref(component)
        self.session_registry = SessionRegistry()
        self.default_broker_config = default_broker_config or {}
        self.cleanup_thread = None
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        
    # State stored in instance variables:
    # - Active sessions tracked in session_registry
    # - Component reference for callbacks
    # - Default configurations for new sessions
```

**Key Methods**:
- `create_session(session_config) -> str`: Creates new session, returns session_id
- `destroy_session(session_id) -> bool`: Destroys session and cleans up resources
- `get_session(session_id) -> RequestResponseSession`: Retrieves session by ID
- `list_sessions() -> List[str]`: Returns list of active session IDs
- `cleanup_expired_sessions()`: Background cleanup of expired sessions
- `shutdown()`: Cleanup all sessions and stop background threads

### 2. RequestResponseSession
**Location**: `src/solace_ai_connector/flow/request_response_session.py`

```python
class RequestResponseSession:
    """
    Wraps a RequestResponseFlowController with session-specific configuration.
    
    State Management:
    - session_id: Unique identifier for this session
    - config: SessionConfig instance with all session parameters
    - controller: RequestResponseFlowController instance
    - created_at: Timestamp of session creation
    - last_used_at: Timestamp of last request
    - active_requests: Set of active request IDs
    - _lock: Threading lock for request tracking
    """
    
    def __init__(self, session_id: str, config: SessionConfig, connector):
        self.session_id = session_id
        self.config = config
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.active_requests = set()
        self._lock = threading.RLock()
        
        # Create the underlying RequestResponseFlowController
        self.controller = RequestResponseFlowController(
            config=config.to_controller_config(),
            connector=connector
        )
        
    # State stored in instance variables:
    # - Session metadata (ID, timestamps, config)
    # - Active request tracking for cleanup
    # - Wrapped RequestResponseFlowController
```

**Key Methods**:
- `do_request_response(message, stream, streaming_complete_expression)`: Execute request/response
- `is_expired() -> bool`: Check if session has expired based on config
- `get_active_request_count() -> int`: Number of active requests
- `cleanup() -> None`: Clean up resources and stop controller
- `update_last_used()`: Update last used timestamp

### 3. SessionRegistry
**Location**: `src/solace_ai_connector/flow/session_registry.py`

```python
class SessionRegistry:
    """
    Thread-safe registry for tracking active sessions.
    
    State Management:
    - _sessions: Dict[str, RequestResponseSession] - Active sessions by ID
    - _lock: Threading RLock for thread safety
    - _session_counter: Atomic counter for generating unique session IDs
    """
    
    def __init__(self):
        self._sessions: Dict[str, RequestResponseSession] = {}
        self._lock = threading.RLock()
        self._session_counter = 0
        
    # State stored in instance variables:
    # - Dictionary of active sessions
    # - Thread synchronization primitives
    # - Session ID generation counter
```

**Key Methods**:
- `register_session(session: RequestResponseSession) -> None`: Add session to registry
- `unregister_session(session_id: str) -> RequestResponseSession`: Remove and return session
- `get_session(session_id: str) -> RequestResponseSession`: Retrieve session by ID
- `list_session_ids() -> List[str]`: Get all active session IDs
- `get_expired_sessions(max_age_seconds: int) -> List[RequestResponseSession]`: Find expired sessions
- `clear() -> List[RequestResponseSession]`: Remove all sessions and return them

### 4. SessionConfig
**Location**: `src/solace_ai_connector/common/session_config.py`

```python
@dataclass
class SessionConfig:
    """
    Configuration for a request/response session.
    
    State Management:
    All configuration is stored as immutable dataclass fields:
    - broker_config: Dict with broker connection parameters
    - request_expiry_ms: Request timeout in milliseconds
    - response_topic_prefix: Prefix for reply topics
    - response_queue_prefix: Prefix for temp queue names
    - session_timeout_seconds: Session idle timeout
    - max_concurrent_requests: Limit on concurrent requests per session
    """
    
    broker_config: Dict[str, Any]
    request_expiry_ms: int = 30000
    response_topic_prefix: str = "reply"
    response_queue_prefix: str = "reply-queue"
    session_timeout_seconds: int = 3600  # 1 hour default
    max_concurrent_requests: int = 100
    user_properties_reply_topic_key: str = "__solace_ai_connector_broker_request_response_topic__"
    user_properties_reply_metadata_key: str = "__solace_ai_connector_broker_request_reply_metadata__"
    response_topic_insertion_expression: str = ""
    
    # State is immutable after creation
    # All fields have defaults except broker_config
```

**Key Methods**:
- `to_controller_config() -> Dict`: Convert to RequestResponseFlowController config format
- `validate() -> None`: Validate configuration parameters
- `merge_with_defaults(defaults: Dict) -> SessionConfig`: Merge with default config

## State Management Details

### Component-Level State (ComponentBase)
**Location**: `src/solace_ai_connector/components/component_base.py`

```python
class ComponentBase:
    def __init__(self, ...):
        # Existing state...
        
        # NEW: Multi-session support
        self._multi_session_manager = None  # Lazy initialization
        self._multi_session_enabled = False
        
    # State additions:
    # - _multi_session_manager: MultiSessionRequestResponseManager instance
    # - _multi_session_enabled: Boolean flag for feature enablement
```

### Session State Lifecycle

1. **Session Creation**:
   ```
   User calls create_session() 
   → MultiSessionRequestResponseManager creates RequestResponseSession
   → Session creates RequestResponseFlowController with unique config
   → Session registered in SessionRegistry
   → Session ID returned to user
   ```

2. **Session Usage**:
   ```
   User calls do_broker_request_response(message, session_id=session_id)
   → ComponentBase looks up session in MultiSessionRequestResponseManager
   → Session updates last_used_at timestamp
   → Session delegates to its RequestResponseFlowController
   → Response returned to user
   ```

3. **Session Cleanup**:
   ```
   Background cleanup thread or explicit destroy_session() call
   → Session removed from SessionRegistry
   → RequestResponseFlowController cleanup() called
   → Temp queues and broker connections cleaned up
   → Session object eligible for garbage collection
   ```

## Thread Safety and Concurrency

### Locking Strategy:
1. **SessionRegistry**: Uses RLock for all operations on the sessions dictionary
2. **RequestResponseSession**: Uses RLock for active request tracking
3. **MultiSessionRequestResponseManager**: Uses RLock for session creation/destruction

### Concurrency Patterns:
1. **Multiple sessions can handle requests simultaneously** - Each session has its own RequestResponseFlowController
2. **Session registry operations are atomic** - All registry modifications are protected by locks
3. **Background cleanup is non-blocking** - Cleanup thread operates independently

## Memory Management

### Object Lifecycle:
1. **Sessions are created on-demand** and stored in SessionRegistry
2. **Sessions are removed** when explicitly destroyed or expired
3. **Weak references** used where appropriate to prevent circular references
4. **RequestResponseFlowController cleanup** ensures broker resources are released

### Resource Cleanup:
1. **Temp queues** are automatically deleted when RequestResponseFlowController is destroyed
2. **Broker connections** are properly closed during session cleanup
3. **Background threads** are stopped during component shutdown
4. **Active requests** are tracked and can be cancelled during session destruction

## Integration Points

### With Existing Code:
1. **ComponentBase.do_broker_request_response()** - Extended to support session_id parameter
2. **RequestResponseFlowController** - Used as-is, no modifications needed
3. **BrokerRequestResponse** - Used indirectly through RequestResponseFlowController

### Backward Compatibility:
1. **Existing single-session behavior** preserved when session_id is None
2. **Component-level broker_request_response config** still supported
3. **App-level request_reply_enabled** still works for default session

## Configuration Examples

### Component Configuration:
```yaml
components:
  - component_name: my_component
    component_module: my_module
    multi_session_request_response:
      enabled: true
      default_broker_config:
        broker_url: tcp://localhost:55555
        broker_username: default_user
        broker_password: default_pass
        broker_vpn: default_vpn
      session_timeout_seconds: 1800
```

### Runtime Session Creation:
```python
# Create session with custom config
session_id = component.create_request_response_session(
    broker_config={
        "broker_url": "tcp://prod-broker:55555",
        "broker_username": "prod_user",
        "broker_password": "prod_pass",
        "broker_vpn": "prod_vpn"
    },
    request_expiry_ms=60000,
    response_topic_prefix="prod/replies",
    session_timeout_seconds=3600
)

# Use the session
response = component.do_broker_request_response(
    message, 
    session_id=session_id
)
```

## Error Handling Strategy

### Session-Level Errors:
1. **Session creation failures** - Return None and log error
2. **Session not found** - Raise ValueError with clear message
3. **Session expired** - Automatically clean up and raise SessionExpiredError
4. **Broker connection failures** - Propagate from RequestResponseFlowController

### Recovery Mechanisms:
1. **Automatic session cleanup** for expired or failed sessions
2. **Graceful degradation** - Fall back to default session if multi-session fails
3. **Resource leak prevention** - Ensure cleanup even on exceptions
4. **Request tracking** - Cancel active requests when session is destroyed

This detailed design provides a complete blueprint for implementing the multi-session request/reply functionality while maintaining clean separation of concerns and robust state management.