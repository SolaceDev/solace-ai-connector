# Command and Control Topics and Schemas

This document defines the topic structure and data schemas used by the command and control system in the Solace AI Connector.

## Topic Structure

The command and control system uses a hierarchical topic structure for different types of messages:

### Command Topics

Commands are sent to the connector on topics with the following pattern:

    <namespace>/sac-control/v1/<method>/<endpoint>

Where:
- `<namespace>` is a configurable prefix (default: `solace`)
- `<method>` is the HTTP method (GET, POST, PUT, DELETE)
- `<endpoint>` is the API endpoint path

Examples:
- `solace/sac-control/v1/GET/connector`
- `solace/sac-control/v1/POST/flows/flow1/start`
- `solace/sac-control/v1/PUT/components/component1/config`

### Response Topics

Responses are sent back to the requester on topics with the following pattern:

    <reply-prefix>/sac-control/v1/response/<request_id>

Where:
- `<reply-prefix>` is provided by the requester in the command message
- `<request_id>` is the unique identifier for the request

Example:
- `client123/sac-control/v1/response/req-456`

### Status Topics

Status updates are published on topics with the following pattern:

    <namespace>/sac-control/v1/status/<entity_id>

Where:
- `<entity_id>` is the identifier of the entity publishing its status

Example:
- `solace/sac-control/v1/status/connector`
- `solace/sac-control/v1/status/flow/flow1`

### Metrics Topics

Metrics are published on topics with the following pattern:

    <namespace>/sac-control/v1/metrics/<entity_id>

Where:
- `<entity_id>` is the identifier of the entity publishing its metrics

Example:
- `solace/sac-control/v1/metrics/connector`
- `solace/sac-control/v1/metrics/component/component1`

### Trace Topics

Trace information is published on topics with the following pattern:

    <namespace>/sac-control/v1/trace/<entity_id>/<trace_level>

Where:
- `<entity_id>` is the identifier of the entity publishing trace information
- `<trace_level>` is the level of the trace (DEBUG, INFO, WARN, ERROR)

Example:
- `solace/sac-control/v1/trace/connector/INFO`
- `solace/sac-control/v1/trace/flow/flow1/ERROR`

### Registry Topics

Entity registry information is published on topics with the following pattern:

    <namespace>/sac-control/v1/registry

Example:
- `solace/sac-control/v1/registry`

## Message Schemas

### Command Message Schema

    {
        "request_id": "string",
        "method": "GET|POST|PUT|DELETE",
        "endpoint": "string",
        "path_params": {
            "param_name": "value"
        },
        "query_params": {
            "param_name": "value"
        },
        "body": "any",
        "timestamp": "string (ISO 8601)",
        "source": "string",
        "reply_to_topic_prefix": "string"
    }

Example:

    {
        "request_id": "req-123",
        "method": "GET",
        "endpoint": "/flows/flow1",
        "path_params": {
            "flow_id": "flow1"
        },
        "query_params": {
            "include_metrics": "true"
        },
        "body": null,
        "timestamp": "2023-05-15T14:30:00Z",
        "source": "admin-console",
        "reply_to_topic_prefix": "admin-console/replies"
    }

### Response Message Schema

    {
        "request_id": "string",
        "status_code": "number",
        "status_message": "string",
        "headers": {
            "header_name": "value"
        },
        "body": "any",
        "timestamp": "string (ISO 8601)"
    }

Example:

    {
        "request_id": "req-123",
        "status_code": 200,
        "status_message": "OK",
        "headers": {
            "content-type": "application/json"
        },
        "body": {
            "id": "flow1",
            "name": "Data Processing Flow",
            "status": "running",
            "components": 5
        },
        "timestamp": "2023-05-15T14:30:01Z"
    }

### Status Message Schema

    {
        "entity_id": "string",
        "entity_type": "string",
        "status": "string",
        "details": {
            "attribute_name": "value"
        },
        "timestamp": "string (ISO 8601)"
    }

Example:

    {
        "entity_id": "flow1",
        "entity_type": "flow",
        "status": "running",
        "details": {
            "uptime": 3600,
            "messages_processed": 1000,
            "error_count": 0,
            "health": "healthy"
        },
        "timestamp": "2023-05-15T14:30:00Z"
    }

### Metrics Message Schema

    {
        "entity_id": "string",
        "entity_type": "string",
        "metrics": {
            "metric_name": {
                "value": "number",
                "unit": "string",
                "type": "counter|gauge|histogram",
                "timestamp": "string (ISO 8601)"
            }
        }
    }

Example:

    {
        "entity_id": "component1",
        "entity_type": "component",
        "metrics": {
            "messages_processed": {
                "value": 1000,
                "unit": "messages",
                "type": "counter",
                "timestamp": "2023-05-15T14:30:00Z"
            },
            "processing_time": {
                "value": 250,
                "unit": "milliseconds",
                "type": "gauge",
                "timestamp": "2023-05-15T14:30:00Z"
            }
        }
    }

