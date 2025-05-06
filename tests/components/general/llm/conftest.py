"""Pytest fixtures for LLM component tests."""

import sys
import os

# Add the project's 'src' directory to the Python path
# This allows finding the 'solace_ai_connector' module.
# Calculate path to 'src' relative to this conftest.py file.
# This conftest.py is at: tests/components/general/llm/conftest.py
# Project root is 4 levels up. src is then in project_root/src.
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", "..", "..", ".."))
_src_dir = os.path.join(_project_root, "src")

if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pytest
from unittest.mock import patch
from threading import Lock # Keep this import for fixtures if they create Locks directly

from solace_ai_connector.common.message import Message
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    litellm_info_base as litellm_base_module_info_dict,
)
from solace_ai_connector.common.monitoring import Metrics


@pytest.fixture
def mock_litellm_router_fixture(mocker):
    """Mocks litellm.Router to prevent actual Router instantiation."""
    # Patch where litellm.Router is looked up in the litellm_base module
    return mocker.patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router",
        autospec=True,
    )


@pytest.fixture
def litellm_base_module_info():
    """Provides the module_info dictionary for LiteLLMBase."""
    return litellm_base_module_info_dict.copy()


@pytest.fixture
def valid_load_balancer_config():
    """Provides a minimal valid load_balancer configuration."""
    return [
        {
            "model_name": "test-model",
            "litellm_params": {
                "model": "gpt-3.5-turbo",
                "api_key": "sk-fakekey",
                "base_url": "https://fake.api.com",
            },
        }
    ]


@pytest.fixture
def minimal_component_config(valid_load_balancer_config):
    """
    Provides a minimal config dictionary for LiteLLMBase instantiation,
    ensuring init_load_balancer can run without extensive mocking of its internals.
    """
    return {"load_balancer": valid_load_balancer_config}


@pytest.fixture
def mock_message_fixture():
    return Message(payload={"text": "hello"}, topic="test/topic")


# Example of how you might mock other litellm functions if needed elsewhere
# @pytest.fixture
# def mock_litellm_completion(mocker):
#     return mocker.patch("litellm.completion", autospec=True)

# @pytest.fixture
# def mock_litellm_embedding(mocker):
#     return mocker.patch("litellm.embedding", autospec=True)

# @pytest.fixture
# def mock_litellm_cost_per_token(mocker):
#     return mocker.patch(
#         "solace_ai_connector.components.general.llm.litellm.litellm_base.cost_per_token",
#         autospec=True
#     )

