"""
Conversation Orchestrator - LangGraph-based conversation management

Handles the main conversation flow using LangGraph state management and workflows.
"""

from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from ..api.llm_factory import get_llm_client
from ..api.llm_interface import LLMError


class ConversationState(TypedDict):
    """State structure for the conversation workflow"""
    user_id: str
    user_message: str
    conversation_history: List[Dict[str, str]]
    assembled_context: Dict[str, Any]
    system_prompt: str
    response: str
    error: Optional[str]


class ConversationOrchestrator:
    """
    Main conversation orchestrator using LangGraph workflows
    """

    def __init__(self):
        """Initialize the conversation orchestrator"""
        self.llm_client = get_llm_client()
        self.workflow = self._build_workflow()

        # Base system prompt for the health assistant
        self.base_system_prompt = """You are a helpful and encouraging health assistant for Fitbit users. 

Your role:
- Provide personalized insights based on user's health data
- Offer actionable advice and gentle encouragement
- Keep responses conversational and supportive
- Reference specific data patterns when relevant
- Suggest follow-up actions or questions when appropriate

Guidelines:
- Always be positive and motivational
- Use specific data points to make insights concrete
- Avoid medical diagnosis - focus on lifestyle and wellness
- Keep responses concise but helpful
- Ask follow-up questions to keep the conversation engaging"""

    def _build_workflow(self) -> Any:
        """Build the LangGraph conversation workflow"""

        # Define the workflow graph
        workflow = StateGraph(ConversationState)

        # Add nodes
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("build_prompt", self._build_system_prompt)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("update_memory", self._update_memory)

        # Define the flow
        workflow.set_entry_point("load_context")
        workflow.add_edge("load_context", "build_prompt")
        workflow.add_edge("build_prompt", "generate_response")
        workflow.add_edge("generate_response", "update_memory")
        return workflow.compile()

    def _load_context(self, state: ConversationState) -> ConversationState:
        """
        Load and assemble context from all 6 memory layers

        For now, this uses mock data. Will be replaced with real memory system.
        """
        user_id = state["user_id"]

        # TODO: Replace with real context assembly
        mock_context = {
            "raw_data": {
                "recent_steps": [8500, 12000, 6800, 9200, 10500],
                "sleep_hours": [7.2, 6.8, 8.1, 7.5, 6.9],
                "resting_hr": [68, 70, 67, 69, 71],
                "user_profile": {
                    "age": 32,
                    "goals": ["better_sleep", "10k_steps_daily"],
                    "location": "Tel Aviv"
                }
            },
            "insights": [
                "Sleep quality improving over past week",
                "Step count varies significantly on weekends",
                "Resting heart rate stable and healthy"
            ],
            "highlights": {
                "preferences": "Prefers specific workout suggestions",
                "concerns": "Mentioned work stress affecting sleep",
                "tried_interventions": "Started evening breathing exercises"
            },
            "external_data": {
                "weather": "Sunny, 24°C in Tel Aviv",
                "air_quality": "Good"
            }
        }

        state["assembled_context"] = mock_context
        return state

    def _build_system_prompt(self, state: ConversationState) -> ConversationState:
        """
        Build the complete system prompt with context
        """
        context = state["assembled_context"]

        # Format context sections
        health_data_section = self._format_health_data(context.get("raw_data", {}))
        insights_section = self._format_insights(context.get("insights", []))
        highlights_section = self._format_highlights(context.get("highlights", {}))
        external_section = self._format_external_data(context.get("external_data", {}))

        # Build complete system prompt
        full_prompt = f"""{self.base_system_prompt}

---
CURRENT HEALTH DATA:
{health_data_section}

RECENT INSIGHTS:
{insights_section}

USER CONTEXT:
{highlights_section}

EXTERNAL CONTEXT:
{external_section}

---
Remember to use this context to provide personalized, specific responses to the user's question."""

        state["system_prompt"] = full_prompt
        return state

    def _format_health_data(self, raw_data: Dict) -> str:
        """Format raw health data for the prompt"""
        if not raw_data:
            return "No recent health data available."

        formatted = []

        if "recent_steps" in raw_data:
            steps = raw_data["recent_steps"]
            avg_steps = sum(steps) / len(steps) if steps else 0
            formatted.append(f"Recent daily steps: {steps} (avg: {avg_steps:.0f})")

        if "sleep_hours" in raw_data:
            sleep = raw_data["sleep_hours"]
            avg_sleep = sum(sleep) / len(sleep) if sleep else 0
            formatted.append(f"Recent sleep duration: {sleep} hours (avg: {avg_sleep:.1f}h)")

        if "resting_hr" in raw_data:
            hr = raw_data["resting_hr"]
            avg_hr = sum(hr) / len(hr) if hr else 0
            formatted.append(f"Recent resting heart rate: {hr} bpm (avg: {avg_hr:.0f})")

        if "user_profile" in raw_data:
            profile = raw_data["user_profile"]
            formatted.append(f"User profile: Age {profile.get('age', 'unknown')}, Goals: {profile.get('goals', [])}")

        return "\n".join(formatted) if formatted else "No health data available."

    def _format_insights(self, insights: List[str]) -> str:
        """Format insights for the prompt"""
        if not insights:
            return "No recent insights available."

        return "\n".join([f"- {insight}" for insight in insights])

    def _format_highlights(self, highlights: Dict) -> str:
        """Format conversation highlights for the prompt"""
        if not highlights:
            return "No previous conversation context."

        formatted = []
        for key, value in highlights.items():
            formatted.append(f"{key.replace('_', ' ').title()}: {value}")

        return "\n".join(formatted) if formatted else "No conversation context."

    def _format_external_data(self, external: Dict) -> str:
        """Format external data for the prompt"""
        if not external:
            return "No external context available."

        formatted = []
        for key, value in external.items():
            formatted.append(f"{key.replace('_', ' ').title()}: {value}")

        return "\n".join(formatted) if formatted else "No external context."

    def _generate_response(self, state: ConversationState) -> ConversationState:
        """
        Generate response using the LLM
        """
        try:
            response = self.llm_client.chat(
                user_message=state["user_message"],
                conversation_history=state["conversation_history"],
                system_prompt=state["system_prompt"]
            )
            state["response"] = response
            state["error"] = None

        except LLMError as e:
            state["response"] = "I'm sorry, I'm having trouble processing your request right now. Please try again."
            state["error"] = str(e)

        return state

    def _update_memory(self, state: ConversationState) -> ConversationState:
        """
        Update conversation memory and extract highlights

        For now, this is a placeholder. Will be implemented with real memory system.
        """
        # TODO: Update conversation history in database
        # TODO: Extract highlights from conversation
        # TODO: Update user context

        # For now, just log that we're updating memory
        print(f"[Memory Update] User {state['user_id']}: {state['user_message'][:50]}...")

        return state

    def chat(self, user_id: str, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Main entry point for conversation

        Args:
            user_id: Unique identifier for the user
            user_message: The user's current message
            conversation_history: Previous conversation messages

        Returns:
            str: The assistant's response
        """
        # Initialize state
        initial_state = ConversationState(
            user_id=user_id,
            user_message=user_message,
            conversation_history=conversation_history or [],
            assembled_context={},
            system_prompt="",
            response="",
            error=None
        )

        # Run the workflow
        final_state = self.workflow.invoke(initial_state)

        # Return the response
        return final_state["response"]

    def is_available(self) -> bool:
        """Check if the orchestrator is ready to handle conversations"""
        return self.llm_client.is_available()


# Convenience function for easy usage
def create_conversation_orchestrator() -> ConversationOrchestrator:
    """Create and return a conversation orchestrator instance"""
    return ConversationOrchestrator()