### Trace Message Schema

    {
        "entity_id": "string",
        "entity_type": "string",
        "trace_level": "DEBUG|INFO|WARN|ERROR",
        "request_id": "string",
        "operation": "string",
        "stage": "start|progress|completion",
        "duration_ms": "number",
        "data": "any",
        "error": {
            "message": "string",
            "code": "string",
            "stack": "string"
        },
        "timestamp": "string (ISO 8601)"
    }

Example:

    {
        "entity_id": "flow1",
        "entity_type": "flow",
        "trace_level": "INFO",
        "request_id": "req-123",
        "operation": "process_message",
        "stage": "completion",
        "duration_ms": 150,
        "data": {
            "message_id": "msg-456",
            "size": 1024
        },
        "error": null,
        "timestamp": "2023-05-15T14:30:00Z"
    }

### Registry Message Schema

    {
        "instance_id": "string",
        "entities": [
            {
                "entity_id": "string",
                "entity_type": "string",
                "entity_name": "string",
                "description": "string",
                "version": "string",
                "endpoints": [
                    {
                        "path": "string",
                        "methods": ["GET", "POST", "PUT", "DELETE"]
                    }
                ]
            }
        ],
        "timestamp": "string (ISO 8601)"
    }

Example:

    {
        "instance_id": "connector-1",
        "entities": [
            {
                "entity_id": "connector",
                "entity_type": "connector",
                "entity_name": "Solace AI Connector",
                "description": "Main connector instance",
                "version": "1.0.0",
                "endpoints": [
                    {
                        "path": "/connector",
                        "methods": ["GET"]
                    },
                    {
                        "path": "/connector/status",
                        "methods": ["GET"]
                    }
                ]
            },
            {
                "entity_id": "flow1",
                "entity_type": "flow",
                "entity_name": "Data Processing Flow",
                "description": "Processes incoming data",
                "version": "1.0.0",
                "endpoints": [
                    {
                        "path": "/flows/flow1",
                        "methods": ["GET"]
                    },
                    {
                        "path": "/flows/flow1/status",
                        "methods": ["GET"]
                    }
                ]
            }
        ],
        "timestamp": "2023-05-15T14:30:00Z"
    }

## Entity Registration Schema

When a component registers with the command and control system, it provides the following information:

    {
        "entity_id": "string",
        "entity_type": "string",
        "entity_name": "string",
        "description": "string",
        "version": "string",
        "parent_entity_id": "string (optional)",
        "endpoints": [
            {
                "path": "string",
                "methods": {
                    "GET": {
                        "description": "string",
                        "path_params": {
                            "param_name": {
                                "type": "string",
                                "description": "string",
                                "required": true
                            }
                        },
                        "query_params": {
                            "param_name": {
                                "type": "string",
                                "description": "string",
                                "required": false,
                                "default": "value"
                            }
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {}
                        },
                        "handler": "function_reference"
                    }
                }
            }
        ],
        "status_attributes": [
            {
                "name": "string",
                "description": "string",
                "type": "string",
                "possible_values": ["value1", "value2"]
            }
        ],
        "metrics": [
            {
                "name": "string",
                "description": "string",
                "type": "counter|gauge|histogram",
                "unit": "string"
            }
        ],
        "configuration": {
            "current_config": {},
            "mutable_paths": ["path.to.config"],
            "config_schema": {}
        }
    }

Example:

    {
        "entity_id": "llm_component_1",
        "entity_type": "component",
        "entity_name": "LLM Processing Component",
        "description": "Processes text using a large language model",
        "version": "1.0.0",
        "parent_entity_id": "flow1",
        "endpoints": [
            {
                "path": "/components/llm_component_1/prompt",
                "methods": {
                    "POST": {
                        "description": "Send a prompt to the LLM",
                        "path_params": {},
                        "query_params": {
                            "temperature": {
                                "type": "number",
                                "description": "Temperature parameter for generation",
                                "required": false,
                                "default": 0.7
                            }
                        },
                        "request_body_schema": {
                            "type": "object",
                            "properties": {
                                "prompt": {
                                    "type": "string",
                                    "description": "The prompt text"
                                }
                            },
                            "required": ["prompt"]
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "response": {
                                    "type": "string",
                                    "description": "The generated response"
                                }
                            }
                        },
                        "handler": "handle_prompt_request"
                    }
                }
            }
        ],
        "status_attributes": [
            {
                "name": "state",
                "description": "Current operational state",
                "type": "string",
                "possible_values": ["idle", "processing", "error"]
            }
        ],
        "metrics": [
            {
                "name": "prompts_processed",
                "description": "Number of prompts processed",
                "type": "counter",
                "unit": "prompts"
            },
            {
                "name": "average_response_time",
                "description": "Average time to generate a response",
                "type": "gauge",
                "unit": "milliseconds"
            }
        ],
        "configuration": {
            "current_config": {
                "model": "gpt-4",
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "mutable_paths": ["temperature", "max_tokens"],
            "config_schema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "The LLM model to use"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate",
                        "minimum": 1,
                        "maximum": 4096
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature parameter",
                        "minimum": 0,
                        "maximum": 1
                    }
                }
            }
        }
    }
