"""
Conversation Orchestrator - LangGraph-based multi-turn loop with stop criteria

Now supports internal looping through messages using LangGraph conditional edges.
Conversation ends after 5 turns or if user says "bye" (case-insensitive).
"""

import sys
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
import logging
import uuid

# Add src to path for imports
sys.path.append('src')

from llm_clients.llm_factory import get_llm_client
from llm_clients.llm_interface import LLMError
from core.context_assembly import ContextAssembler
from memory.database import DatabaseManager, User, Conversation, get_db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    user_id: str
    user_message: str
    messages: List[Dict[str, str]]
    conversation_id: Optional[str]
    assembled_context: Dict[str, Any]
    system_prompt: str
    response: str
    error: Optional[str]
    should_update_memory: bool
    stop_conversation: bool
    context_loaded: bool
    __next__: Optional[str]


class ConversationOrchestrator:
    def __init__(self):
        self.llm_client = get_llm_client()
        self.context_assembler = ContextAssembler()
        self.db_manager = DatabaseManager()
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        graph = StateGraph(ConversationState)

        graph.add_node("load_context", self._load_full_context)
        graph.add_node("build_system_prompt", self._build_system_prompt)
        graph.add_node("generate_response", self._generate_response)
        graph.add_node("update_conversation", self._update_conversation)
        graph.add_node("check_should_continue", self._check_should_continue)
        graph.add_node("trigger_highlights", self._trigger_highlights_extraction)

        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "build_system_prompt")
        graph.add_edge("build_system_prompt", "generate_response")
        graph.add_edge("generate_response", "update_conversation")
        graph.add_edge("update_conversation", "check_should_continue")

        graph.add_conditional_edges("check_should_continue", {
            "continue": self._load_full_context,
            "stop": self._trigger_highlights_extraction
        })

        graph.add_edge("trigger_highlights", END)

        return graph.compile()

    def _load_full_context(self, state: ConversationState) -> ConversationState:
        if state.get("context_loaded"):
            logger.info("Context already loaded, skipping")
            return state
        try:
            logger.info(f"Loading context for user {state['user_id']}")
            context_result = self.context_assembler.get_conversation_context(int(state["user_id"]))
            state["assembled_context"] = context_result["context"]
        except Exception as e:
            logger.error(f"Context error: {e}")
            state["error"] = str(e)
            state["assembled_context"] = {}
        return state

    def _build_system_prompt(self, state: ConversationState) -> ConversationState:
        try:
            state["system_prompt"] = self.context_assembler.build_system_prompt(state["assembled_context"])
        except Exception as e:
            logger.error(f"Prompt error: {e}")
            state["system_prompt"] = "You are a helpful assistant."
            state["error"] = str(e)
        return state

    def _generate_response(self, state: ConversationState) -> ConversationState:
        try:
            logger.info("Generating LLM response")
            user_message = state["user_message"]
            history = state.get("messages", [])

            response = self.llm_client.chat(
                user_message=user_message,
                conversation_history=history,
                system_prompt=state["system_prompt"],
                temperature=0.7,
                max_tokens=1000
            )

            updated = history + [
                {"role": "assistant", "content": response.text}
            ]

            state["messages"] = updated
            state["response"] = response.text
        except LLMError as e:
            logger.error(f"LLM error: {e}")
            state["response"] = "Sorry, I'm having trouble right now."
            state["error"] = str(e)
        return state

    def _update_conversation(self, state: ConversationState) -> ConversationState:
        try:
            user_id = int(state["user_id"])
            session = self.db_manager.get_session()
            try:
                conv = None
                if state.get("conversation_id"):
                    conv = session.query(Conversation).filter(Conversation.id == int(state["conversation_id"])).first()
                if not conv:
                    conv = Conversation(
                        user_id=user_id,
                        session_id=uuid.uuid4(),
                        messages=[],
                        status="active"
                    )
                    session.add(conv)
                    session.flush()

                conv.messages = state["messages"]
                session.commit()
                state["conversation_id"] = str(conv.id)
                state["should_update_memory"] = True
            finally:
                session.close()
        except Exception as e:
            logger.error(f"DB update error: {e}")
            state["error"] = str(e)
            state["should_update_memory"] = False
        return state

    @staticmethod
    def _check_should_continue(state: ConversationState) -> ConversationState:
        messages = state.get("messages", [])
        last_user_input = messages[-2]["content"].strip().lower() if len(messages) >= 2 else ""

        if last_user_input in {"bye", "goodbye"}:
            logger.info("Stopping conversation based on user message")
            state["stop_conversation"] = True
            state["__next__"] = "trigger_highlights"
        elif len(messages) >= 10:
            logger.info("Stopping conversation based on message limit")
            state["stop_conversation"] = True
            state["__next__"] = "trigger_highlights"
        else:
            logger.info("Continuing conversation")
            state["stop_conversation"] = False
            state["__next__"] = "load_context"

        return state

    @staticmethod
    def _trigger_highlights_extraction(state: ConversationState) -> ConversationState:
        try:
            if state.get("should_update_memory") and state.get("conversation_id"):
                from memory.highlights import HighlightsExtractor
                extractor = HighlightsExtractor()
                extractor.process_conversation(int(state["conversation_id"]))
        except Exception as e:
            logger.warning(f"Highlight extraction error: {e}")
        return state

    def chat(self, user_id: str, initial_message: str) -> Dict[str, Any]:
        state = ConversationState(
            user_id=user_id,
            user_message=initial_message,
            messages=[],
            conversation_id=None,
            assembled_context={},
            system_prompt="",
            response="",
            error=None,
            should_update_memory=False,
            stop_conversation=False
        )
        return self.workflow.invoke(state)

def create_conversation_orchestrator():
    return ConversationOrchestrator()


if __name__ == "__main__":
    print("=== TESTING CONVERSATION ORCHESTRATOR LOOP ===")
    session = get_db_session()
    try:
        user = session.query(User).first()
        if user:
            orchestrator = ConversationOrchestrator()
            state = {
                "user_id": str(user.id),
                "user_message": "How am I doing this week?",
                "messages": [],
                "conversation_id": None,
                "assembled_context": {},
                "system_prompt": "",
                "response": "",
                "error": None,
                "should_update_memory": False,
                "stop_conversation": False
            }

            while not state["stop_conversation"]:
                result = orchestrator.workflow.invoke(state)
                print(f"User: {state['user_message']}")
                print(f"Assistant: {result['response'][:100]}...")

                state = result
                if not state["stop_conversation"]:
                    # Simulate next user message
                    state["user_message"] = input("You: ")
    finally:
        session.close()
