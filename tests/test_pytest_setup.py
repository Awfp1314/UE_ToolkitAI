"""
Test to verify pytest setup is working correctly.
"""
import pytest


def test_basic_assertion():
    """Test basic assertion works."""
    assert 1 + 1 == 2


def test_string_operations():
    """Test string operations."""
    text = "Hello, World!"
    assert "Hello" in text
    assert text.startswith("Hello")
    assert text.endswith("!")


@pytest.mark.unit
def test_with_marker():
    """Test with unit marker."""
    assert True


class TestClass:
    """Test class for grouping tests."""
    
    def test_method_one(self):
        """Test method one."""
        assert 2 * 2 == 4
    
    def test_method_two(self):
        """Test method two."""
        assert 3 * 3 == 9


@pytest.fixture
def sample_data():
    """Fixture providing sample data."""
    return {"name": "Test", "value": 42}


def test_with_fixture(sample_data):
    """Test using fixture."""
    assert sample_data["name"] == "Test"
    assert sample_data["value"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

