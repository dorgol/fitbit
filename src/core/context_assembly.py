"""
Context Assembly - Pulls data from all 6 memory layers and builds LLM context

Uses a modular "lego brick" approach where different sections can be mixed and matched
to create personalized system prompts and context for conversations.
"""

import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
import logging

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, User, HealthMetric, Insight,
    ExternalContext, KnowledgeBase, get_db_session
)
from memory.raw_data import RawDataLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptSection:
    """Base class for modular prompt sections - the 'lego bricks'"""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    def generate(self, context: Dict[str, Any]) -> str:
        """Generate the text for this section"""
        if not self.enabled:
            return ""
        return self._generate_content(context)

    def _generate_content(self, context: Dict[str, Any]) -> str:
        """Override this in subclasses"""
        raise NotImplementedError


class BaseCharacterSection(PromptSection):
    """Core character/personality for the health assistant"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        user_prefs = context.get("user_preferences", {})
        communication_style = user_prefs.get("communication_style", "encouraging")

        base_character = """You are a helpful and knowledgeable health assistant for Fitbit users.

Your core personality:
- Supportive and encouraging, celebrating progress and victories
- Data-driven but human-centered - use specific numbers but focus on the person
- Motivational without being pushy - respect user autonomy
- Honest about limitations - you're not a doctor and can't diagnose
- Curious and engaging - ask follow-up questions to keep conversation flowing"""

        # Adjust based on user's preferred communication style
        style_adjustments = {
            "encouraging": "\n- Extra emphasis on positive reinforcement and motivation",
            "analytical": "\n- Focus on data patterns, trends, and quantitative insights",
            "casual": "\n- Keep tone relaxed and conversational, less formal"
        }

        if communication_style in style_adjustments:
            base_character += style_adjustments[communication_style]

        return base_character


class HealthDataSection(PromptSection):
    """Current health data and recent metrics"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        raw_data = context.get("raw_data", {})

        if not raw_data:
            return "CURRENT HEALTH DATA:\nNo recent health data available."

        sections = []

        # Recent metrics summary
        if raw_data.get("recent_metrics"):
            metrics = raw_data["recent_metrics"]
            sections.append("Recent Activity Summary:")

            if "steps" in metrics:
                steps = metrics["steps"]
                avg_steps = sum(steps) / len(steps) if steps else 0
                sections.append(f"- Daily steps (last {len(steps)} days): {steps} (avg: {avg_steps:.0f})")

            if "sleep_hours" in metrics:
                sleep = metrics["sleep_hours"]
                avg_sleep = sum(sleep) / len(sleep) if sleep else 0
                sections.append(f"- Sleep duration (last {len(sleep)} nights): {sleep} hours (avg: {avg_sleep:.1f}h)")

            if "heart_rate" in metrics:
                hr = metrics["heart_rate"]
                avg_hr = sum(hr) / len(hr) if hr else 0
                sections.append(f"- Resting heart rate (recent): {hr} bpm (avg: {avg_hr:.0f})")

        # User profile
        if raw_data.get("user_profile"):
            profile = raw_data["user_profile"]
            sections.append(f"\nUser Profile:")
            sections.append(f"- Age: {profile.get('age', 'unknown')}")
            sections.append(f"- Goals: {', '.join(profile.get('goals', []))}")
            if profile.get("location"):
                sections.append(f"- Location: {profile.get('location')}")

        return "CURRENT HEALTH DATA:\n" + "\n".join(sections)


class InsightsSection(PromptSection):
    """Generated insights and analysis"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        insights = context.get("insights", [])

        if not insights:
            return "RECENT INSIGHTS:\nNo recent insights available."

        sections = ["RECENT INSIGHTS:"]

        # Group insights by category
        insight_groups = {}
        for insight in insights:
            category = insight.get("category", "general")
            if category not in insight_groups:
                insight_groups[category] = []
            insight_groups[category].append(insight)

        # Format each group
        for category, group_insights in insight_groups.items():
            sections.append(f"\n{category.replace('_', ' ').title()}:")
            for insight in group_insights[:3]:  # Limit to top 3 per category
                confidence = insight.get("confidence", 0)
                timeframe = insight.get("timeframe", "recent")
                sections.append(f"- {insight.get('finding')} (confidence: {confidence:.0%}, timeframe: {timeframe})")

        return "\n".join(sections)


class UserContextSection(PromptSection):
    """User context from conversation highlights"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        highlights = context.get("highlights", {})

        if not highlights or not highlights.get("structured_data"):
            return "USER CONTEXT:\nNo previous conversation context available."

        sections = ["USER CONTEXT:"]

        structured = highlights.get("structured_data", {})

        # Important health context first
        priority_fields = ["allergies", "health_concerns", "medications", "family_health"]
        health_context = []
        for field in priority_fields:
            value = structured.get(field)
            if value:
                field_name = field.replace("_", " ").title()
                health_context.append(f"- {field_name}: {value}")

        if health_context:
            sections.append("\nHealth Context:")
            sections.extend(health_context)

        # Lifestyle and preferences
        lifestyle_fields = ["work_schedule", "sleep_schedule", "exercise_preferences", "nutrition_preferences"]
        lifestyle_context = []
        for field in lifestyle_fields:
            value = structured.get(field)
            if value:
                field_name = field.replace("_", " ").title()
                lifestyle_context.append(f"- {field_name}: {value}")

        if lifestyle_context:
            sections.append("\nLifestyle & Preferences:")
            sections.extend(lifestyle_context)

        # Goals and motivations
        goals_context = []
        for field in ["goals_mentioned", "motivation_factors", "stress_sources"]:
            value = structured.get(field)
            if value:
                field_name = field.replace("_", " ").title()
                goals_context.append(f"- {field_name}: {value}")

        if goals_context:
            sections.append("\nGoals & Motivation:")
            sections.extend(goals_context)

        # Unstructured notes
        if highlights.get("unstructured_notes"):
            sections.append(f"\nAdditional Context:")
            sections.append(f"- {highlights['unstructured_notes']}")

        return "\n".join(sections)


