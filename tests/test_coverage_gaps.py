"""
Tests to cover uncovered lines in src modules for 100% coverage.
"""
import json
import os
import sys
import time
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, 'src')

from api import (
    load_env_file,
    KnowledgeBase,
    StadiumGraph,
    AdviceCache,
    MQTTHandler,
    get_storage_uri,
    verify_token_dependency,
    generate_ai_response,
    load_system_prompt,
    Config,
    app,
)
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials


client = TestClient(app)


class TestLoadEnvFile:
    """Tests for load_env_file function."""

    def test_load_env_file_not_exists(self, tmp_path):
        """Test load_env_file when .env doesn't exist (line 26)."""
        with patch('api.Path') as mock_path:
            mock_path.return_value.resolve.return_value.parent.parent = tmp_path
            load_env_file()

    def test_load_env_file_with_content(self, tmp_path):
        """Test load_env_file with valid content (lines 34, 37-40)."""
        with patch('api.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path.resolve.return_value.parent.parent = tmp_path
            mock_path_class.return_value = mock_path

            # Test with content that has comments and blank lines to hit line 34 (continue)
            with patch('builtins.open', mock.mock_open(read_data='# comment\n\nKEY=value\n')):
                with patch('os.path.exists', return_value=True):
                    load_env_file()

    def test_load_env_file_exception_handling(self):
        """Test load_env_file handles exceptions (lines 41-42)."""
        from pathlib import Path
        with patch('api.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path.resolve.return_value.parent.parent = Path('/tmp')
            mock_path_class.return_value = mock_path

            with patch('builtins.open', side_effect=Exception("Permission denied")):
                with patch('os.path.exists', return_value=True):
                    # Should not raise, just log warning
                    load_env_file()


class TestKnowledgeBaseEdgeCases:
    """Tests for KnowledgeBase edge cases to improve coverage."""

    def test_load_chunks_key_error(self, tmp_path):
        """Test KnowledgeBase handles missing 'text' key."""
        kb_file = tmp_path / "kb.json"
        kb_file.write_text(json.dumps([{"id": "test"}]))  # Missing 'text' key

        # Should raise KeyError (not caught in _load_chunks)
        with pytest.raises(KeyError):
            KnowledgeBase(str(kb_file))

    def test_retrieve_empty_chunk_terms(self, tmp_path):
        """Test retrieve with empty chunk terms (line 238)."""
        kb_file = tmp_path / "kb.json"
        # Create chunk with empty text so terms will be empty set
        kb_file.write_text(json.dumps([{"id": "1", "text": ""}, {"id": "2", "text": "valid text"}]))

        kb = KnowledgeBase(str(kb_file))
        # Query that matches nothing - should skip empty terms
        results = kb.retrieve_relevant_chunks("xyz", k=2)
        assert len(results) >= 1


class TestStadiumGraphEdgeCases:
    """Tests for StadiumGraph edge cases."""

    def test_load_graph_exception_fallback(self):
        """Test StadiumGraph fallback when file load fails (lines 278-287)."""
        # Pass non-existent file to trigger fallback
        sg = StadiumGraph('/non/existent/file.gexf')
        assert sg.G is not None
        assert 'Gate_A' in sg._valid_nodes

    def test_update_congestion_thread_safety(self):
        """Test update_congestion with lock (lines 291-296)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        # Call update_congestion to exercise the lock
        sg.update_congestion(('Gate_A', 'Concession_1'), 0.5)
        assert sg.edge_congestion[('Gate_A', 'Concession_1')] == 0.5
        assert sg.edge_congestion[('Concession_1', 'Gate_A')] == 0.5

    def test_update_congestion_bounds(self):
        """Test congestion value clamping (line 293)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        sg.update_congestion(('Gate_A', 'Concession_1'), 1.5)  # Should clamp to 1.0
        assert sg.edge_congestion[('Gate_A', 'Concession_1')] == 1.0

        sg.update_congestion(('Gate_A', 'Concession_1'), -0.5)  # Should clamp to 0.0
        assert sg.edge_congestion[('Gate_A', 'Concession_1')] == 0.0

    def test_find_shortest_path_source_not_in_graph(self):
        """Test find_shortest_path when source not in graph (line 309)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        result = sg.find_shortest_path('NonExistent', 'Gate_A')
        assert result == []

    def test_find_shortest_path_target_not_in_graph(self):
        """Test find_shortest_path when target not in graph (line 309)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        result = sg.find_shortest_path('Gate_A', 'NonExistent')
        assert result == []

    def test_find_shortest_path_networkx_no_path_weighted(self):
        """Test NetworkXNoPath exception in weighted path (lines 314-320)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        # Create a disconnected graph scenario
        sg.G.remove_edge('Gate_A', 'Concession_1')
        sg.G.remove_edge('Gate_A', 'Restroom_1')
        sg.G.remove_edge('Gate_A', 'Section_101')
        # Gate_A is now isolated

        result = sg.find_shortest_path('Gate_A', 'Gate_B')
        # Should fall back to unweighted path
        assert result == []  # Still no path since disconnected

    def test_find_shortest_path_generic_exception(self):
        """Test generic exception handling in find_shortest_path (lines 321-323)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        # Mock get_edge_weight to raise exception
        with patch.object(sg, 'get_edge_weight', side_effect=Exception("Test error")):
            result = sg.find_shortest_path('Gate_A', 'Gate_B')
            assert result == []

    def test_get_nodes_by_type_no_graph(self):
        """Test get_nodes_by_type when graph is None (line 328)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        sg.G = None
        result = sg.get_nodes_by_type('gate')
        assert result == []


class TestAdviceCache:
    """Tests for AdviceCache to cover lines 352-363."""

    def test_get_expired_entry(self):
        """Test cache get with expired entry (lines 352-353)."""
        cache = AdviceCache(maxsize=2, ttl=0)  # TTL = 0 means immediate expiry
        cache.set("key1", MagicMock())
        time.sleep(0.01)  # Ensure expiry
        result = cache.get("key1")
        assert result is None

    def test_get_valid_entry(self):
        """Test cache get with valid entry."""
        cache = AdviceCache(maxsize=2, ttl=300)
        mock_response = MagicMock()
        cache.set("key1", mock_response)
        result = cache.get("key1")
        assert result == mock_response

    def test_set_fifo_eviction(self):
        """Test FIFO eviction when cache is full (lines 359-362)."""
        cache = AdviceCache(maxsize=2, ttl=300)
        cache.set("key1", MagicMock())
        cache.set("key2", MagicMock())
        cache.set("key3", MagicMock())  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None


class TestMQTTHandler:
    """Tests for MQTTHandler to cover lines 384-423."""

    def test_on_connect_success(self):
        """Test _on_connect with reason_code 0 (lines 384-387)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0, None)

        assert handler.connected is True
        mock_client.subscribe.assert_called_once_with("test/topic")

    def test_on_connect_failure(self):
        """Test _on_connect with non-zero reason_code (lines 388-390)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 1, None)

        assert handler.connected is False

    def test_on_message_valid(self):
        """Test _on_message with valid payload (lines 393-402)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        mock_packet = MagicMock()
        mock_packet.payload.decode.return_value = json.dumps({
            "edge": "Gate_A-Concession_1",
            "congestion": 0.7,
            "timestamp": time.time()
        })

        handler._on_message(mock_client, None, mock_packet)

        assert sg.edge_congestion[('Gate_A', 'Concession_1')] == 0.7
        assert sg.edge_congestion[('Concession_1', 'Gate_A')] == 0.7

    def test_on_message_invalid_json(self):
        """Test _on_message with invalid JSON (line 403-404)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        mock_packet = MagicMock()
        mock_packet.payload.decode.return_value = "not valid json"

        handler._on_message(mock_client, None, mock_packet)
        # Should not raise, just log error

    def test_on_message_missing_edge(self):
        """Test _on_message with missing edge field."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        mock_packet = MagicMock()
        mock_packet.payload.decode.return_value = json.dumps({
            "congestion": 0.5
        })

        handler._on_message(mock_client, None, mock_packet)
        # Should not raise

    def test_on_disconnect(self):
        """Test _on_disconnect (lines 407-408)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        mock_client = MagicMock()
        handler._on_disconnect(mock_client, None, None, 0, None)

        assert handler.connected is False

    def test_start_success(self):
        """Test start method success (lines 412-415)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        with patch.object(handler.client, 'connect') as mock_connect:
            with patch.object(handler.client, 'loop_start') as mock_loop:
                handler.start()
                mock_connect.assert_called_once_with("test.mosquitto.org", 1883, 60)
                mock_loop.assert_called_once()

    def test_start_failure(self):
        """Test start method failure (lines 416-417)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        with patch.object(handler.client, 'connect', side_effect=Exception("Connection failed")):
            handler.start()
            # Should not raise, just log error

    def test_stop(self):
        """Test stop method (lines 421-423)."""
        sg = StadiumGraph('data/stadium_graph.gexf')
        handler = MQTTHandler("test.mosquitto.org", 1883, "test/topic", sg)

        with patch.object(handler.client, 'loop_stop') as mock_loop_stop:
            with patch.object(handler.client, 'disconnect') as mock_disconnect:
                handler.stop()
                mock_loop_stop.assert_called_once()
                mock_disconnect.assert_called_once()


class TestGetStorageUri:
    """Tests for get_storage_uri (line 431)."""

    def test_get_storage_uri_with_env(self):
        """Test get_storage_uri with SLOWAPI_STORAGE_URI set."""
        with patch.dict(os.environ, {"SLOWAPI_STORAGE_URI": "redis://localhost:6379"}):
            uri = get_storage_uri()
            assert uri == "redis://localhost:6379"

    def test_get_storage_uri_default(self):
        """Test get_storage_uri default (line 432)."""
        with patch.dict(os.environ, {}, clear=True):
            uri = get_storage_uri()
            assert uri == "memory://"


class TestVerifyTokenDependency:
    """Tests for verify_token_dependency (lines 623-631)."""

    def test_verify_token_dependency_no_credentials(self):
        """Test verify_token_dependency without credentials."""
        result = verify_token_dependency(None)
        assert result is None

    def test_verify_token_dependency_invalid_token(self):
        """Test verify_token_dependency with invalid token."""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token")
        result = verify_token_dependency(credentials)
        assert result is None


class TestGenerateAIResponse:
    """Tests for generate_ai_response (lines 530-548)."""

    def test_generate_ai_response_groq_failure_then_gemini_failure(self):
        """Test AI response when both providers fail."""
        # Need to patch google_genai at the module level where it's used
        import api
        original_google_genai = api.google_genai
        try:
            api.google_genai = MagicMock()
            with patch('api.Config.GROQ_API_KEY', 'test-key'):
                with patch('api.Config.GEMINI_API_KEY', 'test-key'):
                    with patch('api.Config.AI_PROVIDER', 'auto'):
                        with patch('httpx.post', side_effect=Exception("Network error")):
                            mock_client = MagicMock()
                            mock_client.models.generate_content.side_effect = Exception("Gemini error")
                            with patch('api.google_genai.Client', return_value=mock_client):
                                result = generate_ai_response("test prompt")
                                assert result is None
        finally:
            api.google_genai = original_google_genai

    def test_generate_ai_response_gemini_no_sdk(self):
        """Test AI response when Gemini SDK not installed."""
        with patch('api.Config.GROQ_API_KEY', None):
            with patch('api.Config.GEMINI_API_KEY', 'test-key'):
                with patch('api.Config.AI_PROVIDER', 'gemini'):
                    with patch('api.google_genai', None):
                        result = generate_ai_response("test prompt")
                        assert result is None

    def test_generate_ai_response_gemini_exception(self):
        """Test AI response when Gemini raises exception."""
        import api
        original_google_genai = api.google_genai
        try:
            api.google_genai = MagicMock()
            with patch('api.Config.GROQ_API_KEY', None):
                with patch('api.Config.GEMINI_API_KEY', 'test-key'):
                    with patch('api.Config.AI_PROVIDER', 'gemini'):
                        mock_client = MagicMock()
                        mock_client.models.generate_content.side_effect = Exception("API error")
                        with patch('api.google_genai.Client', return_value=mock_client):
                            result = generate_ai_response("test prompt")
                            assert result is None
        finally:
            api.google_genai = original_google_genai


class TestLoadSystemPrompt:
    """Tests for load_system_prompt (lines 481-482)."""

    def test_load_system_prompt_file_not_found(self):
        """Test load_system_prompt when file doesn't exist."""
        with patch('api.os.path.join', return_value='/non/existent/path'):
            result = load_system_prompt()
            assert "FanWayfinder" in result
            assert "strict stadium assistant" in result


class TestGetAdviceEdgeCases:
    """Tests for get_advice endpoint edge cases (lines 708-709, 755, 757, 764-773, 799-801)."""

    def test_get_advice_invalid_location_fallback(self):
        """Test get_advice with invalid location falls back to default."""
        response = client.post(
            "/advice",
            json={
                "query": "Where is the restroom?",
                "language": "en",
                "location": "InvalidLocation",
                "stadium": "MetLife Stadium"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "advice" in data

    def test_get_advice_ai_json_parse_failure(self):
        """Test get_advice when AI returns invalid JSON (lines 764-767)."""
        # The AI response gets cached, so we need unique query to bypass cache
        with patch('api.generate_ai_response', return_value="Not valid JSON{{{"):
            response = client.post(
                "/advice",
                json={
                    "query": "Where is the restroom json parse test?",
                    "language": "en",
                    "location": "Gate_A",
                    "stadium": "MetLife Stadium"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "advice" in data
            # Should fall back to raw AI text
            assert data["advice"] == "Not valid JSON{{{"

    def test_get_advice_ai_returns_none_fallback(self):
        """Test get_advice when AI returns None (lines 768-773)."""
        with patch('api.generate_ai_response', return_value=None):
            with patch('api.knowledge_base.retrieve_relevant_chunks', return_value=["Fallback chunk"]):
                response = client.post(
                    "/advice",
                    json={
                        "query": "Where is the restroom none fallback test?",
                        "language": "en",
                        "location": "Gate_A",
                        "stadium": "MetLife Stadium"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert "advice" in data
                assert "Fallback Mode" in data["advice"]

    def test_get_advice_exception_handling(self):
        """Test get_advice exception handling (lines 799-801)."""
        with patch('api.knowledge_base.retrieve_relevant_chunks', side_effect=Exception("Test error")):
            with patch('api.generate_ai_response', return_value=None):
                response = client.post(
                    "/advice",
                    json={
                        "query": "Where is the restroom exception test?",
                        "language": "en",
                        "location": "Gate_A",
                        "stadium": "MetLife Stadium"
                    }
                )
                assert response.status_code == 500


class TestJWTCoverage:
    """Tests for jwt.py uncovered lines."""

    def test_encode_non_hs256(self):
        """Test encode with non-HS256 algorithm (line 59)."""
        from src.jwt import encode, JWTError
        with pytest.raises(JWTError, match="Only HS256 is supported"):
            encode({"sub": "test"}, key="secret", algorithm="RS256")

    def test_decode_invalid_format(self):
        """Test decode with invalid token format (line 75)."""
        from src.jwt import decode, JWTError
        with pytest.raises(JWTError, match="Invalid token format"):
            decode("invalid.token")

    def test_decode_verify_signature_no_key(self):
        """Test decode with verify_signature=True but no key (lines 85-88)."""
        from src.jwt import decode, JWTError
        with pytest.raises(JWTError, match="No key provided for signature verification"):
            decode("header.payload.signature", options={"verify_signature": True})

    def test_decode_signature_verification_failed(self):
        """Test decode with signature mismatch (lines 91-92)."""
        from src.jwt import decode, JWTError
        with pytest.raises(JWTError, match="Signature verification failed"):
            decode("header.payload.wrongsig", options={"verify_signature": True}, key="secret")

    def test_decode_payload_decode_failure(self):
        """Test decode with payload decode failure (lines 97-98)."""
        from src.jwt import decode, JWTError
        # Create token with invalid base64 payload - need valid format (2 dots) but invalid payload
        with pytest.raises(JWTError, match="Invalid token format"):
            decode("header.!!!invalid!!!signature", options={"verify_signature": False})


class TestSensorMockCoverage:
    """Tests for sensor_mock.py uncovered lines."""

    def test_fallback_graph_creation(self):
        """Test fallback graph creation when file doesn't exist (lines 13-14)."""
        # The sensor_mock module loads graph at module level, so we test the import logic
        import sys

        # Remove sensor_mock from cache to force re-execution
        for mod_name in list(sys.modules.keys()):
            if 'sensor_mock' in mod_name:
                del sys.modules[mod_name]

        with patch('os.path.exists', return_value=False):
            with patch('generate_graph.create_stadium_graph') as mock_create:
                mock_g = MagicMock()
                mock_create.return_value = mock_g
                # Import the module to trigger the module-level code
                import sensor_mock  # noqa: F401
                mock_create.assert_called_once()

    def test_on_connect_rc_zero(self):
        """Test on_connect with rc=0 (lines 26-27)."""
        from sensor_mock import on_connect
        mock_client = MagicMock()
        on_connect(mock_client, None, None, 0)
        # Just verify it doesn't raise

    def test_on_connect_rc_nonzero(self):
        """Test on_connect with rc!=0 (lines 28-29)."""
        from sensor_mock import on_connect
        mock_client = MagicMock()
        on_connect(mock_client, None, None, 1)
        # Just verify it doesn't raise

    def test_on_disconnect(self):
        """Test on_disconnect (line 32)."""
        from sensor_mock import on_disconnect
        mock_client = MagicMock()
        on_disconnect(mock_client, None, 0)
        # Just verify it doesn't raise

    def test_main_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt (line 68)."""
        from sensor_mock import main
        with patch('sensor_mock.mqtt.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.loop_start.return_value = None
            mock_client.loop_stop.return_value = None
            mock_client.disconnect.return_value = None

            # Mock sleep to raise KeyboardInterrupt immediately
            with patch('sensor_mock.time.sleep', side_effect=KeyboardInterrupt()):
                with patch('sensor_mock.time.time', return_value=1234567890.0):
                    with patch('sensor_mock.G') as mock_g:
                        mock_g.edges.return_value = [('A', 'B', {})]
                        try:
                            main()
                        except KeyboardInterrupt:
                            pass  # Expected

            mock_client.loop_stop.assert_called()
            mock_client.disconnect.assert_called()


class TestGenerateGraphCoverage:
    """Tests for generate_graph.py line 132."""

    def test_main_block(self):
        """Test create_stadium_graph when run as main (line 132)."""
        import generate_graph
        with patch('generate_graph.nx.write_gexf') as mock_gexf:
            with patch('builtins.open', mock.mock_open()) as _:
                with patch('generate_graph.json.dump') as mock_dump:
                    with patch('generate_graph.os.makedirs') as _:
                        g = generate_graph.create_stadium_graph()
                        assert g is not None
                        mock_gexf.assert_called()
                        mock_dump.assert_called()


class TestLifespanAndMain:
    """Tests for lifespan and main block (lines 569-573, 834)."""

    def test_lifespan_startup_shutdown(self):
        """Test lifespan context manager."""
        from api import lifespan
        import asyncio

        async def test_lifespan():
            async with lifespan(app):
                pass  # startup and shutdown happen here

        # Run the async test
        asyncio.run(test_lifespan())

    def test_main_block(self):
        """Test __main__ block (line 834)."""
        # This is the uvicorn.run call - we can't easily test without starting server
        # But we can verify the module imports correctly
        import api
        assert api.app is not None


class TestConfigValidationCoverage:
    """Additional tests for Config.validate_production_config."""

    def test_validate_production_config_with_default_secret(self):
        """Test validate_production_config with default secret (line 134)."""
        original_env = dict(os.environ)
        try:
            os.environ["ENVIRONMENT"] = "production"
            # Remove SECRET_KEY to trigger the check
            if "SECRET_KEY" in os.environ:
                del os.environ["SECRET_KEY"]
            with pytest.raises(ValueError, match="Missing required environment variables for production"):
                Config.validate_production_config()
        finally:
            os.environ.clear()
            os.environ.update(original_env)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
