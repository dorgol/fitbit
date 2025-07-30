"""
Test script for LLM Factory functionality
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append('src')

from src.api.llm_factory import LLMFactory, get_llm_client, test_all_providers
from src.api.llm_interface import LLMError


def test_factory_basic():
    """Test basic factory functionality"""
    print("Testing LLM Factory basic functionality...")

    try:
        # Test creating Claude client directly
        claude = LLMFactory.create_client("claude")
        print(f"✓ Created Claude client: {claude}")

        # Test unknown provider
        try:
            unknown = LLMFactory.create_client("unknown_provider")
            print("✗ Should have failed with unknown provider")
        except LLMError as e:
            print(f"✓ Correctly rejected unknown provider: {e.message}")

        # Test default client
        default = LLMFactory.get_default_client()
        print(f"✓ Got default client: {default}")

        return True

    except Exception as e:
        print(f"✗ Factory test failed: {e}")
        return False


def test_fallback_logic():
    """Test fallback functionality"""
    print("\nTesting fallback logic...")

    try:
        # Test with Claude as primary (should work)
        client = LLMFactory.create_client_with_fallback("claude", [])
        print(f"✓ Created client with fallback: {client}")

        # Test with unknown primary, Claude as fallback
        print("Testing unknown primary with Claude fallback...")
        # This should print warnings but return Claude client
        client = LLMFactory.create_client_with_fallback("unknown", ["claude"])
        print(f"✓ Fallback worked, got: {client}")

        return True

    except Exception as e:
        print(f"✗ Fallback test failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions"""
    print("\nTesting convenience functions...")

    try:
        # Test get_llm_client
        client1 = get_llm_client(with_fallback=True)
        client2 = get_llm_client(with_fallback=False)

        print(f"✓ Got client with fallback: {client1}")
        print(f"✓ Got client without fallback: {client2}")

        # Test actual conversation
        print("\nTesting actual conversation...")
        response = client1.chat("Hello! Just testing the factory.")
        print(f"✓ Conversation works: {response[:50]}...")

        return True

    except Exception as e:
        print(f"✗ Convenience function test failed: {e}")
        return False


def test_provider_status():
    """Test provider status checking"""
    print("\nTesting provider status...")

    try:
        status = test_all_providers()
        print("Provider status:")
        for provider, info in status.items():
            status_text = "✓ Available" if info["available"] else "✗ Unavailable"
            print(f"  {provider}: {status_text}")
            if info["error"]:
                print(f"    Error: {info['error']}")

        return True

    except Exception as e:
        print(f"✗ Provider status test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("LLM FACTORY TEST")
    print("=" * 50)

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("✗ No ANTHROPIC_API_KEY found")
        sys.exit(1)

    all_passed = True

    all_passed &= test_factory_basic()
    all_passed &= test_fallback_logic()
    all_passed &= test_convenience_functions()
    all_passed &= test_provider_status()

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All factory tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)