"""
HighlightsExtractor - Extracts structured and unstructured context from conversations

Uses LLM to extract highlight fields defined in HighlightSchema.
Handles formatting, extraction, validation, and storage per conversation.
Batch orchestration has been moved to separate functions.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from memory.database import (
    get_db_session, Conversation, Highlight
)
from memory.highlight_schema import HighlightSchema
from llm_clients.llm_interface import LLMClient, LLMError
from llm_clients.llm_factory import get_llm_client
from utils.load_prompts import render_prompt

logger = logging.getLogger(__name__)


class HighlightsExtractor:
    """
    Extracts highlight data from a completed conversation using LLM
    and stores both structured and unstructured results.
    """

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or get_llm_client()

    def extract_highlights_from_conversation(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Main entry point for extracting highlights from messages.

        Args:
            messages: Full conversation history as list of role-content dicts

        Returns:
            A dictionary with structured and unstructured highlights
        """
        try:
            prompt = self._build_extraction_prompt(messages)
            raw_output = self._extract_with_llm(prompt)

            structured_data = None
            unstructured_notes = raw_output.strip()

            try:
                parsed_data = eval(unstructured_notes)
                if HighlightSchema.validate_structured_data(parsed_data):
                    structured_data = parsed_data
                    logger.debug("Structured data validated successfully")
            except Exception as e:
                logger.warning(f"Failed to validate or parse structured data: {e}")

            return {
                "structured_data": structured_data,
                "unstructured_notes": unstructured_notes
            }

        except LLMError as e:
            logger.error(f"LLM error during highlight extraction: {e}", exc_info=True)
            return {"structured_data": None, "unstructured_notes": ""}

    def _extract_with_llm(self, prompt: str) -> str:
        """Call LLM with prompt and return raw output"""
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(
            user_message=prompt,
            conversation_history=[],
            system_prompt="Extract structured user context from conversation"
        )
        return response.text

    def _build_extraction_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a prompt from the conversation and schema definition using a Jinja2 template
        """
        formatted = self._format_conversation_for_analysis(messages)
        schema_desc = HighlightSchema.get_prompt_description()
        template = HighlightSchema.get_extraction_template()

        return render_prompt("highlight_extraction", {
            "schema_description": schema_desc,
            "conversation_text": formatted,
            "extraction_template": template
        })

    @staticmethod
    def _format_conversation_for_analysis(messages: List[Dict[str, str]]) -> str:
        """Format messages into a readable chat transcript"""
        return "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages
        ])

    @staticmethod
    def store_highlights(user_id: int, conversation_id: int,
                         structured_data: Dict[str, Any], unstructured_notes: str):
        """
        Save extracted highlights to the database
        """
        session = get_db_session()
        try:
            highlight = Highlight(
                user_id=user_id,
                conversation_id=conversation_id,
                structured_data=structured_data,
                unstructured_notes=unstructured_notes,
                extracted_at=datetime.now(timezone.utc)
            )
            session.add(highlight)
            session.commit()
            logger.info(f"Highlights stored for user {user_id}, conversation {conversation_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store highlights: {e}", exc_info=True)
        finally:
            session.close()

    def process_conversation(self, conversation_id: int) -> bool:
        """
        Load a conversation by ID, run extraction, and store results

        Returns:
            True if highlights were extracted and stored
        """
        session = get_db_session()
        try:
            conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conversation or conversation.status != "completed":
                logger.warning(f"Conversation {conversation_id} not found or not completed")
                return False

            messages = conversation.messages or []
            if not messages:
                logger.warning(f"Conversation {conversation_id} has no messages")
                return False

            result = self.extract_highlights_from_conversation(messages)
            self.store_highlights(conversation.user_id, conversation.id,
                                  result["structured_data"], result["unstructured_notes"])
            return True

        except Exception as e:
            logger.error(f"Failed to process conversation {conversation_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()

    @staticmethod
    def get_user_highlights_summary(user_id: int) -> Dict[str, Any]:
        """Fetch latest highlight summary for a given user"""
        session = get_db_session()
        try:
            highlight = session.query(Highlight).filter(Highlight.user_id == user_id).order_by(
                Highlight.extracted_at.desc()
            ).first()

            if not highlight:
                return {"structured": {}, "notes": ""}

            return {
                "structured": highlight.structured_data or {},
                "notes": highlight.unstructured_notes or ""
            }

        finally:
            session.close()


# Batch processing logic moved to runner functions

def process_all_completed_conversations() -> Dict[str, int]:
    """
    Batch process all completed conversations without highlights
    """
    session = get_db_session()
    extractor = HighlightsExtractor()
    results = {"processed": 0, "extracted": 0, "errors": 0, "skipped": 0}

    try:
        conversations = session.query(Conversation).filter(
            Conversation.status == "completed"
        ).outerjoin(Highlight).filter(Highlight.id.is_(None)).all()

        logger.info(f"Found {len(conversations)} conversations to process")

        for conversation in conversations:
            try:
                success = extractor.process_conversation(conversation.id)

                if success:
                    results["extracted"] += 1
                else:
                    results["skipped"] += 1

                results["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing conversation {conversation.id}: {e}", exc_info=True)
                results["errors"] += 1

        logger.info(f"Highlights processing complete: {results}")
        return results

    finally:
        session.close()


def run_highlights_batch():
    """
    Main function to run highlights extraction batch job
    """
    logger.info("Starting highlights batch processing...")
    results = process_all_completed_conversations()
    logger.info(f"Highlights batch complete: {results}")
    return results


if __name__ == "__main__":
    run_highlights_batch()
