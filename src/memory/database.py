"""
Database models and connection management

SQLAlchemy models for all database tables and database session management.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import sessionmaker, relationship, Session, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fitbit_ai_poc.db")

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    age = Column(Integer)
    gender = Column(String(10))
    location = Column(String(100))
    goals = Column(JSON)
    preferences = Column(JSON)

    health_metrics = relationship("HealthMetric", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    insights = relationship("Insight", back_populates="user")
    highlights = relationship("Highlight", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, location={self.location})>"


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    metric_type = Column(String(50), index=True)
    value = Column(Float)
    timestamp = Column(DateTime, index=True)
    extra_data = Column(JSON)

    user = relationship("User", back_populates="health_metrics")

    def __repr__(self):
        return f"<HealthMetric(user_id={self.user_id}, type={self.metric_type}, value={self.value})>"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    session_id = Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)
    messages = Column(JSON)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="conversations")
    highlights = relationship("Highlight", back_populates="conversation")

    def __repr__(self):
        return f"<Conversation(user_id={self.user_id}, status={self.status}, messages={len(self.messages or [])})>"


class Insight(Base):
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

    user = relationship("User", back_populates="insights")

    def __repr__(self):
        return f"<Insight(user_id={self.user_id}, category={self.category}, confidence={self.confidence})>"


class Highlight(Base):
    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    structured_data = Column(JSON)
    unstructured_notes = Column(Text)
    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="highlights")
    conversation = relationship("Conversation", back_populates="highlights")

    def __repr__(self):
        return f"<Highlight(user_id={self.user_id}, conv_id={self.conversation_id}, fields={len(self.structured_data or {})})>"


class ExternalContext(Base):
    __tablename__ = "external_context"

    id = Column(Integer, primary_key=True, index=True)
    context_type = Column(String(50), index=True)
    location = Column(String(100), index=True)
    data = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<ExternalContext(type={self.context_type}, location={self.location})>"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(100), index=True)
    content = Column(Text)
    source = Column(String(200))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<KnowledgeBase(topic={self.topic}, source={self.source})>"


class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created (if not already existing)")

    def drop_tables(self):
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("All database tables dropped")

    def get_session(self) -> Session:
        logger.debug("Creating new DB session")
        return self.SessionLocal()

    def health_check(self) -> bool:
        try:
            session = self.get_session()
            session.execute("SELECT 1")
            session.close()
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}", exc_info=True)
            return False


@contextmanager
def db_session_scope():
    session = DatabaseManager().get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Session rolled back due to error", exc_info=True)
        raise
    finally:
        session.close()


def get_db_session() -> Session:
    return DatabaseManager().get_session()


def init_database():
    db_manager = DatabaseManager()
    db_manager.create_tables()
    print("[✓] Database initialized.")
