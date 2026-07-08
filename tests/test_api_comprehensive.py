"""
Comprehensive tests for api.py to improve coverage.
"""
import json
import os
import secrets
import tempfile
from unittest.mock import patch

import pytest

# Add src to path
import sys
sys.path.insert(0, 'src')

from api import (
    Config,
    KnowledgeBase,
    StadiumGraph,
    create_access_token,
    verify_token,
    determine_target_type
)


def test_validate_production_config_with_missing_secret():
    """Test validate_production_config raises error when SECRET_KEY is missing in production."""
    # Save original env vars
    original_env = dict(os.environ)

    try:
        # Set environment to production
        os.environ["ENVIRONMENT"] = "production"
        # Remove SECRET_KEY if it exists
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]

        # Should raise ValueError
        with pytest.raises(ValueError, match="Missing required environment variables for production"):
            Config.validate_production_config()
    finally:
        # Restore env
        os.environ.clear()
        os.environ.update(original_env)


def test_validate_production_config_with_default_secret():
    """Test validate_production_config raises error when using default SECRET_KEY in production."""
    # Save original env vars
    original_env = dict(os.environ)

    try:
        # Set environment to production
        os.environ["ENVIRONMENT"] = "production"
        # Temporarily set SECRET_KEY to what would be the default
        original_secret = Config.SECRET_KEY
        Config.SECRET_KEY = secrets.token_hex(32)  # This simulates the default

        # Should raise ValueError
        with pytest.raises(ValueError, match="SECRET_KEY must be explicitly set in production"):
            Config.validate_production_config()

        # Restore
        Config.SECRET_KEY = original_secret
    finally:
        # Restore env
        os.environ.clear()
        os.environ.update(original_env)


def test_validate_production_config_valid():
    """Test validate_production_config passes with proper SECRET_KEY in production."""
    # Save original env vars
    original_env = dict(os.environ)

    try:
        # Set environment to production
        os.environ["ENVIRONMENT"] = "production"
        # Set a custom SECRET_KEY
        os.environ["SECRET_KEY"] = "test-secret-key-for-testing-purposes-only"

        # Should not raise
        Config.validate_production_config()  # Should not raise exception
    finally:
        # Restore env
        os.environ.clear()
        os.environ.update(original_env)


def test_validate_production_config_non_production():
    """Test validate_production_config does nothing in non-production environments."""
    # Save original env vars
    original_env = dict(os.environ)

    try:
        # Set environment to development
        os.environ["ENVIRONMENT"] = "development"
        # Remove SECRET_KEY
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]

        # Should not raise
        Config.validate_production_config()  # Should not raise exception
    finally:
        # Restore env
        os.environ.clear()
        os.environ.update(original_env)


def test_knowledge_base_load_fallback_on_file_not_found():
    """Test KnowledgeBase uses fallback when file is not found."""
    # Should not raise exception, should use fallback
    kb = KnowledgeBase('/non/existent/file.json')
    # Should have fallback chunks
    assert len(kb.chunks) >= 5  # There are 5 fallback chunks
    assert any(chunk.get('id') == 'fallback_1' for chunk in kb.chunks)


def test_knowledge_base_load_valid_file():
    """Test KnowledgeBase loads valid JSON file correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([
            {"id": "test1", "text": "First test chunk"},
            {"id": "test2", "text": "Second test chunk"}
        ], f)
        temp_file = f.name

    try:
        # Should load the file successfully
        kb = KnowledgeBase(temp_file)
        # Should have the loaded chunks
        assert len(kb.chunks) == 2
        assert kb.chunks[0]['text'] == "First test chunk"
        assert kb.chunks[1]['text'] == "Second test chunk"
        # Should have extracted texts
        assert len(kb.chunk_texts) == 2
        assert "First test chunk" in kb.chunk_texts
        assert "Second test chunk" in kb.chunk_texts
    finally:
        os.unlink(temp_file)


def test_knowledge_base_load_json_decode_error():
    """Test KnowledgeBase handles JSON decode error by propagating it."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": json content}')  # Invalid JSON
        temp_file = f.name

    try:
        # Should raise JSONDecodeError which is NOT caught, so it will propagate
        # Only FileNotFoundError is caught in the actual code
        with pytest.raises(json.JSONDecodeError):
            KnowledgeBase(temp_file)
    finally:
        os.unlink(temp_file)


