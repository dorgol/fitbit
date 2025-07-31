"""
Debug Tool for Conversation Memory Issues

This script helps identify where the conversation memory is breaking:
1. Frontend session state
2. Backend conversation orchestrator
3. Database storage
4. Context assembly
"""

import sys
sys.path.append('src')

from memory.database import get_db_session, User, Conversation
from core.conversation_orchestrator import chat_with_user, create_conversation_orchestrator
from core.context_assembly import ContextAssembler
import json

def test_frontend_session_simulation():
    """Simulate what the frontend should be doing"""
    print("=== FRONTEND SESSION SIMULATION ===")

    # Simulate user selection
    user_id = "1"  # Assuming user 1 exists

    # Simulate session state (like Streamlit would have)
    session_state = {
        'conversation_history': {user_id: []},
        'conversation_id': {user_id: None}
    }

    print(f"Initial session state for user {user_id}:")
    print(f"  History: {session_state['conversation_history'][user_id]}")
    print(f"  Conv ID: {session_state['conversation_id'][user_id]}")

    # Simulate first message
    message1 = "How did I sleep last night?"
    print(f"\n--- Sending message 1: '{message1}' ---")

    result1 = chat_with_user(user_id, message1, session_state['conversation_id'][user_id])

    # Update session state (like frontend should)
    session_state['conversation_history'][user_id].append({'role': 'user', 'content': message1})
    session_state['conversation_history'][user_id].append({'role': 'assistant', 'content': result1['response']})
    session_state['conversation_id'][user_id] = result1['conversation_id']

    print(f"Result 1: {result1['response'][:100]}...")
    print(f"Conv ID after message 1: {result1['conversation_id']}")
    print(f"Session history length: {len(session_state['conversation_history'][user_id])}")

    # Simulate second message
    message2 = "What about my steps yesterday?"
    print(f"\n--- Sending message 2: '{message2}' ---")

    # This is the KEY TEST - does it remember the first message?
    result2 = chat_with_user(user_id, message2, session_state['conversation_id'][user_id])

    print(f"Result 2: {result2['response'][:100]}...")
    print(f"Conv ID after message 2: {result2['conversation_id']}")

    # Update session state
    session_state['conversation_history'][user_id].append({'role': 'user', 'content': message2})
    session_state['conversation_history'][user_id].append({'role': 'assistant', 'content': result2['response']})

    print(f"Final session history length: {len(session_state['conversation_history'][user_id])}")

    return session_state, result1, result2

def test_database_conversation_storage():
    """Check if conversations are being stored correctly in database"""
    print("\n=== DATABASE CONVERSATION STORAGE TEST ===")

    session = get_db_session()
    try:
        # Get recent conversations
        conversations = session.query(Conversation).order_by(Conversation.created_at.desc()).limit(3).all()

        print(f"Found {len(conversations)} recent conversations:")

        for conv in conversations:
            print(f"\nConversation {conv.id}:")
            print(f"  User ID: {conv.user_id}")
            print(f"  Status: {conv.status}")
            print(f"  Message count: {len(conv.messages or [])}")
            print(f"  Created: {conv.created_at}")

            if conv.messages:
                print("  Messages:")
                for i, msg in enumerate(conv.messages):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:50] + "..." if len(msg.get('content', '')) > 50 else msg.get('content', '')
                    print(f"    {i+1}. {role}: {content}")
            else:
                print("  No messages found!")

    finally:
        session.close()

def test_conversation_orchestrator_directly():
    """Test the conversation orchestrator without frontend"""
    print("\n=== DIRECT CONVERSATION ORCHESTRATOR TEST ===")

    user_id = "1"
    orchestrator = create_conversation_orchestrator()

    print("Testing conversation continuity...")

    # First message
    print(f"\n--- Message 1 ---")
    result1 = orchestrator.chat(user_id, "How did I sleep last night?")
    print(f"Response 1: {result1['response'][:100]}...")
    print(f"Conversation ID: {result1['conversation_id']}")
    print(f"Error: {result1.get('error')}")

    # Second message with conversation ID
    print(f"\n--- Message 2 (with conversation ID) ---")
    result2 = orchestrator.chat(user_id, "What about my heart rate?", conversation_id=result1['conversation_id'])
    print(f"Response 2: {result2['response'][:100]}...")
    print(f"Conversation ID: {result2['conversation_id']}")
    print(f"Error: {result2.get('error')}")

    # Check if second response references first message context
    if "sleep" in result2['response'].lower() or "previous" in result2['response'].lower():
        print("✅ Conversation appears to have memory!")
    else:
        print("❌ Conversation appears to have no memory of previous message")

    return result1, result2

