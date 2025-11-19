"""Test AgentPipeline - Verify CLI contract implementation."""

from src.pipeline import AgentPipeline


class MockBackend:
    """Mock LLM backend for testing."""

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history=None,
        timeout=None,
        max_output_tokens=None,
    ) -> str:
        """Mock response generation."""
        return f"[MOCK] Responding to: {user_prompt[:50]}..."


class MockBackendManager:
    """Mock backend manager for testing."""

    def __init__(self):
        self.backends = [
            {
                'interface': MockBackend(),
                'name': 'mock',
                'label': 'Mock Backend',
                'type': 'test',
            }
        ]


def test_agent_pipeline_basic():
    """Test basic AgentPipeline functionality."""
    print("=" * 60)
    print("TEST: AgentPipeline Basic Functionality")
    print("=" * 60)

    # Initialize
    backend_manager = MockBackendManager()
    pipeline = AgentPipeline(
        backend_manager=backend_manager,
        system_prompt="You are a helpful test assistant."
    )

    print("✓ AgentPipeline initialized")

    # Test run()
    response = pipeline.run("What is Python?")
    print(f"\n✓ run() returned: {response}")

    # Test run() again (with history)
    response2 = pipeline.run("Can you elaborate?")
    print(f"✓ run() with history: {response2}")

    # Check conversation history
    print(f"\n✓ Conversation history length: {len(pipeline.conversation_history)}")
    assert len(pipeline.conversation_history) == 4, "Should have 4 messages (2 exchanges)"

    # Test clear_memory_global()
    pipeline.clear_memory_global()
    print("✓ clear_memory_global() executed")

    # Verify memory cleared
    print(f"✓ History after clear: {len(pipeline.conversation_history)}")
    assert len(pipeline.conversation_history) == 0, "History should be empty"

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)


def test_agent_pipeline_contract():
    """Verify AgentPipeline satisfies CLI contract."""
    print("\n" + "=" * 60)
    print("TEST: CLI Contract Verification")
    print("=" * 60)

    backend_manager = MockBackendManager()

    # Test 1: Constructor signature
    pipeline = AgentPipeline(backend_manager)
    print("✓ Constructor accepts backend_manager")

    pipeline_with_prompt = AgentPipeline(
        backend_manager,
        system_prompt="Custom prompt"
    )
    print("✓ Constructor accepts system_prompt")

    # Test 2: run() method exists and works
    assert hasattr(pipeline, 'run'), "Missing run() method"
    result = pipeline.run("Test input")
    assert isinstance(result, str), "run() must return string"
    print(f"✓ run() method works, returns string: {result[:50]}...")

    # Test 3: clear_memory_global() method exists
    assert hasattr(pipeline, 'clear_memory_global'), "Missing clear_memory_global() method"
    pipeline.clear_memory_global()
    print("✓ clear_memory_global() method exists and works")

    print("\n" + "=" * 60)
    print("✅ CLI CONTRACT SATISFIED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_agent_pipeline_basic()
        test_agent_pipeline_contract()

        print("\n" + "🎉 " * 20)
        print("SUCCESS: AgentPipeline ready for CLI integration!")
        print("🎉 " * 20)

    except Exception as exc:
        print("\n" + "❌ " * 20)
        print(f"TEST FAILED: {exc}")
        print("❌ " * 20)
        raise
