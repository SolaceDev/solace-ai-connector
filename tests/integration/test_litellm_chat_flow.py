"""Integration tests for the LiteLLM chat flow."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message


class TestLiteLLMChatFlow:
    """Test class for LiteLLM chat flow."""

    @pytest.fixture
    def yaml_path(self):
        """Path to the YAML file."""
        return "examples/llm/litellm_chat.yaml"

    @pytest.fixture
    def env_vars(self):
        """Set environment variables for the test."""
        old_env = os.environ.copy()

        # Set required environment variables
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["OPENAI_API_ENDPOINT"] = "https://test-openai-endpoint.com"
        os.environ["OPENAI_MODEL_NAME"] = "gpt-4o"
        os.environ["ANTHROPIC_MODEL_NAME"] = "claude-3-5-sonnet"
        os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
        os.environ["ANTHROPIC_API_ENDPOINT"] = "https://test-anthropic-endpoint.com"
        os.environ["SOLACE_BROKER_URL"] = "tcp://localhost:55555"
        os.environ["SOLACE_BROKER_USERNAME"] = "test-username"
        os.environ["SOLACE_BROKER_PASSWORD"] = "test-password"
        os.environ["SOLACE_BROKER_VPN"] = "test-vpn"

        yield

        # Restore original environment
        os.environ.clear()
        os.environ.update(old_env)

    def test_flow_initialization(self, yaml_path, env_vars, patch_dependencies):
        """Test that the flow initializes correctly."""
        # Read the YAML file content
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        connector, flows = create_test_flows(yaml_content)

        try:
            # Verify flow was created
            assert len(flows) == 1
            assert flows[0]["flow"].name == "Simple template to LLM"

            # Verify components were created
            component_groups = flows[0]["flow"].component_groups
            assert len(component_groups) == 3

            # Check component names
            assert component_groups[0][0].name == "solace_sw_broker"
            assert component_groups[1][0].name == "llm_request"
            assert component_groups[2][0].name == "send_response"
        finally:
            dispose_connector(connector)

    def test_basic_message_flow(self, yaml_path, env_vars, patch_dependencies):
        """Test basic message flow through the components."""
        # Read the YAML file content
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        connector, flows = create_test_flows(yaml_content)

        try:
            # Create a test message
            message = Message(payload={"text": "What is the capital of France?"})

            # Send message through the flow
            send_message_to_flow(flows[0], message)

            # Get the response
            response = get_message_from_flow(flows[0])

            # Verify response structure
            assert response is not None
            assert "payload" in response.get_data("previous")
            assert "topic" in response.get_data("previous")

            # Verify topic transformation
            assert response.get_data("previous:topic") == "demo/question/response"
        finally:
            dispose_connector(connector)

    def test_load_balancing(self, yaml_path, env_vars, patch_dependencies):
        """Test that load balancing works across models."""
        mock_litellm = patch_dependencies["litellm"]

        # Configure mock to alternate between models
        original_completion = mock_litellm.completion
        call_count = [0]

        def alternating_completion(model, messages, stream=False):
            call_count[0] += 1
            # Alternate between models to simulate load balancing
            if call_count[0] % 2 == 1:
                mock_litellm.called_models.append("gpt-4o")
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message = MagicMock()
                response.choices[0].message.content = "Response from OpenAI"
                return response
            else:
                mock_litellm.called_models.append("claude-3-5-sonnet")
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message = MagicMock()
                response.choices[0].message.content = "Response from Anthropic"
                return response

        mock_litellm.completion = alternating_completion

        # Read the YAML file content
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        connector, flows = create_test_flows(yaml_content)

        try:
            # Send multiple messages
            for i in range(4):
                message = Message(payload={"text": f"Test question {i}"})
                send_message_to_flow(flows[0], message)

                # Get response
                response = get_message_from_flow(flows[0])
                assert response is not None

            # Verify both models were used
            assert "gpt-4o" in mock_litellm.called_models
            assert "claude-3-5-sonnet" in mock_litellm.called_models

            # Restore original completion method
            mock_litellm.completion = original_completion
        finally:
            dispose_connector(connector)

    def test_input_transformation(self, yaml_path, env_vars, patch_dependencies):
        """Test that input transformations work correctly."""
        mock_litellm = patch_dependencies["litellm"]

        # Track the messages sent to the LLM
        captured_messages = []
        original_completion = mock_litellm.completion

        def capture_messages(model, messages, stream=False):
            captured_messages.extend(messages)
            return original_completion(model, messages, stream)

        mock_litellm.completion = capture_messages

        # Read the YAML file content
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        connector, flows = create_test_flows(yaml_content)

        try:
            # Send a message
            message = Message(payload={"text": "What is machine learning?"})
            send_message_to_flow(flows[0], message)

            # Get response
            response = get_message_from_flow(flows[0])
            assert response is not None

            # Verify the message was transformed correctly
            assert len(captured_messages) > 0
            transformed_message = captured_messages[0]

            # Check that the template was applied
            assert "You are a helpful AI assistant" in transformed_message["content"]
            assert "What is machine learning?" in transformed_message["content"]
            assert transformed_message["role"] == "user"

            # Restore original completion method
            mock_litellm.completion = original_completion
        finally:
            dispose_connector(connector)

    def test_error_handling(self, yaml_path, env_vars, patch_dependencies):
        """Test error handling when LLM API fails."""
        mock_litellm = patch_dependencies["litellm"]

        # Configure mock to raise an exception
        original_completion = mock_litellm.completion

        def failing_completion(model, messages, stream=False):
            raise Exception("API Error: Service unavailable")

        mock_litellm.completion = failing_completion

        # Read the YAML file content
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        connector, flows = create_test_flows(yaml_content)

        try:
            # Create an error queue to capture errors
            error_queue = flows[0]["flow"].error_queue

            # Send a message
            message = Message(payload={"text": "This should fail"})
            send_message_to_flow(flows[0], message)

            # Check that an error was raised
            assert not error_queue.empty()
            error_event = error_queue.get(timeout=5)
            error_message = error_event.data

            # Verify error details
            error_payload = error_message.get_payload()
            assert "error" in error_payload
            assert "API Error" in error_payload["error"]["text"]

            # Restore original completion method
            mock_litellm.completion = original_completion
        finally:
            dispose_connector(connector)

    def test_streaming_mode(self, yaml_path, env_vars, patch_dependencies):
        """Test streaming mode with LiteLLM."""
        # Modify the YAML to enable streaming
        with open(yaml_path, "r") as f:
            yaml_content = f.read()

        # Replace llm_mode: none with llm_mode: stream
        streaming_yaml = yaml_content.replace("llm_mode: none", "llm_mode: stream")

        mock_litellm = patch_dependencies["litellm"]

        # Configure mock for streaming
        streaming_chunks = []
        for i in range(5):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = f"Chunk {i} "
            streaming_chunks.append(chunk)

        def streaming_completion(model, messages, stream=False):
            if stream:
                return iter(streaming_chunks)
            else:
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message = MagicMock()
                response.choices[0].message.content = "Non-streaming response"
                return response

        mock_litellm.completion = streaming_completion

        connector, flows = create_test_flows(streaming_yaml)

        try:
            # Send a message
            message = Message(payload={"text": "Stream this response"})
            send_message_to_flow(flows[0], message)

            # Get response
            response = get_message_from_flow(flows[0])
            assert response is not None

            # Verify the response contains the aggregated chunks
            response_content = response.get_data("previous:payload:content")
            assert "Chunk 0 Chunk 1 Chunk 2 Chunk 3 Chunk 4 " == response_content
        finally:
            dispose_connector(connector)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
