"""
LLM Interface - Abstract base class for all LLM providers

This interface provides a clean abstraction for different LLM providers
(Claude, OpenAI, local models, etc.) so the conversation system can
work with any provider without knowing implementation details.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    duration_ms: Optional[float] = None
    model: Optional[str] = None


class LLMClient(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Main conversational method

        Args:
            user_message: The user's current message
            conversation_history: List of previous messages in format:
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            system_prompt: Optional system prompt to guide behavior
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            str: The LLM's response

        Raises:
            LLMError: If the provider fails to respond
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Lightweight health check for provider availability

        Returns:
            bool: True if the provider is reachable and functional
        """
        pass


class LLMError(Exception):
    """Base exception for LLM-related issues"""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)


class LLMUnavailableError(LLMError):
    """Raised when the LLM provider is unreachable (e.g., network issues)"""
    pass


class LLMRateLimitError(LLMError):
    """Raised when the LLM provider returns a rate limit error"""
    pass
