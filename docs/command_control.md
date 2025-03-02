# Command and Control in the Solace AI Connector

The Solace AI Connector has a general facitity to allow for command and control by
way of events from the Solace Event Mesh. This is highly configurable and extensible
for the type of application being built.

## Architecture Overview

The command and control system for the Solace AI Connector is designed with the following principles:

1. **Centralized Management**: Each solace-ai-connector instance has a single command and control object that manages all entities within that instance.

2. **Entity Registration**: Components within flows register with the command and control object as managed entities, providing information about their capabilities, endpoints they expose, and configuration.

3. **Consistent Interface**: From the perspective of external management systems, the interface is consistent whether managing a single instance with many entities or many instances each with a single entity.

4. **Event-Based Communication**: The command and control object listens on configurable topics for commands and publishes responses, status updates, metrics, and trace information back to the event mesh.

5. **REST-like API**: The command and control system exposes a REST-like API over the event mesh, making it familiar and easy to integrate with external tools and systems.

6. **Hierarchical Topic Structure**: A well-defined topic hierarchy enables targeted commands and organized monitoring:
   - Commands: `<configurable-namespace>/sac-control/v1/{method}/{endpoint}`
   - Responses: `<reply-to-topic-prefix>/sac-control/v1/response/{request_id}`
   - Status: `<configurable-namespace>/sac-control/v1/status/{entity_id}`
   - Metrics: `<configurable-namespace>/sac-control/v1/metrics/{entity_id}`
   - Tracing: `<configurable-namespace>/sac-control/v1/trace/{entity_id}`

## Entity Registration

### Registration Process

When a component or flow starts up, it needs to register with the command and control system to become a managed entity. The registration process should be straightforward:

1. The component calls a registration method on the command and control object
2. The component provides information about the endpoints it wants to expose
3. The command and control object validates the registration data
4. The component is added to the registry of managed entities
5. The command and control system publishes a notification that a new entity has been registered
6. Periodically, the command and control system publishes a notification with the current list of registered entities and their endpoints

### REST-like API Endpoint Registration

Instead of registering commands, entities register endpoints in a REST-like API format:

1. **Endpoint Registration**:
   - Entities register one or more endpoints with the command and control system
   - Each endpoint has a path (e.g., `/flows/{flow_id}`, `/components/{component_id}`)
   - Endpoints support HTTP-like methods (GET, POST, PUT, DELETE)
   - Each method on an endpoint can have different parameters and responses

2. **Method Definitions**:
   - For each method on an endpoint, the entity defines:
     - Supported HTTP methods (GET, POST, PUT, DELETE)
     - Required and optional parameters
     - Parameter validation rules
     - Response schema
     - Handler function to process the request

3. **Path Parameters**:
   - Endpoints can include path parameters (e.g., `/flows/{flow_id}`)
   - The command and control system extracts these parameters from the path
   - Path parameters are passed to the handler function

4. **Query Parameters**:
   - Methods can accept query parameters
   - These are validated against the method's parameter schema

5. **Request Body**:
   - POST and PUT methods can accept a request body
   - The body is validated against the method's schema

### Registration Data Requirements

The registration data should include comprehensive information about the entity and its endpoints:

1. **Identity Information**:
   - A unique identifier for the entity
   - A human-readable name and description
   - A type or category for the entity
   - Version information

2. **Endpoint Definitions**:
   - List of endpoints the entity exposes
   - For each endpoint:
     - Path template (e.g., `/flows/{flow_id}`)
     - Supported methods (GET, POST, PUT, DELETE)
     - For each method:
       - Description
       - Path parameter definitions
       - Query parameter definitions
       - Request body schema (for POST/PUT)
       - Response schema
       - Handler function reference

3. **Status Reporting**:
   - What status attributes the entity will report
   - Possible values for each status attribute
   - Meaning of each status value

4. **Metrics**:
   - What metrics the entity will report
   - Type of each metric (counter, gauge, etc.)
   - Units of measurement
   - Sampling frequency

5. **Configuration Management**:
   - Current configuration
   - Which configuration elements can be modified at runtime
   - Validation rules for configuration changes
   - Configuration schema, including data types, constraints, is secret, etc.
   - Default values

### Benefits of REST-like API Approach

This REST-like API approach provides several advantages:

1. **Familiar Interface**: Most developers are familiar with REST APIs, making the system easier to understand and use
2. **Tool Integration**: Many existing tools can work with REST APIs
3. **Self-Documentation**: The API is self-documenting through its endpoint and method definitions
4. **Standardized Patterns**: REST provides well-established patterns for different operations (GET for retrieval, POST for creation, etc.)
5. **Versioning**: API versioning is a well-understood problem with established solutions

## Command and Response Structure

### Command Structure
Commands follow a REST-like request structure:
- `request_id`: Unique identifier for tracking/correlation
- `method`: HTTP method (GET, POST, PUT, DELETE)
- `endpoint`: The API endpoint path
- `path_params`: Parameters extracted from the endpoint path
- `query_params`: Query parameters for the request
- `body`: Request body (for POST/PUT)
- `timestamp`: When the request was issued
- `source`: Who/what issued the request
- `reply_to_topic_prefix`: Where to send the response

### Response Structure
Responses follow a REST-like response structure:
- `request_id`: Matching the original request
- `status_code`: HTTP-like status code (200, 400, 500, etc.)
- `status_message`: Human-readable status message
- `headers`: Response headers
- `body`: Response body
- `timestamp`: When the response was generated

## Implementation Considerations

### Endpoint Routing
The command and control object routes incoming requests to the appropriate entity based on the endpoint path.

### Method Handling
The entity's registered handler for the specific method on the endpoint is called to process the request.

### Parameter Validation
Request parameters are validated against the registered schema before the handler is called.

### Security Considerations
- Authentication for API requests
- Authorization for specific endpoints and methods
- Validation of request parameters
- Audit logging of all requests

### State Management
- Track current state of all managed entities
- Maintain history of requests and their outcomes
- Support for idempotent operations

### Integration with Existing Components
- Leverage the existing broker components for messaging
- Use the existing monitoring system for metrics
- Integrate with the cache service for state persistence

### Resilience Features
- Request timeout handling
- Retry mechanisms for failed requests
- Circuit breakers for problematic entities
- Graceful degradation when components are unavailable

### Versioning and Evolution
When implementing the API system, consider:
1. **API Versioning**: How to handle different versions of the API
2. **Endpoint Deregistration**: Process for when entities are removed or stopped
3. **Updates**: How to handle updates to endpoint definitions for running entities
4. **Persistence**: Whether API definitions should be persisted across restarts
5. **Scalability**: How the routing system scales with many endpoints

## Questions to Consider (and my answers)

1. How should we handle versioning of the API as the system evolves?
We will use a versioned topic structure to allow for different versions of the API to coexist and the 
endpoints themselves will be versioned.
2. Should we implement a priority system for requests, or a way to cancel in-progress operations?
No
3. How will we handle distributed request execution across multiple instances?
If multiple instances register for the same entity, we will execute the same method on all instances.
4. What's the approach for handling long-running operations that might exceed typical request/response timeframes?
No long-running operations are allowed. If a request takes too long, it will be terminated.
5. Should we implement a request queue to handle rate limiting or execution ordering?
That will naturally be handled by the Solace Event Mesh.


## High-Level Design

### System Components

The command and control system consists of the following key components:

1. **CommandControlService**: The central service that manages the entire command and control system.
   - Initializes during connector startup
   - Manages entity registration
   - Coordinates request routing and response handling
   - Publishes status updates and metrics

2. **EntityRegistry**: Maintains a registry of all managed entities and their endpoints.
   - Stores entity metadata
   - Maps endpoints to handler functions
   - Validates registration data
   - Provides lookup capabilities for request routing

3. **RequestRouter**: Routes incoming requests to the appropriate entity and handler.
   - Parses request paths
   - Extracts and validates path parameters
   - Matches requests to registered endpoints
   - Invokes the appropriate handler function

4. **BrokerAdapter**: Interfaces with the Solace Event Mesh.
   - Listens for incoming command messages
   - Publishes responses, status updates, and metrics
   - Leverages existing broker components for messaging

5. **SchemaValidator**: Validates requests and responses against schemas.
   - Validates request parameters
   - Validates request bodies
   - Validates response bodies
   - Reports validation errors

### Integration with Existing Architecture

The command and control system integrates with the existing Solace AI Connector architecture at several points:

1. **SolaceAiConnector Class**:
   - Initializes the CommandControlService during startup
   - Creates dedicated flows for command handling and response publishing
   - Provides access to the service for components via a public method
   - Registers connector-level endpoints for system-wide operations

2. **ComponentBase Class**:
   - Provides a registration method for components to register as managed entities
   - Components call this registration method in their `__init__` method
   - Each component is responsible for defining its own endpoints and handlers
   - The Flow class is not directly involved in the registration process

3. **Custom Components**:
   - Register themselves directly with the CommandControlService
   - Define their own endpoints, methods, and handlers
   - Can expose component-specific functionality through the API
   - Registration typically happens during component initialization

4. **Broker Integration**:
   - The SolaceAiConnector creates dedicated flows for command and control messaging
   - These flows use broker_input and broker_output components
   - The BrokerAdapter interfaces with these flows rather than creating its own connections
   - This ensures consistent connection management and error handling

5. **Monitoring System**:
   - Integrates with the existing monitoring system
   - Publishes metrics through the same channels
   - Reuses metric collection mechanisms

6. **Cache Service**:
   - Uses the cache service for state persistence
   - Stores command history and results
   - No persistence across restarts is required

### Data Flow

1. **Registration Flow**:
   - Component → CommandControlService → EntityRegistry
   - EntityRegistry → BrokerAdapter → Event Mesh (notification)

2. **Command Flow**:
   - Event Mesh → BrokerAdapter → RequestRouter
   - RequestRouter → EntityRegistry (lookup) → Handler Function
   - Handler Function → BrokerAdapter → Event Mesh (response)

3. **Status Update Flow**:
   - Entity → CommandControlService → BrokerAdapter → Event Mesh

4. **Metrics Flow**:
   - Entity → Monitoring System → BrokerAdapter → Event Mesh

### Tracing System

The command and control system includes a comprehensive tracing capability that allows for detailed monitoring and debugging of operations across the system:

1. **Purpose and Benefits**:
   - Tracing allows managed entities to emit trace information to the event mesh
   - External analysis tools can collect this information to track progress and debug issues
   - Provides visibility into the internal operations of the system
   - Helps identify bottlenecks, errors, and unexpected behaviors
   - Supports troubleshooting in distributed environments

2. **Configuration and Control**:
   - Tracing is controlled by the system configuration
   - Can be enabled or disabled globally at startup
   - Trace levels can be adjusted at runtime through the command API
   - Granular control allows tracing specific entities or operations
   - Configuration options currently only include trace detail level, which
     can be set to DEBUG, INFO, WARN, or ERROR

3. **Trace Data Structure**:
   - Each trace event includes:
     - Timestamp with millisecond precision
     - Entity ID that generated the trace
     - Message/request ID for correlation
     - Operation being performed
     - Execution stage (start, progress, completion)
     - Duration information for performance analysis (for completed events)
     - Custom trace data specific to the operation
     - Error information if applicable

4. **Component Integration**:
   - The ComponentBase class provides a `emit_trace()` method
   - Components can easily emit trace information without handling messaging details
   - Trace emission is non-blocking to minimize performance impact
   - Conditional logic prevents trace generation when tracing is disabled

5. **Publication and Consumption**:
   - Trace data is published to dedicated topics following the pattern:
     `<configurable-namespace>/sac-control/v1/trace/{entity_id}/{trace_level}`
   - Trace levels include DEBUG, INFO, WARN, ERROR
   - External systems can subscribe to specific trace levels or entities
   - Trace data can be consumed by logging systems, monitoring tools, or custom applications
   - Standard formats ensure compatibility with common analysis tools

6. **System Endpoints for Trace Control**:
   - `/system/trace` - GET: Get current trace configuration
   - `/system/trace` - PUT: Update trace configuration
   - `/system/trace/{entity_id}` - GET: Get trace configuration for a specific entity
   - `/system/trace/{entity_id}` - PUT: Update trace configuration for a specific entity

This tracing system provides deep visibility into the operation of the Solace AI Connector while maintaining performance and flexibility. It integrates seamlessly with the command and control architecture and leverages the existing event mesh for efficient distribution of trace information.

### Standard Endpoints

The system automatically creates a managed entity that represents the connector itself. This entity provides standard endpoints for common operations across the system. This connector entity:

