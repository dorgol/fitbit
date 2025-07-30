"""
Database models and connection management

SQLAlchemy models for all database tables and database session management.
"""

import os
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
# from sqlalchemy.ext.declarative import
from sqlalchemy.orm import sessionmaker, relationship, Session, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
import uuid

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fitbit_ai_poc.db")

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class User(Base):
    """User profile and basic information"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    age = Column(Integer)
    gender = Column(String(10))
    location = Column(String(100))
    goals = Column(JSON)
    preferences = Column(JSON)

    # Relationships
    health_metrics = relationship("HealthMetric", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    insights = relationship("Insight", back_populates="user")
    highlights = relationship("Highlight", back_populates="user")


class HealthMetric(Base):
    """Time-series health data"""
    __tablename__ = "health_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    metric_type = Column(String(50), index=True)
    value = Column(Float)
    timestamp = Column(DateTime, index=True)
    extra_data = Column(JSON)

    # Relationships
    user = relationship("User", back_populates="health_metrics")

    def __repr__(self):
        return f"<HealthMetric(user_id={self.user_id}, type={self.metric_type}, value={self.value})>"


class Conversation(Base):
    """Conversation sessions and message history"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    session_id = Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)
    messages = Column(JSON)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    highlights = relationship("Highlight", back_populates="conversation")

    def __repr__(self):
        return f"<Conversation(user_id={self.user_id}, status={self.status}, messages={len(self.messages or [])})>"


class Insight(Base):
    """Generated health insights and analysis"""
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    category = Column(String(50), index=True)
    finding = Column(Text)
    timeframe = Column(String(20))
    confidence = Column(Float)
    extra_data = Column(JSON)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="insights")

    def __repr__(self):
        return f"<Insight(user_id={self.user_id}, category={self.category}, confidence={self.confidence})>"


class HighlightSchema:
    """Defines the structured fields that can be extracted from conversations"""

    STRUCTURED_FIELDS = {
        "allergies": {
            "type": "list",
            "description": "Food allergies, environmental allergies, or medication allergies",
            "examples": ["dairy", "peanuts", "pollen"]
        },
        "work_schedule": {
            "type": "string",
            "description": "Work hours, shift patterns, or schedule constraints",
            "examples": ["9-5 weekdays", "late shifts ending 10 PM", "rotating shifts"]
        },
        "exercise_preferences": {
            "type": "string",
            "description": "Preferred activities, times, or workout types",
            "examples": ["yoga in mornings", "running outdoors", "gym 3x/week"]
        },
        "health_concerns": {
            "type": "list",
            "description": "Specific health issues, conditions, or areas of focus",
            "examples": ["family heart disease history", "high blood pressure", "back pain"]
        },
        "sleep_schedule": {
            "type": "string",
            "description": "Bedtime routines, wake times, or sleep preferences",
            "examples": ["11 PM bedtime, 6 AM wake", "trouble falling asleep", "needs 8+ hours"]
        },
        "nutrition_preferences": {
            "type": "string",
            "description": "Dietary habits, meal timing, or food preferences",
            "examples": ["vegetarian", "intermittent fasting", "meal prep Sundays"]
        },
        "stress_sources": {
            "type": "list",
            "description": "Sources of stress or factors affecting wellbeing",
            "examples": ["work deadlines", "family responsibilities", "financial concerns"]
        },
        "medications": {
            "type": "list",
            "description": "Medications, supplements, or treatments mentioned",
            "examples": ["vitamin D", "blood pressure medication", "melatonin"]
        },
        "family_health": {
            "type": "string",
            "description": "Relevant family health history or genetic considerations",
            "examples": ["diabetes runs in family", "mother had heart disease"]
        },
        "goals_mentioned": {
            "type": "list",
            "description": "Specific health or fitness goals mentioned in conversation",
            "examples": ["lose 10 pounds", "run 5K", "improve sleep quality", "10k steps daily"]
        },
        "communication_style": {
            "type": "string",
            "description": "How user prefers to receive information and feedback",
            "examples": ["encouraging and positive", "analytical with data", "casual and brief"]
        },
        "motivation_factors": {
            "type": "string",
            "description": "What motivates or drives this user",
            "examples": ["health scare motivation", "wants to keep up with kids", "competitive nature"]
        }
    }

    @classmethod
    def get_field_names(cls):
        """Get list of all structured field names"""
        return list(cls.STRUCTURED_FIELDS.keys())

    @classmethod
    def get_field_description(cls, field_name):
        """Get description for a specific field"""
        return cls.STRUCTURED_FIELDS.get(field_name, {}).get("description", "")

    @classmethod
    def validate_structured_data(cls, data):
        """Validate that structured data contains only known fields"""
        if not isinstance(data, dict):
            return False

        unknown_fields = set(data.keys()) - set(cls.STRUCTURED_FIELDS.keys())
        if unknown_fields:
            raise ValueError(f"Unknown structured fields: {unknown_fields}")

        return True

    @classmethod
    def get_extraction_template(cls):
        """Generate template for LLM extraction"""
        template = {}
        for field_name in cls.STRUCTURED_FIELDS.keys():
            template[field_name] = None
        return template

    @classmethod
    def get_prompt_description(cls):
        """Generate field descriptions for LLM prompt"""
        descriptions = []
        for field_name, field_info in cls.STRUCTURED_FIELDS.items():
            desc = field_info["description"]
            examples = ", ".join(field_info.get("examples", [])[:2])
            if examples:
                descriptions.append(f"- {field_name}: {desc} (e.g., {examples})")
            else:
                descriptions.append(f"- {field_name}: {desc}")
        return "\n".join(descriptions)


