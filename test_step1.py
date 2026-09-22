"""Runner for Step 1 ingestion test."""
import sys
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["-q", "tests/test_step1.py"]))