- Is created automatically during system initialization
- Can be disabled via configuration, but is enabled by default
- Has a configurable name that defaults to 'solace-ai-connector'
- Includes in its description a list of all registered managed entity names to help distinguish instances when multiple connectors are running
- Provides centralized access to system-wide operations and information

The connector entity exposes the following standard endpoints:

1. **Connector Management**:
   - `/connector` - GET: Get connector information (version, uptime, instance name)
   - `/connector/status` - GET: Get connector status (running, stopping, etc.)
   - `/connector/metrics` - GET: Get connector metrics (memory usage, message counts)
   - `/connector/shutdown` - POST: Shutdown the connector gracefully

2. **Flow Management**:
   - `/flows` - GET: List all flows with their IDs and status
   - `/flows/{flow_id}` - GET: Get detailed information about a specific flow
   - `/flows/{flow_id}/status` - GET: Get current status of a specific flow
   - `/flows/{flow_id}/start` - POST: Start a flow that is currently stopped
   - `/flows/{flow_id}/stop` - POST: Stop a running flow

3. **Component Management**:
   - `/components` - GET: List all components across all flows
   - `/components/{component_id}` - GET: Get detailed information about a specific component
   - `/components/{component_id}/status` - GET: Get current status of a specific component
   - `/components/{component_id}/config` - GET/PUT: Get or update component configuration

4. **System Management**:
   - `/system/health` - GET: Get overall system health status
   - `/system/metrics` - GET: Get system-wide metrics
   - `/system/config` - GET: Get system configuration

These standard endpoints provide a consistent interface for managing the connector and its components, regardless of the specific components that are registered. They serve as a foundation that can be extended with custom endpoints provided by individual components.

This design provides a flexible, extensible command and control system that integrates seamlessly with the existing Solace AI Connector architecture while providing a familiar REST-like API over the event mesh.

## Configuration and Customization

The command and control system can be configured through the Solace AI Connector's YAML configuration file. Below are the configuration options available for the command and control system:

    command_control:
        enabled: true                      # Enable or disable the command control system
        namespace: solace                  # Namespace prefix for command control topics
        topic_prefix: sac-control/v1       # Topic prefix for command control messages
        
        # Broker configuration for command and response flows
        broker:
            broker_type: solace            # Type of broker to use (solace, dev_broker)
            queue_name: command_control    # Queue name for receiving commands
            temporary_queue: false         # Whether to use a temporary queue
            max_redelivery_count: 3        # Maximum number of redelivery attempts
        
        # Tracing configuration
        tracing:
            enabled: true                  # Enable or disable tracing
            default_level: INFO            # Default trace level (DEBUG, INFO, WARN, ERROR)
            entity_levels:                 # Override trace levels for specific entities
                connector: DEBUG
                flow1: WARN
        
        # Security configuration - Not yet implemented
        # security:
        #     enabled: false                 # Enable or disable security features
        #     authentication:
        #         enabled: false             # Enable or disable authentication
        #         method: basic              # Authentication method (basic, oauth, etc.)
        #         header_name: Authorization # Header name for authentication tokens
        #     
        #     authorization:
        #         enabled: false             # Enable or disable authorization
        #         rules:                     # Authorization rules
        #             - entity: connector
        #               operations: [GET]
        #               roles: [admin, viewer]
        #             - entity: flows
        #               operations: [GET]
        #               roles: [admin, viewer]
        #             - entity: flows
        #               operations: [POST, PUT, DELETE]
        #               roles: [admin]
        
        # Response configuration
        response:
            timeout_ms: 30000              # Timeout for waiting for responses
            include_timestamps: true       # Include timestamps in responses
            include_request_details: false # Include original request details in responses

Example configuration in a complete connector configuration file:

    instance_name: my-connector
    broker_url: tcp://localhost:55555
    broker_username: admin
    broker_password: admin
    broker_vpn: default

    # Command and control configuration
    command_control:
        enabled: true
        namespace: my-company
        topic_prefix: sac-control/v1
        
        tracing:
            enabled: true
            default_level: INFO
            entity_levels:
                connector: DEBUG

    # Rest of connector configuration
    flows:
        - name: flow1
          components:
            - component_name: input
              component_module: broker_input
              # Component configuration...

## Implementation Plan

### Phase 1: Core Framework (Sprint 1-2)

