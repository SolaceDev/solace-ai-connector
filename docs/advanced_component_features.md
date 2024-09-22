# Advanced Component Features

This document describes advanced features available to custom components in the Solace AI Connector.

## Table of Contents
- [Broker Request-Response](#broker-request-response)
- [Cache Manager](#cache-manager)
- [Timer Features](#timer-features)

## Broker Request-Response

Components can perform a request and get a response from the broker using the `do_broker_request_response` method. This method supports both simple request-response and streamed responses.

### Usage

```python
response = self.do_broker_request_response(message, stream=False)
```

For streamed responses:

```python
for chunk, is_last in self.do_broker_request_response(message, stream=True, streaming_complete_expression="input.payload:streaming.last_message"):
    # Process each chunk
    if is_last:
        break
```

### Parameters

- `message`: The message to send to the broker. This must have a topic and payload.
- `stream` (optional): Boolean indicating whether to expect a streamed response. Default is False.
- `streaming_complete_expression` (optional): An expression to evaluate on each response chunk to determine if it's the last one. This is required when `stream=True`.

### Return Value

- For non-streamed responses: Returns the response message.
- For streamed responses: Returns a generator that yields tuples of (chunk, is_last). Each chunk is a fully formed message with the format of the response. `is_last` is a boolean indicating if the chunk is the last one.

## Memory Cache

<inst>
Describe the cache service features based on the implementation in the cache_service.py file.
</inst>

## Timer Features

<inst>
Describe the timer features based on the implementation in the timer_manager.py file.
</inst>
