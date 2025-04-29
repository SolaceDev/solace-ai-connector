"""Shared fixtures and utilities for integration tests."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message


class MockMessagingService:
    """Mock messaging service for Solace broker."""

    def __init__(self):
        self.sent_messages = []
        self.message_queue = []
        self.subscriptions = {}

    def connect(self):
        """Mock connect method."""
        return True

    def disconnect(self):
        """Mock disconnect method."""
        return True

    def send_message(
        self, payload, destination_name, user_properties=None, user_context=None
    ):
        """Mock send_message method."""
        message = {
            "payload": payload,
            "topic": destination_name,
            "user_properties": user_properties or {},
        }
        self.sent_messages.append(message)

        # If there's a user_context with a callback, call it
        if user_context and "callback" in user_context:
            user_context["callback"](user_context)

        return True

    def receive_message(self, timeout_ms, queue_name):
        """Mock receive_message method."""
        if not self.message_queue:
            return None
        return self.message_queue.pop(0)

    def ack_message(self, message):
        """Mock ack_message method."""
        return True

    def get_connection_status(self):
        """Mock get_connection_status method."""
        return "connected"

    @property
    def messaging_service(self):
        """Mock messaging_service property."""
        return self

    def metrics(self):
        """Mock metrics method."""
        metrics_obj = MagicMock()
        metrics_obj.get_value = (
            lambda metric: len(self.sent_messages) if "sent" in str(metric) else 0
        )
        return metrics_obj


class MockLiteLLM:
    """Mock LiteLLM for testing."""

    def __init__(self, models=None):
        self.models = models or ["gpt-4o"]
        self.called_models = []
        self.responses = {}

        # Default response
        self.default_response = MagicMock()
        self.default_response.choices = [MagicMock()]
        self.default_response.choices[0].message = MagicMock()
        self.default_response.choices[0].message.content = "This is a mock response"

        # Default streaming response
        self.default_streaming_response = []
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = "This is a mock streaming response"
        self.default_streaming_response.append(chunk)

    def set_response(self, model, response, streaming=False):
        """Set a custom response for a specific model."""
        self.responses[(model, streaming)] = response

    def completion(self, model, messages, stream=False):
        """Mock completion method."""
        self.called_models.append(model)

        # Return custom response if set
        if (model, stream) in self.responses:
            return self.responses[(model, stream)]

        # Otherwise return default response
        if stream:
            return iter(self.default_streaming_response)
        return self.default_response


class MockChromaDB:
    """Mock ChromaDB for testing."""

    def __init__(self):
        self.collections = {}
        self.current_collection = None

    def get_or_create_collection(self, name):
        """Mock get_or_create_collection method."""
        if name not in self.collections:
            self.collections[name] = {
                "documents": [],
                "embeddings": [],
                "metadatas": [],
                "ids": [],
            }
        self.current_collection = name
        return self

    def add(self, documents, embeddings=None, metadatas=None, ids=None):
        """Mock add method."""
        collection = self.collections[self.current_collection]
        collection["documents"].extend(documents)

        # Generate fake embeddings if not provided
        if embeddings is None:
            embeddings = [[0.1] * 10 for _ in documents]
        collection["embeddings"].extend(embeddings)

        # Use empty metadata if not provided
        if metadatas is None:
            metadatas = [{} for _ in documents]
        collection["metadatas"].extend(metadatas)

        # Generate IDs if not provided
        if ids is None:
            start_id = len(collection["ids"])
            ids = [f"id-{i}" for i in range(start_id, start_id + len(documents))]
        collection["ids"].extend(ids)

    def query(self, query_embeddings, n_results=5):
        """Mock query method."""
        collection = self.collections[self.current_collection]

        # Return up to n_results documents
        n = min(n_results, len(collection["documents"]))

        return {
            "documents": collection["documents"][:n],
            "metadatas": collection["metadatas"][:n],
            "distances": [0.1 * i for i in range(n)],
            "ids": collection["ids"][:n],
        }


@pytest.fixture
def mock_messaging_service():
    """Fixture for mock messaging service."""
    return MockMessagingService()


@pytest.fixture
def mock_litellm():
    """Fixture for mock LiteLLM."""
    return MockLiteLLM()


@pytest.fixture
def mock_chromadb():
    """Fixture for mock ChromaDB."""
    return MockChromaDB()


@pytest.fixture
def patch_dependencies(mock_messaging_service, mock_litellm, mock_chromadb):
    """Patch dependencies for testing."""
    patches = []

    # Patch MessagingServiceBuilder
    messaging_builder_patch = patch(
        "solace_ai_connector.common.messaging.messaging_builder.MessagingServiceBuilder.build"
    )
    mock_builder = messaging_builder_patch.start()
    mock_builder.return_value = mock_messaging_service
    patches.append(messaging_builder_patch)

    # Patch litellm.Router
    litellm_router_patch = patch("litellm.Router")
    mock_router = litellm_router_patch.start()
    mock_router_instance = MagicMock()
    mock_router_instance.completion.side_effect = mock_litellm.completion
    mock_router.return_value = mock_router_instance
    patches.append(litellm_router_patch)

    # Patch Chroma client
    chroma_patch = patch("chromadb.Client")
    mock_chroma = chroma_patch.start()
    mock_chroma.return_value = mock_chromadb
    patches.append(chroma_patch)

    yield {
        "messaging_service": mock_messaging_service,
        "litellm": mock_litellm,
        "chromadb": mock_chromadb,
    }

    # Stop all patches
    for p in patches:
        p.stop()


def create_test_message(text):
    """Create a test message with the given text."""
    return Message(payload={"text": text})


def create_test_query_message(query):
    """Create a test query message for RAG."""
    return Message(payload={"query": query})


def create_test_data_message(text):
    """Create a test data message for RAG ingestion."""
    return Message(payload={"text": text})
