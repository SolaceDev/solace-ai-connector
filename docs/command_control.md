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

## Open Questions

1. How should we handle versioning of the API as the system evolves?
2. Should we implement a priority system for requests, or a way to cancel in-progress operations?
3. How will we handle distributed request execution across multiple instances?
4. What's the approach for handling long-running operations that might exceed typical request/response timeframes?
5. Should we implement a request queue to handle rate limiting or execution ordering?