def test_knowledge_base_load_missing_text_field():
    """Test KnowledgeBase handles missing 'text' field."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('[{"id": "test1", "text": "Test"}, {"id": "test2"}]')  # Missing 'text' in second object
        temp_file = f.name

    try:
        # Should raise KeyError when trying to access 'text' key
        with pytest.raises(KeyError, match="'text'"):
            KnowledgeBase(temp_file)
    finally:
        os.unlink(temp_file)


def test_knowledge_base_load_empty_array():
    """Test KnowledgeBase with empty array."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([], f)
        temp_file = f.name

    try:
        # Should work with empty array
        kb = KnowledgeBase(temp_file)
        assert len(kb.chunks) == 0
        assert len(kb.chunk_texts) == 0
        assert len(kb.chunk_ids) == 0
    finally:
        os.unlink(temp_file)


def test_knowledge_base_retrieve_empty_query():
    """Test retrieving chunks with empty query."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([
            {"id": "1", "text": "First chunk"},
            {"id": "2", "text": "Second chunk"}
        ], f)
        temp_file = f.name

    try:
        kb = KnowledgeBase(temp_file)
        # Empty query should return first k chunks
        result = kb.retrieve_relevant_chunks("", k=1)
        assert len(result) == 1
        assert result[0] == "First chunk"

        result = kb.retrieve_relevant_chunks("", k=2)
        assert len(result) == 2
        assert result[0] == "First chunk"
        assert result[1] == "Second chunk"
    finally:
        os.unlink(temp_file)


def test_knowledge_base_retrieve_no_matches():
    """Test retrieving chunks when no terms match."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([
            {"id": "1", "text": "apple banana cherry"},
            {"id": "2", "text": "date elderberry fig"}
        ], f)
        temp_file = f.name

    try:
        kb = KnowledgeBase(temp_file)
        # Query with no matching terms
        result = kb.retrieve_relevant_chunks("xyz qwerty", k=1)
        # Should return empty list since no matches and score > 0 filter
        # Looking at the code: return [chunk for score, chunk in scored_chunks[:k] if score > 0] or self.chunk_texts[:k]
        # If all scores are 0, the first part is empty, so it falls back to self.chunk_texts[:k]
        assert len(result) == 1
        assert result[0] == "apple banana cherry"
    finally:
        os.unlink(temp_file)


