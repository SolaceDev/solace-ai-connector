# Integration Tests for Solace AI Connector

This directory contains integration tests for the Solace AI Connector, specifically focusing on testing the functionality of YAML configurations.

## Overview

The integration tests verify that the flows defined in YAML configuration files work correctly end-to-end. They test the interaction between components, data transformations, and error handling.

## Test Files

- `test_litellm_chat_flow.py`: Tests for the LiteLLM chat flow defined in `examples/llm/litellm_chat.yaml`
- `test_openai_chroma_rag_flow.py`: Tests for the OpenAI ChromaDB RAG flow defined in `examples/llm/openai_chroma_rag_with_splitter.yaml`
- `conftest.py`: Shared fixtures and utilities for the integration tests

## Running the Tests

To run all integration tests:

```bash
pytest tests/integration
```

To run a specific test file:

```bash
pytest tests/integration/test_litellm_chat_flow.py
```

To run a specific test:

```bash
pytest tests/integration/test_litellm_chat_flow.py::TestLiteLLMChatFlow::test_basic_message_flow
```

## Test Design

The integration tests use mocks to simulate external dependencies such as:

- Solace broker
- LiteLLM
- OpenAI API
- ChromaDB

This allows the tests to run without requiring actual connections to these services.

### LiteLLM Chat Flow Tests

These tests verify:

1. Flow initialization and component creation
2. Basic message flow through the components
3. Load balancing across multiple LLM models
4. Input transformations
5. Error handling
6. Streaming mode

### OpenAI ChromaDB RAG Flow Tests

These tests verify:

1. Flow initialization and component creation
2. Data ingestion flow
3. Text splitting functionality
4. RAG query flow
5. End-to-end RAG pipeline
6. Error handling for empty retrievals
7. Handling of malformed queries

## Adding New Tests

To add new tests:

1. Create a new test file in the `tests/integration` directory
2. Import the necessary utilities from `conftest.py`
3. Create test classes and methods
4. Use the `patch_dependencies` fixture to mock external dependencies

## Mocking Strategy

The tests use the following mocking strategy:

- `MockMessagingService`: Simulates the Solace broker
- `MockLiteLLM`: Simulates LiteLLM responses
- `MockChromaDB`: Simulates ChromaDB functionality

These mocks are defined in `conftest.py` and are available through the `patch_dependencies` fixture.
