"""Mock implementation of LiteLLMBase for testing."""

from unittest.mock import MagicMock, patch
from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
from solace_ai_connector.common.log import log


class MockLiteLLMBase(LiteLLMBase):
    """Mock implementation of LiteLLMBase for testing."""

    def __init__(self, module_info, **kwargs):
        # Skip the parent __init__ to avoid actual initialization
        # We'll just set up the necessary attributes for testing
        self.module_info = module_info
        self.config = kwargs.get("config", {})
        self.component_config = self.config
        self.load_balancer_config = self.config.get("load_balancer", [])
        self.router = MagicMock()
        self._lock_stats = MagicMock()
        self.stats = {}
        self.timeout = self.config.get("timeout", 60)
        self.retry_policy_config = self.config.get("retry_policy", {})
        self.allowed_fails_policy_config = self.config.get("allowed_fails_policy", {})
        self.set_response_uuid_in_user_properties = self.config.get(
            "set_response_uuid_in_user_properties", False
        )

        # Call validate_model_config to perform validations
        self.validate_model_config(self.load_balancer_config)

    def get_config(self, key, default=None):
        """Get a configuration value."""
        return self.config.get(key, default)

    def validate_model_config(self, config):
        """Validate the model config and throw a descriptive error if it's invalid."""
        for model_entry in config:  # 'config' is the list from load_balancer
            params = model_entry.get("litellm_params", {})
            model_identifier = params.get("model")
            model_alias = model_entry.get("model_name", "Unknown Model Alias")

            if not model_identifier:
                raise ValueError(
                    f"Missing 'model' in 'litellm_params' for model alias '{model_alias}'."
                )

            if model_identifier.startswith("bedrock/"):
                # Bedrock-specific validation
                if "api_key" in params:
                    log.warning(
                        f"'api_key' found in 'litellm_params' for Bedrock model '{model_identifier}' (alias '{model_alias}'). "
                        f"This is typically not used for Bedrock; AWS credentials are used instead."
                    )

                has_explicit_aws_keys = (
                    "aws_access_key_id" in params and "aws_secret_access_key" in params
                )

                if has_explicit_aws_keys and not params.get("aws_region_name"):
                    log.warning(
                        f"'aws_region_name' not found in 'litellm_params' for Bedrock model '{model_identifier}' (alias '{model_alias}') "
                        f"when 'aws_access_key_id' and 'aws_secret_access_key' are provided. "
                        f"Consider adding 'aws_region_name' to 'litellm_params' or ensure it's set via AWS environment variables for Boto3."
                    )
                elif (
                    "aws_access_key_id" in params
                    and not "aws_secret_access_key" in params
                ):
                    raise ValueError(
                        f"If 'aws_access_key_id' is provided in 'litellm_params' for Bedrock model '{model_identifier}' (alias '{model_alias}'), "
                        f"'aws_secret_access_key' must also be provided."
                    )
                elif (
                    "aws_secret_access_key" in params
                    and not "aws_access_key_id" in params
                ):
                    raise ValueError(
                        f"If 'aws_secret_access_key' is provided in 'litellm_params' for Bedrock model '{model_identifier}' (alias '{model_alias}'), "
                        f"'aws_access_key_id' must also be provided."
                    )
            else:
                # Validation for other providers (e.g., OpenAI, Anthropic direct)
                if not params.get("api_key"):
                    raise ValueError(
                        f"Missing 'api_key' in 'litellm_params' for non-Bedrock model '{model_identifier}' (alias '{model_alias}')."
                    )

    def load_balance(self, messages, stream):
        """Mock load_balance method."""
        params = self.load_balancer_config[0].get("litellm_params", {})
        model = params["model"]

        # Call the router's completion method
        self.router.completion(
            model=self.load_balancer_config[0]["model_name"],
            messages=messages,
            stream=stream,
        )

        # Return a mock response
        return MagicMock()
