"""
Highlights Generation - Extract conversation memory and user context

Analyzes completed conversations to extract structured facts and unstructured notes
that help personalize future conversations. Uses Claude API for extraction.
"""

import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
import logging

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, Conversation, Highlight, HighlightSchema
)
from api.llm_factory import get_llm_client
from api.llm_interface import LLMError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HighlightsExtractor:
    """Extracts conversation highlights using LLM analysis"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.llm_client = get_llm_client()
        # Note: We'll build the prompt dynamically to avoid format conflicts

    def _build_extraction_prompt(self, conversation_text: str) -> str:
        """Build the extraction prompt dynamically to avoid format conflicts"""

        field_descriptions = HighlightSchema.get_prompt_description()
        structured_template = json.dumps(HighlightSchema.get_extraction_template(), indent=8)

        prompt = f"""You are analyzing a health conversation to extract key user information that will help personalize future conversations.

Extract the following structured information if mentioned:

STRUCTURED FIELDS (return "null" if not mentioned):
{field_descriptions}

ALSO EXTRACT:
- unstructured_notes: Any other important context about this user that doesn't fit the structured fields

CONVERSATION TO ANALYZE:
{conversation_text}

Respond with a JSON object in this exact format:
{{
    "structured_data": {structured_template},
    "unstructured_notes": "Brief summary of other important user context and preferences"
}}

