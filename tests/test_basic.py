"""
Unit tests for FanWayfinder components
"""
import json
import tempfile
import os

# Import our modules
import sys
sys.path.insert(0, 'src')

from api import KnowledgeBase, determine_target_type


def test_knowledge_base_initialization():
    """Test that KnowledgeBase loads correctly."""
    # Create temporary KB file
    kb_data = [
        {"id": "test_1", "text": "Restrooms are near Gate A."},
        {"id": "test_2", "text": "Food is available at Concession 1."}
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(kb_data, f)
        kb_file = f.name

    try:
        kb = KnowledgeBase(kb_file)
        assert len(kb.chunks) == 2
        assert kb.chunk_texts == ["Restrooms are near Gate A.", "Food is available at Concession 1."]
        assert kb.chunk_ids == ["test_1", "test_2"]
    finally:
        os.unlink(kb_file)


def test_knowledge_base_fallback():
    """Test fallback when KB file is missing."""
    kb = KnowledgeBase("/non/existent/file.json")
    assert len(kb.chunks) > 0  # Should have fallback data
    assert any("restroom" in text.lower() for text in kb.chunk_texts)


def test_retrieve_relevant_chunks():
    """Test knowledge retrieval functionality."""
    kb_data = [
        {"id": "restroom", "text": "Restrooms are near Gate A and Gate C."},
        {"id": "food", "text": "Food concessions are near each gate."},
        {"id": "medical", "text": "Medical tents are near Gate A and Gate C."}
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(kb_data, f)
        kb_file = f.name

    try:
        kb = KnowledgeBase(kb_file)

        # Test exact match
        results = kb.retrieve_relevant_chunks("restroom")
        assert len(results) > 0
        assert any("restroom" in result.lower() for result in results)

        # Test partial match
        results = kb.retrieve_relevant_chunks("food gate")
        assert len(results) > 0

        # Test no match (should return first k results)
        results = kb.retrieve_relevant_chunks("xyzzyplugh")
        assert len(results) == 3  # Should return all chunks as fallback

    finally:
        os.unlink(kb_file)


def test_determine_target_type():
    """Test target type detection from queries."""
    # Test restroom detection
    assert determine_target_type("Where is the restroom?") == "restroom"
    assert determine_target_type("I need a bathroom") == "restroom"
    assert determine_target_type("Where's the toilet?") == "restroom"

    # Test food/concession detection
    assert determine_target_type("Where can I get food?") == "concession"
    assert determine_target_type("I'm hungry") == "concession"
    assert determine_target_type("Where are the concessions?") == "concession"

    # Test medical detection
    assert determine_target_type("Is there medical help?") == "medical"
    assert determine_target_type("I need first aid") == "medical"
    assert determine_target_type("Where is the medical tent?") == "medical"

    # Test section detection
    assert determine_target_type("Where is my section?") == "section"
    assert determine_target_type("Where are the seats?") == "section"

    # Test unknown query
    assert determine_target_type("What's the weather?") is None
    assert determine_target_type("Hello") is None


def test_determine_target_type_case_insensitive():
    """Test that target detection is case insensitive."""
    assert determine_target_type("WHERE IS THE RESTROOM?") == "restroom"
    assert determine_target_type("i NEED FOOD") == "concession"


if __name__ == "__main__":
    test_knowledge_base_initialization()
    test_knowledge_base_fallback()
    test_retrieve_relevant_chunks()
    test_determine_target_type()
    test_determine_target_type_case_insensitive()
    print("All tests passed!")
