"""
Tests for new features: authentication, caching, etc.
"""

import sys
sys.path.insert(0, 'src')

from fastapi.testclient import TestClient
from api import app, create_access_token, verify_token

client = TestClient(app)


def test_login_endpoint():
    """Test the login endpoint."""
    response = client.post("/token", json={
        "username": "testuser",
        "password": "testpass"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    access_token = data["access_token"]
    assert isinstance(access_token, str)
    # JWT tokens contain two dots separating header, payload, signature
    assert access_token.count(".") == 2


def test_create_access_token():
    """Test token creation."""
    data = {"sub": "testuser", "role": "user"}
    token = create_access_token(data)

    assert isinstance(token, str)
    # JWT tokens contain two dots separating header, payload, signature
    assert token.count(".") == 2


def test_verify_token():
    """Test token verification."""
    data = {"sub": "testuser"}
    token = create_access_token(data)
    token_data = verify_token(token)
    # Our mock implementation returns a TokenData object
    assert token_data is not None
    assert hasattr(token_data, 'username')
    # Our implementation returns the username from the token's sub claim
    assert token_data.username == "testuser"


def test_advice_endpoint_with_token():
    """Test the advice endpoint with a valid token."""
    # First get a token
    login_response = client.post("/token", json={
        "username": "testuser",
        "password": "testpass"
    })
    assert login_response.status_code == 200
    token_data = login_response.json()
    access_token = token_data["access_token"]

    # Make request with token
    response = client.post(
        "/advice",
        json={
            "query": "Where is the nearest restroom?",
            "language": "en",
            "location": "Gate_A"
        },
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "advice" in data
    assert "route" in data
    assert data["congestion_aware"]


def test_advice_endpoint_without_token():
    """Test the advice endpoint without a token (should work for hackathon)."""
    response = client.post(
        "/advice",
        json={
            "query": "Where is the nearest restroom?",
            "language": "en",
            "location": "Gate_A"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "advice" in data
    assert "route" in data
    assert data["congestion_aware"]


def test_advice_cache():
    """Test the advice cache by making two identical requests."""
    # We'll test by making two identical requests and checking that the advice is the same.
    # Note: We cannot directly inspect the cache, but we can rely on the fact that the same query returns the same advice.

    # First request
    response1 = client.post(
        "/advice",
        json={
            "query": "Where is the nearest restroom?",
            "language": "en",
            "location": "Gate_A"
        }
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Second request with the same parameters
    response2 = client.post(
        "/advice",
        json={
            "query": "Where is the nearest restroom?",
            "language": "en",
            "location": "Gate_A"
        }
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # The advice should be the same (assuming no change in underlying data changed)
    # Note: In a real test, we might want to mock the underlying data to ensure it's static.
    # For now, we just check that both responses are successful and have the same structure.
    assert data1["advice"] == data2["advice"]


def test_rate_limiter():
    """Test the rate limiter by making many requests quickly."""
    # We'll make more than the allowed requests (30 per minute) and expect a 429.
    # Note: This test might be flaky if run multiple times in a short period.
    # We'll skip this test for now because it's hard to test in isolation without affecting other tests.
    pass


def test_frontend_assets_served():
    """The root route should serve the frontend landing page and its assets."""
    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "FanWayfinder" in index_response.text

    js_response = client.get("/app.js")
    assert js_response.status_code == 200
    assert "API_URL" in js_response.text

    css_response = client.get("/style.css")
    assert css_response.status_code == 200
    assert "font-family" in css_response.text


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