IMPORTANT: Only include information that was actually mentioned in the conversation. Use "null" for fields not discussed. Be specific and accurate."""

        return prompt

    def should_extract_highlights(self, conversation_id: int) -> bool:
        """
        Determine if highlights should be extracted from this conversation

        Returns True if:
        - No highlights exist for this conversation yet
        - Conversation has meaningful content (more than just greetings)
        - Conversation contains potentially extractable information
        """
        session = self.db_manager.get_session()

        try:
            # Check if highlights already exist
            existing_highlight = session.query(Highlight).filter(
                Highlight.conversation_id == conversation_id
            ).first()

            if existing_highlight:
                logger.info(f"Highlights already exist for conversation {conversation_id}")
                return False

            # Get the conversation
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation or not conversation.messages:
                return False

            # Check if conversation has meaningful content
            total_user_content = ""
            for message in conversation.messages:
                if message.get("role") == "user":
                    total_user_content += " " + message.get("content", "")

            # Skip very short conversations or greetings-only
            if len(total_user_content.strip()) < 20:
                logger.info(f"Conversation {conversation_id} too short for highlights extraction")
                return False

            # Skip if it's just basic greetings
            greeting_phrases = ["hi", "hello", "hey", "good morning", "good evening", "thanks", "thank you", "bye", "goodbye"]
            content_lower = total_user_content.lower().strip()

            # If the conversation is just greetings, skip
            words = content_lower.split()
            if len(words) <= 3 and any(phrase in content_lower for phrase in greeting_phrases):
                logger.info(f"Conversation {conversation_id} appears to be just greetings")
                return False

            return True

        finally:
            session.close()
    def extract_highlights_from_conversation(self, conversation_id: int) -> Optional[Dict]:
        """
        Extract highlights from a single conversation

        Args:
            conversation_id: ID of the conversation to analyze

        Returns:
            Dict with structured_data and unstructured_notes, or None if extraction fails
        """
        # First check if we should extract highlights
        if not self.should_extract_highlights(conversation_id):
            return None

        session = self.db_manager.get_session()

        try:
            # Get the conversation
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation or not conversation.messages:
                logger.warning(f"Conversation {conversation_id} not found or has no messages")
                return None

            # Format conversation for analysis
            conversation_text = self._format_conversation_for_analysis(conversation.messages)

            # Use LLM to extract highlights
            highlights = self._extract_with_llm(conversation_text)

            if highlights:
                logger.info(f"Successfully extracted highlights from conversation {conversation_id}")
                return highlights
            else:
                logger.warning(f"Failed to extract highlights from conversation {conversation_id}")
                return None

        except Exception as e:
            logger.error(f"Error extracting highlights from conversation {conversation_id}: {e}")
            return None
        finally:
            session.close()

    def _format_conversation_for_analysis(self, messages: List[Dict]) -> str:
        """Format conversation messages into readable text for LLM analysis"""
        formatted_lines = []

        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            timestamp = message.get("timestamp", "")

            # Clean up role names
            role_name = "User" if role == "user" else "Assistant"

            formatted_lines.append(f"{role_name}: {content}")

        return "\n\n".join(formatted_lines)

    def _extract_with_llm(self, conversation_text: str) -> Optional[Dict]:
        """Use LLM to extract structured highlights from conversation text"""
        try:
            # Build the extraction prompt
            prompt = self._build_extraction_prompt(conversation_text)

            # Call LLM
            response = self.llm_client.chat(
                user_message=prompt,
                system_prompt="You are a precise data extraction assistant. Always respond with valid JSON only.",
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000
            )

            # Parse JSON response
            try:
                # Clean the response - remove markdown formatting and extra whitespace
                cleaned_response = response.strip()

                # Remove common markdown JSON formatting
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]

                cleaned_response = cleaned_response.strip()

                # Parse JSON
                highlights = json.loads(cleaned_response)

                # Validate structure using schema
                if "structured_data" not in highlights or "unstructured_notes" not in highlights:
                    logger.error("LLM response missing required fields")
                    logger.error(f"Response keys: {list(highlights.keys())}")
                    return None

                # Validate structured data against schema
                try:
                    HighlightSchema.validate_structured_data(highlights["structured_data"])
                except ValueError as e:
                    logger.error(f"Structured data validation error: {e}")
                    return None

                # Clean up null values and empty strings
                structured_data = highlights["structured_data"]
                for key, value in structured_data.items():
                    if value == "null" or value == "" or value == "None":
                        structured_data[key] = None

                return highlights

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Cleaned response was: {cleaned_response}")
                logger.error(f"Original response was: {response}")
                return None

        except LLMError as e:
            logger.error(f"LLM error during highlight extraction: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during LLM extraction: {e}")
            return None

    def store_highlights(self, conversation_id: int, user_id: int, highlights: Dict) -> bool:
        """Store extracted highlights in the database"""
        session = self.db_manager.get_session()

        try:
            # Check if highlights already exist
            existing = session.query(Highlight).filter(
                Highlight.conversation_id == conversation_id
            ).first()

            if existing:
                # Update existing highlights
                existing.structured_data = highlights["structured_data"]
                existing.unstructured_notes = highlights["unstructured_notes"]
                existing.extracted_at = datetime.now(timezone.utc)
                logger.info(f"Updated existing highlights for conversation {conversation_id}")
            else:
                # Create new highlights
                highlight = Highlight(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    structured_data=highlights["structured_data"],
                    unstructured_notes=highlights["unstructured_notes"]
                )
                session.add(highlight)
                logger.info(f"Created new highlights for conversation {conversation_id}")

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing highlights for conversation {conversation_id}: {e}")
            return False
        finally:
            session.close()

    def process_conversation(self, conversation_id: int) -> bool:
        """
        Complete process: extract and store highlights for a conversation

        Args:
            conversation_id: ID of conversation to process

        Returns:
            bool: True if successful, False otherwise
        """
        session = self.db_manager.get_session()

        try:
            # Get conversation details
            conversation = session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation:
                logger.error(f"Conversation {conversation_id} not found")
                return False

            # Extract highlights
            highlights = self.extract_highlights_from_conversation(conversation_id)

            if not highlights:
                logger.warning(f"No highlights extracted for conversation {conversation_id}")
                return False

            # Store highlights
            success = self.store_highlights(conversation_id, conversation.user_id, highlights)

            if success:
                logger.info(f"Successfully processed conversation {conversation_id}")

            return success

        finally:
            session.close()

    def process_all_completed_conversations(self) -> Dict[str, int]:
        """
        Process all completed conversations that don't have highlights yet

        Returns:
            Dict with processing statistics
        """
        session = self.db_manager.get_session()
        results = {"processed": 0, "extracted": 0, "errors": 0, "skipped": 0}

        try:
            # Find completed conversations without highlights
            conversations_without_highlights = session.query(Conversation).filter(
                Conversation.status == "completed"
            ).outerjoin(Highlight).filter(Highlight.id.is_(None)).all()

            logger.info(f"Found {len(conversations_without_highlights)} conversations to process")

            for conversation in conversations_without_highlights:
                try:
                    success = self.process_conversation(conversation.id)

                    if success:
                        results["extracted"] += 1
                    else:
                        results["skipped"] += 1

                    results["processed"] += 1

                except Exception as e:
                    logger.error(f"Error processing conversation {conversation.id}: {e}")
                    results["errors"] += 1

            logger.info(f"Highlights processing complete: {results}")

        finally:
            session.close()

        return results

    def get_user_highlights_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get a consolidated summary of all highlights for a user

        Args:
            user_id: User ID to get highlights for

        Returns:
            Dict with consolidated user context
        """
        session = self.db_manager.get_session()

        try:
            # Get all highlights for user
            highlights = session.query(Highlight).filter(
                Highlight.user_id == user_id
            ).order_by(Highlight.extracted_at.desc()).all()

            if not highlights:
                return {"structured_data": {}, "unstructured_notes": "", "source_conversations": []}

            # Consolidate structured data (most recent non-null values take precedence)
            consolidated_structured = {}
            all_notes = []
            conversation_ids = []

            for highlight in highlights:
                conversation_ids.append(highlight.conversation_id)

                # Add unstructured notes
                if highlight.unstructured_notes and highlight.unstructured_notes.strip():
                    all_notes.append(highlight.unstructured_notes.strip())

                # Merge structured data (newer data overwrites older)
                if highlight.structured_data:
                    for key, value in highlight.structured_data.items():
                        if value is not None and key not in consolidated_structured:
                            consolidated_structured[key] = value

            # Combine unstructured notes
            combined_notes = " | ".join(all_notes) if all_notes else ""

            return {
                "structured_data": consolidated_structured,
                "unstructured_notes": combined_notes,
                "source_conversations": conversation_ids,
                "last_updated": highlights[0].extracted_at if highlights else None,
                "total_highlights": len(highlights)
            }

        finally:
            session.close()


def run_highlights_batch():
    """Main function to run highlights extraction batch job"""
    logger.info("Starting highlights batch processing...")

    extractor = HighlightsExtractor()
    results = extractor.process_all_completed_conversations()

    logger.info(f"Highlights batch complete: {results}")
    return results


if __name__ == "__main__":
    # Run the batch job
    run_highlights_batch()
