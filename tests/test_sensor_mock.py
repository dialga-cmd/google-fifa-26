"""
Tests for sensor_mock module
"""
import sys
sys.path.insert(0, 'src')

import sensor_mock


def test_import():
    """Test that the module can be imported."""
    assert sensor_mock is not None


def test_on_connect():
    """Test the on_connect callback."""
    client = None
    userdata = None
    flags = {}
    rc = 0
    # Should not raise
    sensor_mock.on_connect(client, userdata, flags, rc)


def test_on_disconnect():
    """Test the on_disconnect callback."""
    client = None
    userdata = None
    rc = 0
    sensor_mock.on_disconnect(client, userdata, rc)


def test_main_exists():
    """Test that main function exists."""
    assert hasattr(sensor_mock, 'main')
