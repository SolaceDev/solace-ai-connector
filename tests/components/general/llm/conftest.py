"""Pytest fixtures for LLM component tests."""

import sys
import os

# Add the project's 'src' directory to the Python path
# This allows finding the 'solace_ai_connector' module.
# This assumes pytest is run from the project root directory.
# For a more robust path, you could calculate it relative to this file's location,
# but 'sys.path.append("src")' is a common pattern if the CWD is the project root.
# Example of a more robust way (if needed later):
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
# src_dir = os.path.join(project_root, "src")
# if src_dir not in sys.path:
#    sys.path.insert(0, src_dir)

# Simple approach, consistent with other test files like tests/test_flows.py:
if os.path.join(os.getcwd(), "src") not in sys.path and "src" not in sys.path:
    # Check if 'src' is directly accessible (e.g. running from project root)
    if os.path.isdir("src"):
        sys.path.insert(0, "src")
    else:
        # Fallback for deeper execution paths: try to find project root
        # This conftest is at tests/components/general/llm/conftest.py
        # Project root is four levels up from this file's directory.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_marker = "pyproject.toml" # A file that typically exists at the project root
        
        # Traverse up to find the project root (where pyproject.toml is)
        path_to_check = current_dir
        found_root = False
        for _ in range(5): # Limit search depth
            if os.path.exists(os.path.join(path_to_check, project_root_marker)):
                project_root = path_to_check
                src_dir_abs = os.path.join(project_root, "src")
                if os.path.isdir(src_dir_abs) and src_dir_abs not in sys.path:
                    sys.path.insert(0, src_dir_abs)
                found_root = True
                break
            parent_dir = os.path.dirname(path_to_check)
            if parent_dir == path_to_check: # Reached filesystem root
                break
            path_to_check = parent_dir
        
        if not found_root:
            # If specific project root marker not found, fall back to simpler relative path
            # This assumes conftest.py is at tests/components/general/llm/conftest.py
            # and src is at ../../../../src from this file's location.
            # This is less robust than finding a marker file.
            # For now, let's stick to the simpler "src" append if running from root,
            # and rely on hatch to set up paths correctly.
            # The initial simple 'sys.path.insert(0, "src")' if os.path.isdir("src")
            # should cover the common case of running pytest from project root.
            # If that doesn't work, the hatch environment setup is the primary fix.
            pass


import pytest
from unittest.mock import patch
from threading import Lock

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

