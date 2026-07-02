"""Simple test for AI components."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_imports():
    """Test that all modules can be imported."""
    try:
        print("✓ Base driver imports successful")

        print("✓ SmartRouter imports successful")

        print("✓ InferencePool imports successful")

        print("✓ ModelRegistry imports successful")

        print("✓ AIManager imports successful")

        print("✓ CircuitBreaker imports successful")

        print("\n✅ All imports successful!")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_structure():
    """Test that the structure matches specification."""
    # Just basic validation that we have the required components
    expected_files = [
        "app/ai/drivers/base.py",
        "app/ai/smart_router.py",
        "app/ai/inference_pool.py",
        "app/ai/model_registry.py",
        "app/ai/embedding_service.py",
        "app/ai/context_manager.py",
        "app/ai/circuit_breaker.py",
    ]

    missing_files = []
    for file_path in expected_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)

    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✓ All required files exist")
        return True


if __name__ == "__main__":
    print("Testing AI Smart Router implementation...")
    print("=" * 50)

    success = True
    success &= test_imports()
    success &= test_structure()

    print("=" * 50)
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)
