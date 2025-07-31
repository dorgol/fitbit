"""
LLM Factory - Creates LLM clients with fallback logic

Handles provider selection, fallback chains, and client configuration.
"""

import os
import logging
from typing import Optional, List
from dotenv import load_dotenv

from .llm_interface import LLMClient, LLMError
from .claude_client import ClaudeClient

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM clients with fallback support"""

    @staticmethod
    def create_client(provider: str = "claude", **kwargs) -> LLMClient:
        """
        Create a single LLM client

        Args:
            provider: LLM provider name ("claude", "openai", etc.)
            **kwargs: Provider-specific configuration

        Returns:
            LLMClient: Configured LLM client

        Raises:
            LLMError: If provider is unknown or can't be created
        """
        provider = provider.lower()

        logger.debug(f"Attempting to create LLM client for provider: {provider}")

        if provider == "claude":
            return ClaudeClient(**kwargs)
        # elif provider == "openai":
        #     return OpenAIClient(**kwargs)  # Future implementation
        # elif provider == "local":
        #     return LocalLLMClient(**kwargs)  # Future implementation
        else:
            raise LLMError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def get_default_client() -> LLMClient:
        """
        Get the default LLM client based on environment configuration

        Returns:
            LLMClient: Default configured client
        """
        preferred_provider = os.getenv("LLM_PROVIDER", "claude").lower()
        logger.info(f"Preferred provider from environment: {preferred_provider}")

        try:
            return LLMFactory.create_client(preferred_provider)
        except LLMError as e:
            logger.warning(f"Failed to create preferred provider '{preferred_provider}': {e.message}. Falling back to Claude.")
            return LLMFactory.create_client("claude")

    @staticmethod
    def create_client_with_fallback(
        primary_provider: str = "claude",
        fallback_providers: Optional[List[str]] = None
    ) -> LLMClient:
        """
        Create LLM client with built-in fallback logic

        Args:
            primary_provider: Primary provider to try first
            fallback_providers: List of fallback providers

        Returns:
            LLMClient: Client that handles fallback automatically
        """
        providers_to_try = [primary_provider] + (fallback_providers or [])
        logger.info(f"Trying providers in order: {providers_to_try}")

        for provider in providers_to_try:
            try:
                client = LLMFactory.create_client(provider)
                if client.is_available():
                    logger.info(f"Using available provider: {provider}")
                    return client
                else:
                    logger.warning(f"Provider {provider} is not available, trying next...")
            except LLMError as e:
                logger.error(f"Failed to create client for provider {provider}: {e.message}", exc_info=True)

        logger.warning("All fallback providers failed. Returning primary client and letting it handle errors.")
        return LLMFactory.create_client(primary_provider)


# Convenience functions
def get_llm_client(with_fallback: bool = True) -> LLMClient:
    """
    Get an LLM client (simple interface for the conversation system)

    Args:
        with_fallback: Whether to use fallback providers

    Returns:
        LLMClient: Ready-to-use LLM client
    """
    return (
        LLMFactory.create_client_with_fallback("claude", [])
        if with_fallback
        else LLMFactory.get_default_client()
    )


def test_all_providers() -> dict:
    """
    Test all available providers and return status

    Returns:
        dict: Provider status information
    """
    results = {}
    providers = ["claude"]  # Add more as implemented

    for provider in providers:
        try:
            client = LLMFactory.create_client(provider)
            available = client.is_available()
            results[provider] = {"available": available, "error": None}
        except Exception as e:
            results[provider] = {"available": False, "error": str(e)}
            logger.error(f"Provider check failed for {provider}", exc_info=True)

    return results
