"""
LLM Factory - Creates LLM clients with fallback logic

Handles provider selection, fallback chains, and client configuration.
"""

import os
from typing import Optional, List
from dotenv import load_dotenv

from .llm_interface import LLMClient, LLMError
from .claude_client import ClaudeClient

# Load environment variables
load_dotenv()


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
        # Check environment for preferred provider
        preferred_provider = os.getenv("LLM_PROVIDER", "claude").lower()

        try:
            return LLMFactory.create_client(preferred_provider)
        except LLMError:
            # Fallback to Claude if preferred provider fails
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

        for provider in providers_to_try:
            try:
                client = LLMFactory.create_client(provider)
                if client.is_available():
                    return client
                else:
                    print(f"Provider {provider} not available, trying next...")
            except LLMError as e:
                print(f"Failed to create {provider} client: {e.message}")
                continue

        # If all fail, return the primary anyway and let it handle errors
        return LLMFactory.create_client(primary_provider)


# Convenience functions for easy usage
def get_llm_client(with_fallback: bool = True) -> LLMClient:
    """
    Get an LLM client (simple interface for the conversation system)

    Args:
        with_fallback: Whether to use fallback providers

    Returns:
        LLMClient: Ready-to-use LLM client
    """
    if with_fallback:
        # For POC, just Claude since it's the only one we have
        # In the future: add fallback_providers=["openai", "local"]
        return LLMFactory.create_client_with_fallback("claude", [])
    else:
        return LLMFactory.get_default_client()


def test_all_providers() -> dict:
    """
    Test all available providers and return status

    Returns:
        dict: Provider status information
    """
    results = {}

    # Test Claude
    try:
        claude = LLMFactory.create_client("claude")
        results["claude"] = {
            "available": claude.is_available(),
            "error": None
        }
    except Exception as e:
        results["claude"] = {
            "available": False,
            "error": str(e)
        }

    # Add other providers here when implemented

    return results
