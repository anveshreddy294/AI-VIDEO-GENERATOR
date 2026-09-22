"""Runner for Step 2 diagnostic assessment test."""
import sys
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["-q", "tests/test_step2.py"]))