1. **Create Basic Command Control Service** [done]
   - File: `src/solace_ai_connector/command_control/command_control_service.py`
     - Implement the core CommandControlService class
     - Add entity registration methods
     - Add request handling infrastructure

   - File: `src/solace_ai_connector/command_control/entity_registry.py`
     - Implement the EntityRegistry class
     - Add methods for registering and looking up entities and endpoints

   - File: `src/solace_ai_connector/command_control/request_router.py`
     - Implement the RequestRouter class
     - Add path parsing and parameter extraction
     - Add handler invocation logic

2. **Integrate with SolaceAiConnector** [done]
   - File: `src/solace_ai_connector/solace_ai_connector.py`
     - Add CommandControlService initialization
     - Add public method for components to access the service
     - Add configuration options for command control

3. **Create Broker Adapter** [done]
   - File: `src/solace_ai_connector/command_control/broker_adapter.py`
     - Implement the BrokerAdapter class
     - Add methods for receiving commands and publishing responses
     - Add integration with existing broker components

4. **Add Schema Validation** [done]
   - File: `src/solace_ai_connector/command_control/schema_validator.py`
     - Implement the SchemaValidator class
     - Add methods for validating requests and responses
     - Add schema definition utilities

### Phase 2: Component Integration (Sprint 3)

1. **Update ComponentBase** [done]
   - File: `src/solace_ai_connector/components/component_base.py`
     - Add registration method for components
     - Add trace emission method
     - Add helper methods for defining endpoints

2. **Create Standard Connector Entity** [done]
   - File: `src/solace_ai_connector/command_control/connector_entity.py`
     - Implement the ConnectorEntity class
     - Add standard endpoints for connector management
     - Add standard endpoints for flow management
     - Add standard endpoints for component management
     - Add standard endpoints for system management

3. **Add Configuration Support** [done]
   - Integration with existing configuration system
   - Support for filtering sensitive information
   - Support for exposing mutable configuration paths

### Phase 3: Tracing System (Sprint 4)

1. **Implement Tracing Infrastructure**
   - File: `src/solace_ai_connector/command_control/tracing.py`
     - Implement the TracingSystem class
     - Add methods for emitting trace events
     - Add configuration for trace levels
     - Add integration with the event mesh

2. **Add Trace Endpoints**
   - Update: `src/solace_ai_connector/command_control/connector_entity.py`
     - Add endpoints for trace configuration
     - Add endpoints for retrieving trace status

3. **Integrate Tracing with Components**
   - Update: `src/solace_ai_connector/components/component_base.py`
     - Enhance trace emission methods
     - Add trace context management
     - Add performance measurement utilities

### Phase 4: Testing and Documentation (Sprint 5)

1. **Create Unit Tests**
   - File: `tests/command_control/test_command_control_service.py`
   - File: `tests/command_control/test_entity_registry.py`
   - File: `tests/command_control/test_request_router.py`
   - File: `tests/command_control/test_broker_adapter.py`
   - File: `tests/command_control/test_schema_validator.py`
   - File: `tests/command_control/test_tracing.py`

2. **Create Integration Tests**
   - File: `tests/command_control/test_integration.py`
     - Test end-to-end command handling
     - Test component registration
     - Test tracing system

3. **Create Example Components**
   - File: `examples/command_control/custom_component.py`
     - Demonstrate how to register a component
     - Demonstrate how to define custom endpoints
     - Demonstrate how to use tracing

4. **Update Documentation**
   - File: `docs/command_control_api.md`
     - Document the API for component developers
     - Include examples of common patterns
     - Provide troubleshooting guidance

### Phase 5: Security and Production Hardening (Sprint 6)

1. **Implement Authentication and Authorization**
   - File: `src/solace_ai_connector/command_control/security.py`
     - Add authentication mechanisms
     - Add authorization rules
     - Add audit logging

2. **Add Error Handling and Resilience**
   - Update: `src/solace_ai_connector/command_control/command_control_service.py`
     - Add comprehensive error handling
     - Add circuit breaker patterns
     - Add request timeout handling

3. **Performance Optimization**
   - Review and optimize all command control components
   - Add benchmarking tests
   - Implement caching where appropriate

4. **Final Documentation and Examples**
   - Update all documentation with final design
   - Create comprehensive examples
   - Provide migration guidance for existing components
