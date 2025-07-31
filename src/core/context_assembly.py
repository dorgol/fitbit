"""
Context Assembly - Pulls data from all 6 memory layers and builds LLM context

Uses a modular "lego brick" approach where different sections can be mixed and matched
to create personalized system prompts and context for conversations.
"""

import sys
from datetime import datetime, timezone
from typing import Dict, List, Any
import logging
from contextlib import contextmanager

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, User, Insight,
    ExternalContext, KnowledgeBase, get_db_session
)
from memory.raw_data import RawDataLoader
from utils.load_prompts import render_prompt

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

        return render_prompt("base_character", {
            "communication_style": communication_style
        })


class HealthDataSection(PromptSection):
    """Current health data and recent metrics"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        raw_data = context.get("raw_data", {})

        if not raw_data:
            return "CURRENT HEALTH DATA:\nNo recent health data available."

        return render_prompt("health_data", {
            "recent_metrics": raw_data.get("recent_metrics", {}),
            "user_profile": raw_data.get("user_profile", {})
        })


class InsightsSection(PromptSection):
    """Generated insights and analysis"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        insights = context.get("insights", [])

        if not insights:
            return "RECENT INSIGHTS:\nNo recent insights available."

        return render_prompt("insights", {"insights": insights})


class UserContextSection(PromptSection):
    """User context from conversation highlights"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        highlights = context.get("highlights", {})
        structured = highlights.get("structured_data", {})
        notes = highlights.get("unstructured_notes", "")

        if not structured and not notes:
            return "USER CONTEXT:\nNo previous conversation context available."

        return render_prompt("user_context", {
            "structured_data": structured,
            "unstructured_notes": notes
        })


class ExternalContextSection(PromptSection):
    """External context like weather, time, etc."""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        external = context.get("external_data", {})
        weather = external.get("weather", {})

        if not external and not weather:
            return "EXTERNAL CONTEXT:\nNo external context available."

        return render_prompt("external_context", {
            "external": external,
            "weather": weather,
            "current_time": datetime.now()
        })


class KnowledgeSection(PromptSection):
    """Relevant health knowledge and education"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        knowledge = context.get("knowledge", [])

        return render_prompt("knowledge", {"knowledge": knowledge})


class ConversationGuidelinesSection(PromptSection):
    """Guidelines for conversation behavior"""

    def _generate_content(self, context: Dict[str, Any]) -> str:
        structured = context.get("highlights", {}).get("structured_data", {})

        return render_prompt("conversation_guidelines", {
            "structured_data": structured
        })


class ContextAssembler:
    """Main class that assembles context from all memory layers"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.raw_data_loader = RawDataLoader()

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

    @contextmanager
    def get_session(self):
        session = self.db_manager.get_session()
        try:
            yield session
        finally:
            session.close()

    def load_insights(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        logger.debug(f"[Assembler] Loading insights for user {user_id}")
        try:
            with self.get_session() as session:
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
        except Exception as e:
            logger.error(f"[Assembler] Failed to load insights: {e}", exc_info=True)
            return []

    @staticmethod
    def load_highlights(user_id: int) -> Dict[str, Any]:
        logger.debug(f"[Assembler] Loading highlights for user {user_id}")
        try:
            from memory.highlights import HighlightsExtractor
            extractor = HighlightsExtractor()
            return extractor.get_user_highlights_summary(user_id)
        except Exception as e:
            logger.error(f"[Assembler] Failed to load highlights: {e}", exc_info=True)
            return {}

    def load_external_data(self, user_location: str) -> Dict[str, Any]:
        logger.debug(f"[Assembler] Loading external data for location: {user_location}")
        try:
            with self.get_session() as session:
                weather_data = session.query(ExternalContext).filter(
                    ExternalContext.context_type == "weather",
                    ExternalContext.location == user_location
                ).order_by(ExternalContext.timestamp.desc()).first()

                external = {}
                if weather_data and weather_data.data:
                    external["weather"] = weather_data.data

                return external
        except Exception as e:
            logger.error(f"[Assembler] Failed to load external data: {e}", exc_info=True)
            return {}

    def load_knowledge(self, relevant_topics: List[str] = None) -> List[Dict[str, Any]]:
        logger.debug("[Assembler] Loading knowledge entries")
        try:
            with self.get_session() as session:
                knowledge_entries = session.query(KnowledgeBase).limit(5).all()
                return [
                    {
                        "topic": entry.topic,
                        "content": entry.content,
                        "source": entry.source
                    }
                    for entry in knowledge_entries
                ]
        except Exception as e:
            logger.error(f"[Assembler] Failed to load knowledge entries: {e}", exc_info=True)
            return []

    def assemble_full_context(self, user_id: int) -> Dict[str, Any]:
        logger.debug(f"[Assembler] Assembling full context for user {user_id}")

        raw_data = self.raw_data_loader.load_user_data(user_id)
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
        if sections is None:
            sections = self.default_sections

        logger.debug(f"[Assembler] Building system prompt using sections: {sections}")

        prompt_parts = []

        for section_name in sections:
            if section_name in self.available_sections:
                section = self.available_sections[section_name]
                content = section.generate(context)
                if content.strip():
                    prompt_parts.append(content)
            else:
                logger.warning(f"Unknown prompt section: {section_name}")

        system_prompt = "\n---\n".join(prompt_parts) + "\n"
        logger.info(f"[Assembler] System prompt length: {len(system_prompt)} characters")
        return system_prompt

    def get_conversation_context(self, user_id: int,
                                 sections: List[str] = None) -> Dict[str, Any]:
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
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("=== TESTING CONTEXT ASSEMBLY ===")

    session = get_db_session()
    try:
        user = session.query(User).first()
        if user:
            logger.info(f"Testing context assembly for user {user.id}")
            assembler = ContextAssembler()

            try:
                result = assembler.get_conversation_context(user.id)
                preview = result["system_prompt"]
                if len(preview) > 500:
                    preview = preview[:500] + "..."
                logger.info(f"System prompt length: {len(result['system_prompt'])} characters")
                logger.info(f"System prompt preview:\n{preview}")
            except Exception as e:
                logger.error(f"Error generating context: {e}", exc_info=True)
        else:
            logger.warning("No users found in database")
    finally:
        session.close()
