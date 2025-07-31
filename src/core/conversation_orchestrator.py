"""
Conversation Orchestrator - Complete LangGraph-based conversation management

Handles the main conversation flow using LangGraph state management and workflows.
Integrates with the complete context assembly system.
"""

import sys
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from datetime import datetime, timezone
import logging

# Add src to path for imports
sys.path.append('src')

from api.llm_factory import get_llm_client
from api.llm_interface import LLMError
from core.context_assembly import ContextAssembler
from memory.database import DatabaseManager, User, Conversation, get_db_session
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State structure for the LangGraph conversation workflow"""
    user_id: str
    user_message: str
    conversation_history: List[Dict[str, str]]
    conversation_id: Optional[str]
    assembled_context: Dict[str, Any]
    system_prompt: str
    response: str
    error: Optional[str]
    should_update_memory: bool


class ConversationOrchestrator:
    """
    Main conversation orchestrator using LangGraph workflows with full context assembly
    """

    def __init__(self):
        """Initialize the conversation orchestrator"""
        self.llm_client = get_llm_client()
        self.context_assembler = ContextAssembler()
        self.db_manager = DatabaseManager()
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> Any:
        """Build the complete LangGraph conversation workflow"""

        # Define the workflow graph
        workflow = StateGraph(ConversationState)

        # Add nodes for each step
        workflow.add_node("load_context", self._load_full_context)
        workflow.add_node("build_system_prompt", self._build_system_prompt)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("update_conversation", self._update_conversation)
        workflow.add_node("trigger_highlights", self._trigger_highlights_extraction)

        # Define the workflow flow
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "build_system_prompt")
        workflow.add_edge("build_system_prompt", "generate_response")
        workflow.add_edge("generate_response", "update_conversation")
        workflow.add_edge("update_conversation", "trigger_highlights")
        workflow.add_edge("trigger_highlights", END)

        return workflow.compile()

    def _load_full_context(self, state: ConversationState) -> ConversationState:
        """
        Load and assemble context from all 6 memory layers using ContextAssembler
        """
        user_id = int(state["user_id"])

        try:
            logger.info(f"Loading full context for user {user_id}")

            # Use the context assembler to get all data
            context_result = self.context_assembler.get_conversation_context(user_id)

            state["assembled_context"] = context_result["context"]

            logger.info(f"Successfully loaded context for user {user_id}")
            logger.debug(f"Context keys: {list(context_result['context'].keys())}")

        except Exception as e:
            logger.error(f"Error loading context for user {user_id}: {e}")
            state["error"] = f"Failed to load user context: {str(e)}"
            # Provide minimal fallback context
            state["assembled_context"] = {
                "user_id": user_id,
                "raw_data": {},
                "insights": [],
                "highlights": {},
                "external_data": {},
                "knowledge": [],
                "user_preferences": {}
            }

        return state

    def _build_system_prompt(self, state: ConversationState) -> ConversationState:
        """
        Build the complete system prompt using the modular context assembly
        """
        try:
            logger.info("Building system prompt from assembled context")

            # Use context assembler to build the prompt
            context = state["assembled_context"]
            system_prompt = self.context_assembler.build_system_prompt(context)

            state["system_prompt"] = system_prompt

            logger.info(f"Built system prompt ({len(system_prompt)} characters)")
            logger.debug(f"System prompt preview: {system_prompt[:200]}...")

        except Exception as e:
            logger.error(f"Error building system prompt: {e}")
            state["error"] = f"Failed to build system prompt: {str(e)}"
            # Fallback to basic prompt
            state["system_prompt"] = """You are a helpful health assistant for Fitbit users. 
            Provide encouraging, data-driven advice based on the user's health information."""

        return state

    def _generate_response(self, state: ConversationState) -> ConversationState:
        """
        Generate response using the LLM with full context
        """
        try:
            logger.info("Generating LLM response")

            response = self.llm_client.chat(
                user_message=state["user_message"],
                conversation_history=state["conversation_history"],
                system_prompt=state["system_prompt"],
                temperature=0.7,  # Slightly creative but consistent
                max_tokens=1000
            )

            state["response"] = response
            state["error"] = None

            logger.info(f"Generated response ({len(response)} characters)")
            logger.debug(f"Response preview: {response[:100]}...")

        except LLMError as e:
            logger.error(f"LLM error during response generation: {e}")
            state["response"] = "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment."
            state["error"] = str(e)
        except Exception as e:
            logger.error(f"Unexpected error during response generation: {e}")
            state["response"] = "I apologize, but I encountered an unexpected error. Please try again."
            state["error"] = str(e)

        return state

    def _update_conversation(self, state: ConversationState) -> ConversationState:
        """
        Update conversation history in database
        """
        try:
            logger.info("Updating conversation in database")

            user_id = int(state["user_id"])
            session = self.db_manager.get_session()

            try:
                # Get or create active conversation
                conversation_id = state.get("conversation_id")

                if conversation_id:
                    # Update existing conversation
                    conversation = session.query(Conversation).filter(
                        Conversation.id == conversation_id
                    ).first()
                else:
                    # Create new conversation or get active one
                    active_conversation = session.query(Conversation).filter(
                        Conversation.user_id == user_id,
                        Conversation.status == "active"
                    ).first()

                    if active_conversation:
                        conversation = active_conversation
                    else:
                        # Create new conversation
                        conversation = Conversation(
                            user_id=user_id,
                            session_id=uuid.uuid4(),
                            messages=[],
                            status="active"
                        )
                        session.add(conversation)
                        session.flush()  # Get ID

                # Update messages
                if not conversation.messages:
                    conversation.messages = []

                # Add user message
                conversation.messages.append({
                    "role": "user",
                    "content": state["user_message"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Add assistant response
                conversation.messages.append({
                    "role": "assistant",
                    "content": state["response"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                session.commit()

                # Update state with conversation ID
                state["conversation_id"] = str(conversation.id)
                state["should_update_memory"] = True

                logger.info(f"Updated conversation {conversation.id}")

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error updating conversation: {e}")
            state["error"] = f"Failed to save conversation: {str(e)}"
            state["should_update_memory"] = False

        return state

    def _trigger_highlights_extraction(self, state: ConversationState) -> ConversationState:
        """
        Trigger highlights extraction after each conversation turn

        This extracts learnings from every interaction to build user context
        """
        try:
            if not state.get("should_update_memory", False):
                return state

            conversation_id = state.get("conversation_id")
            if not conversation_id:
                return state

            logger.info(f"Triggering highlights extraction for conversation {conversation_id}")

            # Import here to avoid circular imports
            from memory.highlights import HighlightsExtractor

            extractor = HighlightsExtractor()

            # Run extraction after each conversation turn (non-blocking)
            try:
                # Extract highlights from the current conversation
                success = extractor.process_conversation(int(conversation_id))

                if success:
                    logger.info(f"Successfully extracted highlights from conversation {conversation_id}")
                else:
                    logger.info(f"No new highlights extracted from conversation {conversation_id}")

            except Exception as e:
                logger.warning(f"Background highlights extraction failed for conversation {conversation_id}: {e}")
                # Don't fail the whole conversation for highlights extraction issues

        except Exception as e:
            logger.warning(f"Error in highlights extraction trigger: {e}")
            # Don't fail the conversation for highlights extraction issues

        return state

    def chat(self, user_id: str, user_message: str,
             conversation_id: Optional[str] = None,
             conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Main entry point for conversation

        Args:
            user_id: Unique identifier for the user
            user_message: The user's current message
            conversation_id: Optional existing conversation ID
            conversation_history: Optional previous conversation messages

        Returns:
            Dict with response and metadata
        """
        logger.info(f"Starting conversation for user {user_id}")

        # Initialize state
        initial_state = ConversationState(
            user_id=user_id,
            user_message=user_message,
            conversation_history=conversation_history or [],
            conversation_id=conversation_id,
            assembled_context={},
            system_prompt="",
            response="",
            error=None,
            should_update_memory=False
        )

        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)

            # Return the response with metadata
            result = {
                "response": final_state["response"],
                "conversation_id": final_state.get("conversation_id"),
                "error": final_state.get("error"),
                "user_id": user_id
            }

            logger.info(f"Conversation completed for user {user_id}")
            return result

        except Exception as e:
            logger.error(f"Workflow execution failed for user {user_id}: {e}")
            return {
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again.",
                "conversation_id": conversation_id,
                "error": str(e),
                "user_id": user_id
            }

    def end_conversation(self, conversation_id: str) -> bool:
        """
        Mark a conversation as completed and trigger final highlights extraction
        """
        try:
            session = self.db_manager.get_session()

            try:
                conversation = session.query(Conversation).filter(
                    Conversation.id == int(conversation_id)
                ).first()

                if conversation:
                    conversation.status = "completed"
                    conversation.ended_at = datetime.now(timezone.utc)
                    session.commit()

                    logger.info(f"Conversation {conversation_id} marked as completed")

                    # Trigger final highlights extraction
                    from memory.highlights import HighlightsExtractor
                    extractor = HighlightsExtractor()
                    extractor.process_conversation(conversation.id)

                    return True
                else:
                    logger.warning(f"Conversation {conversation_id} not found")
                    return False

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error ending conversation {conversation_id}: {e}")
            return False

    def is_available(self) -> bool:
        """Check if the orchestrator is ready to handle conversations"""
        return self.llm_client.is_available()


# Convenience functions for easy usage
def create_conversation_orchestrator() -> ConversationOrchestrator:
    """Create and return a conversation orchestrator instance"""
    return ConversationOrchestrator()


def chat_with_user(user_id: str, message: str, conversation_id: str = None) -> Dict[str, Any]:
    """Simple function for chatting with a user - main entry point for frontend"""
    orchestrator = create_conversation_orchestrator()
    return orchestrator.chat(user_id, message, conversation_id)


if __name__ == "__main__":
    # Test the conversation orchestrator
    print("=== TESTING CONVERSATION ORCHESTRATOR ===")

    session = get_db_session()
    try:
        user = session.query(User).first()
        if user:
            print(f"Testing conversation with user {user.id}")

            # Test multiple conversation types
            test_questions = [
                "Should I exercise outside today?",
                "What's a good time to go for a walk?",
                "How did I sleep last night?",
                "I'm thinking about going for a run"
            ]

            for question in test_questions:
                print(f"\n--- Testing: '{question}' ---")
                result = chat_with_user(str(user.id), question)

                print(f"Response: {result['response']}")
                print(f"Conversation ID: {result['conversation_id']}")
                if result['error']:
                    print(f"Error: {result['error']}")
                print()

        else:
            print("No users found in database")
    finally:
        session.close()
