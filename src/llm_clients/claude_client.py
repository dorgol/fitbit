"""
Claude API Client - Implementation of LLM interface for Anthropic's Claude

Handles all Claude-specific API calls and converts them to our standard interface.
"""

import os
import time
from typing import List, Dict, Optional
import anthropic
from anthropic import APIError, RateLimitError, APIConnectionError

from .llm_interface import LLMClient, LLMError, LLMUnavailableError, LLMRateLimitError, LLMResponse


class ClaudeClient(LLMClient):
    """Claude implementation of the LLM interface"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude client

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use
        """
        super().__init__()
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise LLMError("No API key provided. Set ANTHROPIC_API_KEY environment variable.", "claude")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Send a message to Claude and get response

        Args:
            user_message: The user's current message
            conversation_history: Previous conversation messages
            system_prompt: System prompt to set context
            **kwargs: Claude-specific parameters (temperature, max_tokens, etc.)

        Returns:
            str: Claude's response

        Raises:
            LLMError: If the request fails
        """
        start = time.time()

        try:
            messages = conversation_history or []
            messages.append({"role": "user", "content": user_message})

            api_params = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 1000),
                "messages": messages,
            }

            if system_prompt:
                api_params["system"] = system_prompt

            if "temperature" in kwargs:
                api_params["temperature"] = kwargs["temperature"]

            self.logger.debug("Sending request to Claude", extra={
                "model": self.model,
                "prompt_length": len(user_message),
                "conversation_turns": len(messages)
            })

            response = self.client.messages.create(**api_params)

            duration = time.time() - start
            content = response.content[0].text if response.content else ""

            self.logger.info("Received response from Claude", extra={
                "duration_sec": round(duration, 3),
                "response_snippet": content[:100]  # trim for log size
            })

            if response.content and len(response.content) > 0:
                return LLMResponse(
                    text=response.content[0].text,
                    duration_ms=duration,
                    model=self.model
                )
            else:
                raise LLMError("Empty response from Claude", "claude")

        except RateLimitError as e:
            self.logger.warning("Claude rate limit hit", exc_info=True)
            raise LLMRateLimitError("Claude rate limit exceeded", "claude", e)

        except APIConnectionError as e:
            self.logger.error("Claude API connection failed", exc_info=True)
            raise LLMUnavailableError("Cannot connect to Claude API", "claude", e)

        except APIError as e:
            self.logger.error("Claude API error", exc_info=True)
            raise LLMError(f"Claude API error: {str(e)}", "claude", e)

        except Exception as e:
            self.logger.exception("Unexpected Claude client error")
            raise LLMError(f"Unexpected error with Claude: {str(e)}", "claude", e)

    def is_available(self) -> bool:
        """
        Test if Claude API is accessible

        Returns:
            bool: True if available, False otherwise
        """
        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            self.logger.warning("Claude availability check failed", exc_info=True)
            return False

    def __str__(self):
        return f"ClaudeClient(model={self.model})"