class ExternalContextSection(PromptSection):
    """External context like weather, time, etc."""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        external = context.get("external_data", {})

        if not external:
            return "EXTERNAL CONTEXT:\nNo external context available."

        sections = ["EXTERNAL CONTEXT:"]

        # Weather information
        if external.get("weather"):
            weather = external["weather"]
            weather_parts = []
            if weather.get("temperature"):
                weather_parts.append(f"{weather['temperature']}°C")
            if weather.get("condition"):
                weather_parts.append(weather["condition"])
            if weather.get("air_quality"):
                weather_parts.append(f"air quality: {weather['air_quality']}")

            if weather_parts:
                sections.append(f"- Weather: {', '.join(weather_parts)}")

        # Time context
        now = datetime.now()
        sections.append(f"- Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}")

        # Add any other external context
        for key, value in external.items():
            if key != "weather" and value:
                sections.append(f"- {key.replace('_', ' ').title()}: {value}")

        return "\n".join(sections)


class KnowledgeSection(PromptSection):
    """Relevant health knowledge and education"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        knowledge = context.get("knowledge", [])

        if not knowledge:
            return "HEALTH KNOWLEDGE:\nGeneral health and fitness knowledge available as needed."

        sections = ["RELEVANT HEALTH KNOWLEDGE:"]

        for item in knowledge[:3]:  # Limit to top 3 most relevant
            topic = item.get("topic", "general")
            content = item.get("content", "")
            source = item.get("source", "")

            sections.append(f"\n{topic.replace('_', ' ').title()}:")
            sections.append(f"- {content}")
            if source:
                sections.append(f"  Source: {source}")

        return "\n".join(sections)


class ConversationGuidelinesSection(PromptSection):
    """Guidelines for conversation behavior"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        user_prefs = context.get("user_preferences", {})

        guidelines = """CONVERSATION GUIDELINES:
- Always reference specific data when making observations or suggestions
- Ask engaging follow-up questions to keep the conversation flowing
- Celebrate improvements and progress, no matter how small
- If you notice concerning patterns, suggest gentle lifestyle changes rather than medical advice
- Keep responses concise but helpful (2-4 sentences typically)
- Use the user's preferred communication style and adapt to their needs"""

        # Add personalized guidelines based on user context
        highlights = context.get("highlights", {})
        if highlights and highlights.get("structured_data"):
            structured = highlights["structured_data"]

            personal_guidelines = []

            if structured.get("allergies"):
                personal_guidelines.append("- Be mindful of food allergies when discussing nutrition")

            if structured.get("work_schedule"):
                personal_guidelines.append("- Consider work schedule when suggesting activity timing")

            if structured.get("stress_sources"):
                personal_guidelines.append("- Be sensitive to stress factors and suggest stress management")

            if personal_guidelines:
                guidelines += "\n\nPersonalized Guidelines:\n" + "\n".join(personal_guidelines)

        return guidelines