def test_knowledge_base_retrieve_partial_matches():
    """Test retrieving chunks with partial matches."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([
            {"id": "1", "text": "restroom location"},
            {"id": "2", "text": "concession stand food"}
        ], f)
        temp_file = f.name

    try:
        kb = KnowledgeBase(temp_file)
        # Query matching first chunk
        result = kb.retrieve_relevant_chunks("restroom", k=1)
        assert len(result) == 1
        assert result[0] == "restroom location"
    finally:
        os.unlink(temp_file)


def test_stadium_graph_load_failure():
    """Test StadiumGraph handles graph loading failure gracefully."""
    # Should not raise exception even if file doesn't exist
    sg = StadiumGraph('/non/existent/file.gexf')
    # Should have initialized attributes
    assert sg.G is not None  # NetworkX creates empty graph on failure
    assert isinstance(sg.edge_congestion, dict)
    assert isinstance(sg._valid_nodes, set)


def test_determine_target_type_comprehensive():
    """Test determine_target_type with various inputs."""
    # Test each category
    assert determine_target_type("restroom") == "restroom"
    assert determine_target_type("bathrooms") == "restroom"
    assert determine_target_type("toilet") == "restroom"
    assert determine_target_type("washroom") == "restroom"

    assert determine_target_type("food") == "concession"
    assert determine_target_type("drinks") == "concession"
    assert determine_target_type("concessions") == "concession"
    # Note: "eat" is in food_words, so "eating" should match
    assert determine_target_type("eating") == "concession"  # "eat" + "ing" still matches "eat"

    assert determine_target_type("medical") == "medical"
    assert determine_target_type("help") == "medical"
    assert determine_target_type("emergency") == "medical"

    assert determine_target_type("section") == "section"
    # Checking section_words from code: ["section", "seat", "seats", "sit", "sitting", "row", "rows"]
    assert determine_target_type("seat") == "section"
    assert determine_target_type("rows") == "section"

    # Test that order matters - sections checked first
    # If a word matches multiple categories, the first match wins
    # There's no overlap between the word lists, so this is just to verify

    # Test no match
    assert determine_target_type("hello world") is None
    assert determine_target_type("") is None
    assert determine_target_type("   ") is None
    assert determine_target_type("xyz") is None


def test_create_access_token_custom_expiration():
    """Test create_access_token with custom expiration time."""
    from datetime import timedelta

    data = {"sub": "testuser", "role": "admin"}
    # 5 minute expiration
    expires = timedelta(minutes=5)
    token = create_access_token(data, expires_delta=expires)

    assert isinstance(token, str)
    # Should be a valid JWT
    assert token.count(".") == 2

    # Decode and check expiration is set
    import jwt
    try:
        # Decode without verification for testing
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded["exp"]
        # Should be a future timestamp
        assert exp > 0
    except jwt.JWTError:
        # If we can't decode, at least verify it's a string with 2 dots
        assert isinstance(token, str)
        assert token.count(".") == 2


def test_create_access_token_default_expiration():
    """Test create_access_token uses default expiration when none provided."""
    data = {"sub": "testuser"}

    token = create_access_token(data)

    assert isinstance(token, str)
    assert token.count(".") == 2

    # Decode and check
    import jwt
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded["exp"]
        iat = decoded.get("iat", 0)  # issued at time
        # Should be approximately ACCESS_TOKEN_EXPIRE_MINUTES minutes from now
        # We'll just check it's a reasonable future time
        assert exp > iat
        diff = exp - iat
        # Should be close to 30 minutes (default)
        assert 25 * 60 <= diff <= 35 * 60  # Between 25-35 minutes
    except jwt.JWTError:
        assert isinstance(token, str)
        assert token.count(".") == 2


def test_create_access_token_exception_handling():
    """Test create_access_token handles JWT encoding errors."""
    # Mock jwt.encode to raise an exception
    with patch('api.jwt.encode', side_effect=Exception("JWT encoding failed")):
        with pytest.raises(Exception, match="JWT encoding failed"):
            create_access_token({"sub": "test"})


def test_verify_token_invalid_token():
    """Test verify_token with invalid token."""
    # Should return None for invalid token
    result = verify_token("invalid.token.here")
    assert result is None


def test_verify_token_expired_token():
    """Test verify_token with expired token."""
    # Create an expired token
    from datetime import datetime, timedelta
    import jwt

    # Set expiration to 1 hour ago
    exp_time = datetime.now() - timedelta(hours=1)
    payload = {"sub": "testuser", "exp": exp_time}
    # Use a dummy secret for encoding
    token = jwt.encode(payload, "secret", algorithm="HS256")

    # Should return None for expired token (our verify returns None on any error)
    result = verify_token(token)
    assert result is None


def test_verify_token_valid_token():
    """Test verify_token with valid token."""
    from datetime import datetime, timedelta
    import jwt

    # Set expiration to 1 hour from now
    exp_time = datetime.now() + timedelta(hours=1)
    payload = {"sub": "testuser", "role": "admin", "exp": exp_time.timestamp()}
    # Use the actual secret from config
    token = jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")

    # Should return token data
    result = verify_token(token)
    assert result is not None
    assert hasattr(result, 'username')
    assert result.username == "testuser"


def test_verify_token_exception_during_decode():
    """Test verify_token handles exceptions during JWT decoding."""
    # Mock jwt.decode to raise an exception
    with patch('api.jwt.decode', side_effect=Exception("Decode failed")):
        # Should return None on any exception
        result = verify_token("any.token")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

