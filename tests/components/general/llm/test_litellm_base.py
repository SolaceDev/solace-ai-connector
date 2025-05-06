"""Unit tests for LiteLLMBase."""

import pytest
from unittest.mock import patch, MagicMock
import threading # Changed from 'from threading import Lock'

from litellm.exceptions import APIConnectionError
from solace_ai_connector.common.message import Message_NACK_Outcome
from solace_ai_connector.common.monitoring import Metrics
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    LiteLLMBase,
    litellm_info_base,
)


class TestLiteLLMBaseInitialization:
    """Tests for the __init__ method of LiteLLMBase."""

    def test_initialization_with_defaults_and_minimal_config(
        self,
        litellm_base_module_info,
        minimal_component_config,
        mock_litellm_router_fixture,
    ):
        """
        Tests that LiteLLMBase initializes correctly with default values from
        module_info when only a minimal valid config (for load_balancer) is provided.
        """
        component = LiteLLMBase(
            module_info=litellm_base_module_info, config=minimal_component_config
        )

        # Check config values (defaults from litellm_info_base or None)
        assert component.timeout == litellm_info_base["config_parameters"][4]["default"]  # Default: 60
        assert component.retry_policy_config is None  # No default in module_info
        assert component.allowed_fails_policy_config is None  # No default in module_info
        assert (
            component.load_balancer_config
            == minimal_component_config["load_balancer"]
        )
        assert component.set_response_uuid_in_user_properties == litellm_info_base[
            "config_parameters"
        ][3][
            "default"
        ]  # Default: False

        # Check stats initialization
        expected_stats_keys = {
            Metrics.LITELLM_STATS_PROMPT_TOKENS,
            Metrics.LITELLM_STATS_RESPONSE_TOKENS,
            Metrics.LITELLM_STATS_TOTAL_TOKENS,
            Metrics.LITELLM_STATS_RESPONSE_TIME,
            Metrics.LITELLM_STATS_COST,
        }
        assert set(component.stats.keys()) == expected_stats_keys
        for key in expected_stats_keys:
            assert component.stats[key] == []

        # Check lock initialization
        assert isinstance(component._lock_stats, threading.Lock) # Changed to threading.Lock

        # Check that init_load_balancer was called (implicitly, router mock is called)
        mock_litellm_router_fixture.assert_called_once()
        assert component.router is mock_litellm_router_fixture.return_value

    def test_initialization_with_custom_config(
        self,
        litellm_base_module_info,
        valid_load_balancer_config,
        mock_litellm_router_fixture,
    ):
        """
        Tests that LiteLLMBase initializes correctly with custom configuration values.
        """
        custom_config = {
            "timeout": 30,
            "retry_policy": {"RateLimitErrorRetries": 5},
            "allowed_fails_policy": {"BadRequestErrorAllowedFails": 2},
            "load_balancer": valid_load_balancer_config,
            "set_response_uuid_in_user_properties": True,
        }
        component = LiteLLMBase(
            module_info=litellm_base_module_info, config=custom_config
        )

        assert component.timeout == custom_config["timeout"]
        assert component.retry_policy_config == custom_config["retry_policy"]
        assert (
            component.allowed_fails_policy_config
            == custom_config["allowed_fails_policy"]
        )
        assert component.load_balancer_config == custom_config["load_balancer"]
        assert (
            component.set_response_uuid_in_user_properties
            == custom_config["set_response_uuid_in_user_properties"]
        )

        # Stats and lock should still be initialized
        assert isinstance(component.stats, dict)
        assert isinstance(component._lock_stats, threading.Lock) # Changed to threading.Lock
        mock_litellm_router_fixture.assert_called_once()

    @patch.object(
        LiteLLMBase, "init_load_balancer", MagicMock()
    )  # Mock to isolate __init__
    def test_stats_initialization_structure(self, litellm_base_module_info):
        """
        Tests the detailed structure of the initialized stats dictionary.
        """
        # We pass an empty config because init_load_balancer is mocked,
        # so it won't try to validate the load_balancer config.
        component = LiteLLMBase(module_info=litellm_base_module_info, config={})

        assert isinstance(component.stats, dict)
        assert component.stats == {
            Metrics.LITELLM_STATS_PROMPT_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TOKENS: [],
            Metrics.LITELLM_STATS_TOTAL_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TIME: [],
            Metrics.LITELLM_STATS_COST: [],
        }

    @patch.object(
        LiteLLMBase, "init_load_balancer", MagicMock()
    )  # Mock to isolate __init__
    def test_lock_initialization_type(self, litellm_base_module_info):
        """
        Tests that _lock_stats is initialized as a threading.Lock instance.
        """
        component = LiteLLMBase(module_info=litellm_base_module_info, config={})
        assert isinstance(component._lock_stats, threading.Lock) # Changed to threading.Lock

    def test_initialization_calls_init_and_init_load_balancer(
        self, litellm_base_module_info, minimal_component_config
    ):
        """
        Tests that __init__ calls both init() and init_load_balancer().
        """
        with patch.object(
            LiteLLMBase, "init", wraps=LiteLLMBase.init, autospec=True # Added autospec=True
        ) as mock_init, patch.object(
            LiteLLMBase, "init_load_balancer", wraps=LiteLLMBase.init_load_balancer, autospec=True # Added autospec=True
        ) as mock_init_load_balancer, patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):  # Mock router to let init_load_balancer run
            LiteLLMBase(
                module_info=litellm_base_module_info, config=minimal_component_config
            )
            mock_init.assert_called_once()
            mock_init_load_balancer.assert_called_once()

# Placeholder for other LiteLLMBase tests (e.g., init_load_balancer, validate_model_config)
# Refer to testing_plan_llm_components.md for detailed test cases.
