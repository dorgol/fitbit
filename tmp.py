"""
Test script for highlights extraction system
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add src to path
sys.path.append('src')

from src.memory.database import DatabaseManager, User, Conversation, Highlight, get_db_session
from src.memory.highlights import HighlightsExtractor


def test_highlights_extraction():
    """Test the highlights extraction process"""
    print("=== TESTING HIGHLIGHTS EXTRACTION ===\n")

    extractor = HighlightsExtractor()

    # Check for existing conversations
    session = get_db_session()
    try:
        conversations = session.query(Conversation).filter(
            Conversation.status == "completed"
        ).all()

        if not conversations:
            print("No completed conversations found. Need to create some test conversations first.")
            return

        print(f"Found {len(conversations)} completed conversations to test")

        # Test individual conversation processing
        for i, conversation in enumerate(conversations[:2]):  # Test first 2
            print(f"\n--- Testing Conversation {conversation.id} (User {conversation.user_id}) ---")

            # Show the conversation content
            print("Conversation content:")
            for msg in conversation.messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", "")
                print(f"  {role.capitalize()}: {content}")

            # Extract highlights
            try:
                highlights = extractor.extract_highlights_from_conversation(conversation.id)

                if highlights:
                    print(f"\n✓ Extracted highlights:")
                    print(f"Structured data: {json.dumps(highlights['structured_data'], indent=2)}")
                    print(f"Unstructured notes: {highlights['unstructured_notes']}")

                    # Store highlights
                    success = extractor.store_highlights(conversation.id, conversation.user_id, highlights)
                    if success:
                        print("✓ Stored highlights in database")
                    else:
                        print("✗ Failed to store highlights")
                else:
                    print("✗ No highlights extracted")

            except Exception as e:
                print(f"✗ Error processing conversation: {e}")

            print("\n" + "="*50)

    finally:
        session.close()


def test_batch_processing():
    """Test batch processing of all conversations"""
    print("\n=== TESTING BATCH PROCESSING ===\n")

    extractor = HighlightsExtractor()

    try:
        results = extractor.process_all_completed_conversations()
        print(f"Batch processing results: {results}")

        # Show what's now in the database
        session = get_db_session()
        try:
            highlights = session.query(Highlight).all()
            print(f"\nTotal highlights in database: {len(highlights)}")

            for highlight in highlights:
                print(f"\nUser {highlight.user_id}, Conversation {highlight.conversation_id}:")
                print(f"  Structured: {highlight.structured_data}")
                print(f"  Notes: {highlight.unstructured_notes}")
                print(f"  Extracted: {highlight.extracted_at}")

        finally:
            session.close()

    except Exception as e:
        print(f"✗ Batch processing error: {e}")


def test_user_summary():
    """Test getting consolidated user highlights"""
    print("\n=== TESTING USER HIGHLIGHTS SUMMARY ===\n")

    extractor = HighlightsExtractor()
    session = get_db_session()

    try:
        users = session.query(User).all()

        for user in users[:2]:  # Test first 2 users
            print(f"\n--- User {user.id} Highlights Summary ---")

            summary = extractor.get_user_highlights_summary(user.id)

            print(f"Consolidated structured data:")
            for key, value in summary["structured_data"].items():
                if value:
                    print(f"  {key}: {value}")

            print(f"\nCombined notes: {summary['unstructured_notes']}")
            print(f"Source conversations: {summary['source_conversations']}")
            print(f"Last updated: {summary['last_updated']}")

    finally:
        session.close()


def create_test_conversation():
    """Create a richer test conversation for better highlight extraction"""
    print("\n=== CREATING RICH TEST CONVERSATION ===\n")

    session = get_db_session()

    try:
        # Get first user
        user = session.query(User).first()
        if not user:
            print("No users found")
            return

        # Create a conversation with more detailed health context
        rich_conversation = Conversation(
            user_id=user.id,
            messages=[
                {
                    "role": "user",
                    "content": "I'm having trouble sleeping lately. I usually go to bed around 11 PM but I work late shifts that end at 10 PM.",
                    "timestamp": "2025-01-15T09:00:00Z"
                },
                {
                    "role": "assistant",
                    "content": "I understand late shifts can make it challenging to wind down. What time do you typically need to wake up for work?",
                    "timestamp": "2025-01-15T09:00:05Z"
                },
                {
                    "role": "user",
                    "content": "I wake up at 6 AM usually. Also, I'm allergic to dairy and I've been stressed about a big project at work. I prefer doing yoga for exercise but haven't had time lately.",
                    "timestamp": "2025-01-15T09:01:00Z"
                },
                {
                    "role": "assistant",
                    "content": "That's quite a short sleep window with your schedule. Yoga is excellent for stress relief and better sleep. Have you considered doing some gentle stretches before bed to help transition from work stress?",
                    "timestamp": "2025-01-15T09:01:10Z"
                },
                {
                    "role": "user",
                    "content": "That's a good idea. I'm also trying to hit 10,000 steps daily as my main fitness goal. My doctor mentioned I should track my heart rate too because of family history of heart disease.",
                    "timestamp": "2025-01-15T09:02:00Z"
                },
                {
                    "role": "assistant",
                    "content": "Great goals! With your family history, tracking heart rate is wise. Since you prefer yoga, we could explore ways to integrate more movement into your day that works with your late shift schedule.",
                    "timestamp": "2025-01-15T09:02:15Z"
                }
            ],
            status="completed",
            ended_at=datetime.now(timezone.utc)
        )

        session.add(rich_conversation)
        session.commit()

        print(f"✓ Created rich test conversation with ID {rich_conversation.id}")
        print("This conversation includes:")
        print("- Work schedule details (late shifts, 10 PM end)")
        print("- Sleep schedule (11 PM bedtime, 6 AM wake)")
        print("- Allergies (dairy)")
        print("- Stress sources (work project)")
        print("- Exercise preferences (yoga)")
        print("- Health concerns (family heart disease history)")
        print("- Goals (10k steps daily)")

        return rich_conversation.id

    except Exception as e:
        session.rollback()
        print(f"✗ Error creating test conversation: {e}")
        return None
    finally:
        session.close()


if __name__ == "__main__":
    # Create a rich test conversation first
    conversation_id = create_test_conversation()

    if conversation_id:
        print(f"\nNow testing highlights extraction on conversation {conversation_id}...")

        # Test the extraction specifically on our rich conversation
        extractor = HighlightsExtractor()
        highlights = extractor.extract_highlights_from_conversation(conversation_id)

        if highlights:
            print(f"\n✓ Successfully extracted highlights from rich conversation:")
            print(json.dumps(highlights, indent=2))
        else:
            print("✗ Failed to extract highlights from rich conversation")

    # Run all tests
    test_highlights_extraction()
    test_batch_processing()
    test_user_summary()

    print("\n=== HIGHLIGHTS TESTING COMPLETE ===")
    print("If you see extracted highlights above, the system is working!")