def test_context_assembly():
    """Test if context assembly includes conversation history"""
    print("\n=== CONTEXT ASSEMBLY TEST ===")

    user_id = 1
    assembler = ContextAssembler()

    try:
        context_result = assembler.get_conversation_context(user_id)
        context = context_result['context']
        system_prompt = context_result['system_prompt']

        print(f"Context keys: {list(context.keys())}")
        print(f"System prompt length: {len(system_prompt)}")

        # Check highlights (conversation memory)
        highlights = context.get('highlights', {})
        if highlights:
            print(f"Highlights found: {highlights.get('structured_data', {}).keys()}")
            print(f"Unstructured notes: {highlights.get('unstructured_notes', 'None')[:100]}...")
        else:
            print("No highlights found - this might be the issue!")

        # Check if system prompt mentions conversation history
        if "conversation" in system_prompt.lower() or "previous" in system_prompt.lower():
            print("✅ System prompt appears to include conversation context")
        else:
            print("❌ System prompt may not include conversation context")

    except Exception as e:
        print(f"Error in context assembly: {e}")

def inspect_langgraph_state():
    """Try to inspect what's happening in the LangGraph workflow"""
    print("\n=== LANGGRAPH WORKFLOW INSPECTION ===")

    # This is tricky since LangGraph workflow is internal
    # But we can check if the orchestrator is loading conversation history

    session = get_db_session()
    try:
        # Get a conversation with multiple messages
        conversation = session.query(Conversation).filter(
            Conversation.messages.isnot(None)
        ).first()

        if conversation and len(conversation.messages or []) > 2:
            print(f"Found conversation {conversation.id} with {len(conversation.messages)} messages")

            # The question is: does the orchestrator pass these messages to the LLM?
            print("Checking if messages are properly formatted for LLM...")

            messages = conversation.messages
            llm_format_messages = []

            for msg in messages:
                if msg.get('role') and msg.get('content'):
                    llm_format_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

            print(f"LLM-formatted messages: {len(llm_format_messages)}")
            for i, msg in enumerate(llm_format_messages):
                print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")

            if len(llm_format_messages) >= 2:
                print("✅ Conversation history exists and is properly formatted")
            else:
                print("❌ Conversation history is missing or malformed")
        else:
            print("No multi-message conversations found to inspect")

    finally:
        session.close()

def main():
    """Run all debug tests"""
    print("🔍 CONVERSATION MEMORY DEBUG TOOL")
    print("=" * 50)

    # Test 1: Simulate what frontend should do
    try:
        session_state, result1, result2 = test_frontend_session_simulation()
    except Exception as e:
        print(f"Frontend simulation failed: {e}")

    # Test 2: Check database storage
    try:
        test_database_conversation_storage()
    except Exception as e:
        print(f"Database test failed: {e}")

    # Test 3: Test orchestrator directly
    try:
        test_conversation_orchestrator_directly()
    except Exception as e:
        print(f"Orchestrator test failed: {e}")

    # Test 4: Check context assembly
    try:
        test_context_assembly()
    except Exception as e:
        print(f"Context assembly test failed: {e}")

    # Test 5: Inspect LangGraph workflow
    try:
        inspect_langgraph_state()
    except Exception as e:
        print(f"LangGraph inspection failed: {e}")

    print("\n" + "=" * 50)
    print("🔍 DEBUG COMPLETE")
    print("\nKey things to check:")
    print("1. Are conversations being stored in database with multiple messages?")
    print("2. Is the conversation_id being passed correctly between messages?")
    print("3. Is the LangGraph workflow loading conversation history?")
    print("4. Is the conversation history being passed to the LLM?")
    print("5. Is the frontend maintaining conversation_id across messages?")

if __name__ == "__main__":
    main()