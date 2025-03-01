# Command and Control in the Solace AI Connector

The Solace AI Connector has a general facitity to allow for command and control by
way of events from the Solace Event Mesh. This is highly configurable and extensible
for the type of application being built.

<inst>
I have changed my mind about how the command registration and execution should be done.
I think that instead of registering commands with the command and control object, 
managed entities will register endpoints with the command and control object in a format
that is similar to a REST API. This will make it easier to interact with the system from 
external tools and systems.

There requests will still come in on the event mesh, 
but the command payload will provide an endpoint, method, and parameters to be used
for the command. The command and control object will then route the command to the appropriate
entity based on the endpoint. The method and endpoint will also be used to generate the request topic.

Adjust the document accordingly.

</inst>

## Architecture Overview

The command and control system for the Solace AI Connector is designed with the following principles:

1. **Centralized Management**: Each solace-ai-connector instance has a single command and control object that manages all entities within that instance.

2. **Entity Registration**: Components within flows register with the command and control object as managed entities, providing information about their capabilities, commands they support, and configuration.

3. **Consistent Interface**: From the perspective of external management systems, the interface is consistent whether managing a single instance with many entities or many instances each with a single entity.

4. **Event-Based Communication**: The command and control object listens on configurable topics for commands and publishes responses, status updates, metrics, and trace information back to the event mesh.

5. **Hierarchical Topic Structure**: A well-defined topic hierarchy enables targeted commands and organized monitoring:
   - Commands: `<configurable-namespace>/sac-control/v1/command/{entity_id}/{command_id}`
   - Responses: `<reply-to-topic-prefix>/sac-control/v1/response/{entity_id}/{command_id}`
   - Status: `<configurable-namespace>/<configurable-status-topic>/{entity_id}`
   - Metrics: `<configurable-namespace>/<configurable-metrics-topic>/{entity_id}`
   - Tracing: `<configurable-namespace>/<configurable-trace-topic>/{entity_id}`

## Entity Registration

### Registration Process

When a component or flow starts up, it needs to register with the command and control system to become a managed entity. The registration process should be straightforward:

1. The component calls a registration method on the command and control object
2. The command and control object validates the registration data
3. The component is added to the registry of managed entities
4. The command and control system publishes a notification that a new entity has been registered
5. Periodically, the command and control system publishes a notification with the current list of registered entities
6. It is acceptable for multiple objects to register with the same name, but the command and control system should handle this gracefully and keep a list of all objects with the same name so that commands can be sent to all of them. If this is not desired by the components, it is up to the component to ensure that it only registers once.

### Registration Data Requirements

The registration data should include comprehensive information about the entity to enable effective management and control. This should include:

1. **Identity Information**:
   - A unique identifier for the entity
   - A human-readable name and description
   - A type or category for the entity
   - Version information

2. **Command Interface**:
   - A list of all commands the entity can handle
   - For each command:
     - List of versions and in each version:
        - Name and description
        - Required and optional parameters with their types and descriptions
        - Each parameter can be marked as 'secret' to indicate that it should not be logged
        - Any constraints or validation rules
        - Callback function to handle the command

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

### Benefits of Comprehensive Registration

This detailed registration approach provides several advantages:

1. **Self-Documentation**: The system becomes self-documenting, with each entity describing its capabilities
2. **Dynamic Discovery**: External systems can discover what entities exist and what they can do
3. **Validation**: Commands can be validated against the registered schema before execution
4. **Runtime Configuration**: The system knows which configuration elements can be modified at runtime
5. **Consistent Monitoring**: Metrics and status reporting are standardized across all entities

## Command and Response Structure

### Command Structure
Commands should follow a consistent structure with fields like:
- `command_id`: Unique identifier for tracking/correlation
- `command_type`: The action to perform (e.g., "start_flow", "stop_flow", "update_config")
- `target_entity`: The specific component or flow to target
- `parameters`: Command-specific parameters
- `timestamp`: When the command was issued
- `source`: Who/what issued the command
- `reply_to_topic_prefix`: Where to send the response

### Response Structure
Similarly, responses should have:
- `command_id`: Matching the original command
- `status`: Success/failure
- `message`: Human-readable result or error message
- `data`: Any returned data
- `timestamp`: When the response was generated

## Implementation Considerations

### Command Handler Registry
The command and control object should maintain a registry mapping commands to handler functions, allowing components to register their capabilities.

### Security Considerations
- Authentication for command issuers
- Authorization for specific commands
- Validation of command parameters
- Audit logging of all commands

### State Management
- Track current state of all managed entities
- Maintain history of commands and their outcomes
- Support for idempotent commands

### Integration with Existing Components
- Leverage the existing broker components for messaging
- Use the existing monitoring system for metrics
- Integrate with the cache service for state persistence

### Resilience Features
- Command timeout handling
- Retry mechanisms for failed commands
- Circuit breakers for problematic entities
- Graceful degradation when components are unavailable

### Versioning and Evolution
When implementing the registration system, consider:
1. **Versioning**: How to handle different versions of entities with different capabilities
2. **Deregistration**: Process for when entities are removed or stopped
3. **Updates**: How to handle updates to registration data for running entities
4. **Persistence**: Whether registration data should be persisted across restarts
5. **Scalability**: How the registry scales with many entities

## Open Questions

1. How should we handle versioning of commands and responses as the system evolves?
2. Should we implement a priority system for commands, or a way to cancel in-progress commands?
3. How will we handle distributed command execution across multiple instances?
4. What's the approach for handling long-running commands that might exceed typical request/response timeframes?
5. Should we implement a command queue to handle rate limiting or execution ordering?
