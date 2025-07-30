"""
LLM Interface - Abstract base class for all LLM providers

This interface provides a clean abstraction for different LLM providers
(Claude, OpenAI, local models, etc.) so the conversation system can
work with any provider without knowing implementation details.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMClient(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def chat(
            self,
            user_message: str,
            conversation_history: Optional[List[Dict[str, str]]] = None,
            system_prompt: Optional[str] = None,
            **kwargs
    ) -> str:
        """
        Main conversational method

        Args:
            user_message: The user's current message
            conversation_history: List of previous messages in format:
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            system_prompt: Optional system prompt to override default
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            str: The LLM's response message

        Raises:
            LLMError: If the API call fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Quick health check to see if this provider is accessible

        Returns:
            bool: True if provider is available, False otherwise
        """
        pass


class LLMError(Exception):
    """Base exception for LLM-related errors"""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)


class LLMUnavailableError(LLMError):
    """Raised when an LLM provider is temporarily unavailable"""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limits are exceeded"""
    pass