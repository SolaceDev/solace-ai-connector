"""Integration tests for the OpenAI ChromaDB RAG flow."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.append("src")

# Mock langchain modules
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_chroma"] = MagicMock()

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message


class TestOpenAIChromaRAGFlow:
    """Test class for OpenAI ChromaDB RAG flow."""

    @pytest.fixture
    def yaml_path(self):
        """Path to the YAML file."""
        return "examples/llm/openai_chroma_rag_with_splitter.yaml"

    @pytest.fixture
    def env_vars(self):
        """Set environment variables for the test."""
        old_env = os.environ.copy()

        # Set required environment variables
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["OPENAI_API_ENDPOINT"] = "https://test-openai-endpoint.com"
        os.environ["OPENAI_EMBEDDING_MODEL_NAME"] = "text-embedding-ada-002"
        os.environ["OPENAI_MODEL_NAME"] = "gpt-4o"
        os.environ["SOLACE_BROKER_URL"] = "tcp://localhost:55555"
        os.environ["SOLACE_BROKER_USERNAME"] = "test-username"
        os.environ["SOLACE_BROKER_PASSWORD"] = "test-password"
        os.environ["SOLACE_BROKER_VPN"] = "test-vpn"

        yield

        # Restore original environment
        os.environ.clear()
        os.environ.update(old_env)

    def test_flow_initialization(self, yaml_path, env_vars, patch_dependencies):
        """Test that the flows initialize correctly."""
        connector, flows = create_test_flows(yaml_path)

        try:
            # Verify flows were created
            assert len(flows) == 2

            # Verify flow names
            flow_names = [flow["flow"].name for flow in flows]
            assert "chroma_ingest" in flow_names
            assert "OpenAI_RAG" in flow_names

            # Get the ingest flow
            ingest_flow = next(
                flow for flow in flows if flow["flow"].name == "chroma_ingest"
            )

            # Verify ingest flow components
            ingest_components = ingest_flow["flow"].component_groups
            assert len(ingest_components) == 4

            # Check component names for ingest flow
            assert ingest_components[0][0].name == "solace_data_input"
            assert ingest_components[1][0].name == "text_splitter"
            assert ingest_components[2][0].name == "chroma_embed"
            assert ingest_components[3][0].name == "send_response"

            # Get the RAG flow
            rag_flow = next(flow for flow in flows if flow["flow"].name == "OpenAI_RAG")

            # Verify RAG flow components
            rag_components = rag_flow["flow"].component_groups
            assert len(rag_components) == 4

            # Check component names for RAG flow
            assert rag_components[0][0].name == "solace_completion_broker"
            assert rag_components[1][0].name == "chroma_search"
            assert rag_components[2][0].name == "llm_request"
            assert rag_components[3][0].name == "send_response"
        finally:
            dispose_connector(connector)

    def test_data_ingestion_flow(self, yaml_path, env_vars, patch_dependencies):
        """Test the data ingestion flow."""
        mock_chromadb = patch_dependencies["chromadb"]

        connector, flows = create_test_flows(yaml_path)

        try:
            # Get the ingest flow
            ingest_flow = next(
                flow for flow in flows if flow["flow"].name == "chroma_ingest"
            )

            # Create test data
            test_data = (
                "This is a test document about artificial intelligence. "
                "AI is a branch of computer science that aims to create systems "
                "capable of performing tasks that typically require human intelligence."
            )

            # Send data to the flow
            message = Message(payload={"text": test_data})
            send_message_to_flow(ingest_flow["flow"], message)

            # Get response
            response = get_message_from_flow(ingest_flow["flow"])
            assert response is not None

            # Verify data was split and stored in ChromaDB
            collection = mock_chromadb.collections.get("rag", None)
            assert collection is not None
            assert len(collection["documents"]) > 0

            # Verify the text was split into chunks
            assert len(collection["documents"]) > 1
        finally:
            dispose_connector(connector)

    def test_text_splitting(self, yaml_path, env_vars, patch_dependencies):
        """Test the text splitting functionality."""
        connector, flows = create_test_flows(yaml_path)

        try:
            # Get the ingest flow
            ingest_flow = next(
                flow for flow in flows if flow["flow"].name == "chroma_ingest"
            )

            # Create a long test document
            long_text = " ".join(["word" + str(i) for i in range(100)])

            # Send data to the flow
            message = Message(payload={"text": long_text})
            send_message_to_flow(ingest_flow["flow"], message)

            # Get response
            response = get_message_from_flow(ingest_flow["flow"])
            assert response is not None

            # Verify the text was split into chunks
            # The config specifies chunk_size: 10, chunk_overlap: 1
            # So we expect multiple chunks with approximately 10 tokens each
            mock_chromadb = patch_dependencies["chromadb"]
            collection = mock_chromadb.collections.get("rag", None)

            # Verify we have multiple chunks
            assert len(collection["documents"]) > 1

            # Check that each chunk is approximately the right size
            for chunk in collection["documents"]:
                # Rough estimate: each "word" is one token
                tokens = len(chunk.split())
                # Allow some flexibility due to chunk_overlap
                assert tokens <= 15, f"Chunk too large: {tokens} tokens"
        finally:
            dispose_connector(connector)

    def test_rag_query_flow(self, yaml_path, env_vars, patch_dependencies):
        """Test the RAG query flow."""
        mock_chromadb = patch_dependencies["chromadb"]
        mock_openai = MagicMock()

        # Add some test documents to the mock ChromaDB
        mock_chromadb.get_or_create_collection("rag")
        mock_chromadb.add(
            [
                "Artificial intelligence is the simulation of human intelligence by machines.",
                "Machine learning is a subset of AI focused on learning from data.",
                "Deep learning uses neural networks with many layers.",
                "Natural language processing helps computers understand human language.",
                "Computer vision enables machines to interpret visual information.",
            ]
        )

        # Configure OpenAI mock response
        openai_response = MagicMock()
        openai_response.choices = [MagicMock()]
        openai_response.choices[0].message = MagicMock()
        openai_response.choices[0].message.content = (
            "AI is the simulation of human intelligence by machines."
        )

        # Patch OpenAI completion
        with patch("openai.ChatCompletion.create", return_value=openai_response):
            connector, flows = create_test_flows(yaml_path)

            try:
                # Get the RAG flow
                rag_flow = next(
                    flow for flow in flows if flow["flow"].name == "OpenAI_RAG"
                )

                # Create a query
                query = "What is artificial intelligence?"

                # Send query to the flow
                message = Message(payload={"query": query})
                send_message_to_flow(rag_flow["flow"], message)

                # Get response
                response = get_message_from_flow(rag_flow["flow"])
                assert response is not None

                # Verify response structure
                payload = response.get_data("previous:payload")
                assert "response" in payload
                assert "query" in payload
                assert "retrieved_data" in payload

                # Verify the response contains the expected content
                assert (
                    payload["response"]
                    == "AI is the simulation of human intelligence by machines."
                )
                assert payload["query"] == query

                # Verify retrieved data contains the relevant documents
                assert "Artificial intelligence" in str(payload["retrieved_data"])
            finally:
                dispose_connector(connector)

    def test_end_to_end_rag(self, yaml_path, env_vars, patch_dependencies):
        """Test the complete RAG pipeline."""
        mock_chromadb = patch_dependencies["chromadb"]

        # Configure OpenAI mock response
        openai_response = MagicMock()
        openai_response.choices = [MagicMock()]
        openai_response.choices[0].message = MagicMock()
        openai_response.choices[0].message.content = (
            "Based on the provided context, AI is the simulation of human intelligence by machines."
        )

        # Patch OpenAI completion
        with patch("openai.ChatCompletion.create", return_value=openai_response):
            connector, flows = create_test_flows(yaml_path)

            try:
                # Get both flows
                ingest_flow = next(
                    flow for flow in flows if flow["flow"].name == "chroma_ingest"
                )
                rag_flow = next(
                    flow for flow in flows if flow["flow"].name == "OpenAI_RAG"
                )

                # Step 1: Ingest data
                test_data = [
                    "Artificial intelligence is the simulation of human intelligence by machines.",
                    "Machine learning is a subset of AI focused on learning from data.",
                    "Deep learning uses neural networks with many layers.",
                    "Natural language processing helps computers understand human language.",
                    "Computer vision enables machines to interpret visual information.",
                ]

                for data in test_data:
                    message = Message(payload={"text": data})
                    send_message_to_flow(ingest_flow["flow"], message)
                    response = get_message_from_flow(ingest_flow["flow"])
                    assert response is not None

                # Step 2: Query the RAG system
                query = "What is artificial intelligence?"
                message = Message(payload={"query": query})
                send_message_to_flow(rag_flow["flow"], message)

                # Get response
                response = get_message_from_flow(rag_flow["flow"])
                assert response is not None

                # Verify response
                payload = response.get_data("previous:payload")
                assert (
                    payload["response"]
                    == "Based on the provided context, AI is the simulation of human intelligence by machines."
                )
                assert payload["query"] == query

                # Verify retrieved data contains the relevant documents
                assert "Artificial intelligence" in str(payload["retrieved_data"])
            finally:
                dispose_connector(connector)

    def test_error_handling_empty_retrieval(
        self, yaml_path, env_vars, patch_dependencies
    ):
        """Test error handling when no documents are retrieved."""
        mock_chromadb = patch_dependencies["chromadb"]

        # Configure ChromaDB to return empty results
        original_query = mock_chromadb.query
        mock_chromadb.query = lambda *args, **kwargs: {
            "documents": [],
            "metadatas": [],
            "distances": [],
            "ids": [],
        }

        # Configure OpenAI mock response
        openai_response = MagicMock()
        openai_response.choices = [MagicMock()]
        openai_response.choices[0].message = MagicMock()
        openai_response.choices[0].message.content = (
            "I cannot answer your query as there is no relevant information in the provided context."
        )

        # Patch OpenAI completion
        with patch("openai.ChatCompletion.create", return_value=openai_response):
            connector, flows = create_test_flows(yaml_path)

            try:
                # Get the RAG flow
                rag_flow = next(
                    flow for flow in flows if flow["flow"].name == "OpenAI_RAG"
                )

                # Create a query
                query = "What is quantum computing?"

                # Send query to the flow
                message = Message(payload={"query": query})
                send_message_to_flow(rag_flow["flow"], message)

                # Get response
                response = get_message_from_flow(rag_flow["flow"])
                assert response is not None

                # Verify response indicates no relevant information
                payload = response.get_data("previous:payload")
                assert "I cannot answer your query" in payload["response"]

                # Restore original query method
                mock_chromadb.query = original_query
            finally:
                dispose_connector(connector)

    def test_malformed_query_handling(self, yaml_path, env_vars, patch_dependencies):
        """Test handling of malformed queries."""
        connector, flows = create_test_flows(yaml_path)

        try:
            # Get the RAG flow
            rag_flow = next(flow for flow in flows if flow["flow"].name == "OpenAI_RAG")

            # Create a malformed query (missing the 'query' field)
            message = Message(payload={"text": "This is not a proper query"})

            # Send malformed query to the flow
            send_message_to_flow(rag_flow["flow"], message)

            # Check that an error was raised
            error_queue = rag_flow["flow"].error_queue
            assert not error_queue.empty()

            error_event = error_queue.get(timeout=5)
            error_message = error_event.data

            # Verify error details
            error_payload = error_message.get_payload()
            assert "error" in error_payload
        finally:
            dispose_connector(connector)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
