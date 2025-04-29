"""Test that the mocks in conftest.py work correctly."""

import pytest
from unittest.mock import MagicMock

# Import the mocks from conftest.py
from conftest import MockMessagingService, MockLiteLLM, MockChromaDB


class TestMocks:
    """Test class for mocks."""

    def test_messaging_service_mock(self, mock_messaging_service):
        """Test that the messaging service mock works correctly."""
        # Test connect method
        assert mock_messaging_service.connect() is True

        # Test send_message method
        mock_messaging_service.send_message(
            payload="test payload",
            destination_name="test/topic",
            user_properties={"key": "value"},
        )

        # Verify message was sent
        assert len(mock_messaging_service.sent_messages) == 1
        sent_message = mock_messaging_service.sent_messages[0]
        assert sent_message["payload"] == "test payload"
        assert sent_message["topic"] == "test/topic"
        assert sent_message["user_properties"] == {"key": "value"}

        # Test receive_message method
        mock_message = {
            "payload": "test response",
            "topic": "test/response",
            "user_properties": {"response_key": "response_value"},
        }
        mock_messaging_service.message_queue.append(mock_message)

        received_message = mock_messaging_service.receive_message(1000, "test_queue")
        assert received_message == mock_message

        # Test queue is now empty
        assert mock_messaging_service.receive_message(1000, "test_queue") is None

        # Test ack_message method
        assert mock_messaging_service.ack_message(mock_message) is True

    def test_litellm_mock(self, mock_litellm):
        """Test that the LiteLLM mock works correctly."""
        # Test default response
        response = mock_litellm.completion(
            "gpt-4o", [{"role": "user", "content": "Hello"}]
        )
        assert response.choices[0].message.content == "This is a mock response"
        assert "gpt-4o" in mock_litellm.called_models

        # Test custom response
        custom_response = MagicMock()
        custom_response.choices = [MagicMock()]
        custom_response.choices[0].message = MagicMock()
        custom_response.choices[0].message.content = "Custom response"

        mock_litellm.set_response("claude-3-5-sonnet", custom_response)
        response = mock_litellm.completion(
            "claude-3-5-sonnet", [{"role": "user", "content": "Hello"}]
        )
        assert response.choices[0].message.content == "Custom response"

        # Test streaming response
        streaming_response = list(
            mock_litellm.completion(
                "gpt-4o", [{"role": "user", "content": "Hello"}], stream=True
            )
        )
        assert len(streaming_response) == 1
        assert (
            streaming_response[0].choices[0].delta.content
            == "This is a mock streaming response"
        )

    def test_chromadb_mock(self, mock_chromadb):
        """Test that the ChromaDB mock works correctly."""
        # Test collection creation
        mock_chromadb.get_or_create_collection("test_collection")
        assert "test_collection" in mock_chromadb.collections

        # Test adding documents
        documents = ["Document 1", "Document 2", "Document 3"]
        metadatas = [
            {"source": "source1"},
            {"source": "source2"},
            {"source": "source3"},
        ]

        mock_chromadb.add(documents, metadatas=metadatas)

        # Verify documents were added
        collection = mock_chromadb.collections["test_collection"]
        assert len(collection["documents"]) == 3
        assert collection["documents"] == documents
        assert collection["metadatas"] == metadatas

        # Test query
        results = mock_chromadb.query(query_embeddings=[[0.1] * 10], n_results=2)
        assert len(results["documents"]) == 2
        assert results["documents"] == documents[:2]
        assert results["metadatas"] == metadatas[:2]

    def test_patch_dependencies(self, patch_dependencies):
        """Test that the patch_dependencies fixture works correctly."""
        # Verify that all mocks are available
        assert "messaging_service" in patch_dependencies
        assert "litellm" in patch_dependencies
        assert "chromadb" in patch_dependencies

        # Verify that the mocks are the correct types
        assert isinstance(patch_dependencies["messaging_service"], MockMessagingService)
        assert isinstance(patch_dependencies["litellm"], MockLiteLLM)
        assert isinstance(patch_dependencies["chromadb"], MockChromaDB)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