class Highlight(Base):
    """Extracted conversation highlights and user context"""
    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    structured_data = Column(JSON)
    unstructured_notes = Column(Text)
    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="highlights")
    conversation = relationship("Conversation", back_populates="highlights")

    def __init__(self, **kwargs):
        """Initialize with schema validation"""
        # Validate structured_data if provided
        if 'structured_data' in kwargs and kwargs['structured_data'] is not None:
            HighlightSchema.validate_structured_data(kwargs['structured_data'])

        super().__init__(**kwargs)

    @property
    def valid_structured_fields(self):
        """Get only the structured data fields that have non-null values"""
        if not self.structured_data:
            return {}

        return {
            key: value for key, value in self.structured_data.items()
            if value is not None and value != "" and value != []
        }

    def get_field_value(self, field_name):
        """Get a specific structured field value"""
        if not self.structured_data:
            return None
        return self.structured_data.get(field_name)

    def has_field(self, field_name):
        """Check if a structured field has a value"""
        value = self.get_field_value(field_name)
        return value is not None and value != "" and value != []

    def update_structured_data(self, new_data):
        """Update structured data with validation"""
        if new_data:
            HighlightSchema.validate_structured_data(new_data)

            # Merge with existing data (new data takes precedence)
            if self.structured_data:
                merged = self.structured_data.copy()
                merged.update(new_data)
                self.structured_data = merged
            else:
                self.structured_data = new_data

            self.extracted_at = datetime.now(timezone.utc)

    def get_summary(self):
        """Get a human-readable summary of this highlight"""
        summary_parts = []

        valid_fields = self.valid_structured_fields
        if valid_fields:
            summary_parts.append(f"Structured fields: {', '.join(valid_fields.keys())}")

        if self.unstructured_notes and self.unstructured_notes.strip():
            note_preview = self.unstructured_notes[:100] + "..." if len(
                self.unstructured_notes) > 100 else self.unstructured_notes
            summary_parts.append(f"Notes: {note_preview}")

        return " | ".join(summary_parts) if summary_parts else "No highlights extracted"

    @classmethod
    def get_user_consolidated_data(cls, session, user_id):
        """
        Get consolidated structured data for a user across all their highlights

        This is a class method that can be called without an instance:
        consolidated = Highlight.get_user_consolidated_data(session, user_id)
        """
        highlights = session.query(cls).filter(
            cls.user_id == user_id
        ).order_by(cls.extracted_at.desc()).all()

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

            # Merge structured data (newer data overwrites older for same fields)
            valid_fields = highlight.valid_structured_fields
            for key, value in valid_fields.items():
                if key not in consolidated_structured:  # Only add if we don't have this field yet
                    consolidated_structured[key] = value

        # Combine unstructured notes
        combined_notes = " | ".join(all_notes) if all_notes else ""

        return {
            "structured_data": consolidated_structured,
            "unstructured_notes": combined_notes,
            "source_conversations": list(set(conversation_ids)),  # Remove duplicates
            "last_updated": highlights[0].extracted_at if highlights else None,
            "total_highlights": len(highlights)
        }

    def __repr__(self):
        field_count = len(self.valid_structured_fields)
        has_notes = bool(self.unstructured_notes and self.unstructured_notes.strip())
        return f"<Highlight(user_id={self.user_id}, conv_id={self.conversation_id}, fields={field_count}, notes={has_notes})>"


class ExternalContext(Base):
    """External data like weather, air quality, etc."""
    __tablename__ = "external_context"

    id = Column(Integer, primary_key=True, index=True)
    context_type = Column(String(50), index=True)
    location = Column(String(100), index=True)
    data = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<ExternalContext(type={self.context_type}, location={self.location})>"


class KnowledgeBase(Base):
    """Health knowledge base for advanced insights"""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(100), index=True)
    content = Column(Text)
    source = Column(String(200))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<KnowledgeBase(topic={self.topic}, source={self.source})>"


# Database connection and session management
class DatabaseManager:
    """Handles database connections and session management"""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            session = self.get_session()
            session.execute("SELECT 1")
            session.close()
            return True
        except Exception:
            return False


# Convenience functions
def get_db_session() -> Session:
    """Get a database session (convenience function)"""
    db_manager = DatabaseManager()
    return db_manager.get_session()


def init_database():
    """Initialize database tables"""
    db_manager = DatabaseManager()
    db_manager.create_tables()
    print("Database tables created successfully!")