class ContextAssembler:
    """Main class that assembles context from all memory layers"""

    def __init__(self):
        self.db_manager = DatabaseManager()

        # Define available prompt sections - the "lego bricks"
        self.available_sections = {
            "base_character": BaseCharacterSection("base_character"),
            "health_data": HealthDataSection("health_data"),
            "insights": InsightsSection("insights"),
            "user_context": UserContextSection("user_context"),
            "external_context": ExternalContextSection("external_context"),
            "knowledge": KnowledgeSection("knowledge"),
            "guidelines": ConversationGuidelinesSection("guidelines")
        }

        # Default prompt configuration
        self.default_sections = [
            "base_character",
            "health_data",
            "insights",
            "user_context",
            "external_context",
            "knowledge",
            "guidelines"
        ]

    def load_insights(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Load recent insights for the user"""
        session = self.db_manager.get_session()

        try:
            insights = session.query(Insight).filter(
                Insight.user_id == user_id,
                Insight.expires_at > datetime.now(timezone.utc)
            ).order_by(Insight.confidence.desc()).limit(limit).all()

            return [
                {
                    "category": insight.category,
                    "finding": insight.finding,
                    "timeframe": insight.timeframe,
                    "confidence": insight.confidence,
                    "extra_data": insight.extra_data
                }
                for insight in insights
            ]

        finally:
            session.close()

    def load_highlights(self, user_id: int) -> Dict[str, Any]:
        """Load consolidated conversation highlights for the user"""
        session = self.db_manager.get_session()

        try:
            from memory.highlights import HighlightsExtractor
            extractor = HighlightsExtractor()
            return extractor.get_user_highlights_summary(user_id)

        finally:
            session.close()

    def load_external_data(self, user_location: str) -> Dict[str, Any]:
        """Load external context data"""
        session = self.db_manager.get_session()

        try:
            # Get weather data for user's location
            weather_data = session.query(ExternalContext).filter(
                ExternalContext.context_type == "weather",
                ExternalContext.location == user_location
            ).order_by(ExternalContext.timestamp.desc()).first()

            external = {}
            if weather_data and weather_data.data:
                external["weather"] = weather_data.data

            return external

        finally:
            session.close()

    def load_knowledge(self, relevant_topics: List[str] = None) -> List[Dict[str, Any]]:
        """Load relevant knowledge base entries"""
        session = self.db_manager.get_session()

        try:
            # For now, get general health knowledge
            # In the future, this could be filtered by relevant_topics
            knowledge_entries = session.query(KnowledgeBase).limit(5).all()

            return [
                {
                    "topic": entry.topic,
                    "content": entry.content,
                    "source": entry.source
                }
                for entry in knowledge_entries
            ]

        finally:
            session.close()

    def assemble_full_context(self, user_id: int) -> Dict[str, Any]:
        """Assemble context from all 6 memory layers"""

        # Load from all layers
        raw_data = RawDataLoader().load_user_data(user_id)
        insights = self.load_insights(user_id)
        highlights = self.load_highlights(user_id)

        user_location = raw_data.get("user_profile", {}).get("location", "")
        external_data = self.load_external_data(user_location)
        knowledge = self.load_knowledge()

        return {
            "user_id": user_id,
            "raw_data": raw_data,
            "insights": insights,
            "highlights": highlights,
            "external_data": external_data,
            "knowledge": knowledge,
            "user_preferences": raw_data.get("user_profile", {}).get("preferences", {})
        }

    def build_system_prompt(self, context: Dict[str, Any],
                            sections: List[str] = None) -> str:
        """Build system prompt using specified sections"""

        if sections is None:
            sections = self.default_sections

        prompt_parts = []

        for section_name in sections:
            if section_name in self.available_sections:
                section = self.available_sections[section_name]
                content = section.generate(context)
                if content.strip():
                    prompt_parts.append(content)
            else:
                logger.warning(f"Unknown prompt section: {section_name}")

        return "\n\n" + "---\n".join(prompt_parts) + "\n---"

    def get_conversation_context(self, user_id: int,
                                 sections: List[str] = None) -> Dict[str, Any]:
        """Get complete conversation context - main entry point"""

        context = self.assemble_full_context(user_id)
        system_prompt = self.build_system_prompt(context, sections)

        return {
            "context": context,
            "system_prompt": system_prompt,
            "user_id": user_id
        }


# Convenience functions for easy usage
def get_conversation_context(user_id: int, sections: List[str] = None) -> Dict[str, Any]:
    """Main function to get conversation context for a user"""
    assembler = ContextAssembler()
    return assembler.get_conversation_context(user_id, sections)


def get_custom_prompt(user_id: int, sections: List[str]) -> str:
    """Get a custom system prompt with specific sections"""
    assembler = ContextAssembler()
    context = assembler.assemble_full_context(user_id)
    return assembler.build_system_prompt(context, sections)


if __name__ == "__main__":
    # Test the context assembly
    print("=== TESTING CONTEXT ASSEMBLY ===")

    session = get_db_session()
    try:
        user = session.query(User).first()
        if user:
            print(f"Testing context assembly for user {user.id}")

            assembler = ContextAssembler()
            result = assembler.get_conversation_context(user.id)

            print(f"\nSystem prompt length: {len(result['system_prompt'])} characters")
            print(f"\nSystem prompt preview:")
            print(result['system_prompt'][:500] + "..." if len(result['system_prompt']) > 500 else result[
                'system_prompt'])

        else:
            print("No users found in database")
    finally:
        session.close()