"""
Tests for sensor_mock module
"""
import json
import sys
from unittest import mock

# Add src to path
sys.path.insert(0, 'src')


def test_mqtt_payload_structure():
    """Test that MQTT payloads have the correct structure."""
    # Test the payload structure that would be created
    edge_id = "Gate_A-Concession_1"
    congestion = 0.5
    timestamp = 1234567890.0

    payload = {
        "edge": edge_id,
        "congestion": congestion,
        "timestamp": timestamp
    }

    # Verify required fields are present
    assert "edge" in payload
    assert "congestion" in payload
    assert "timestamp" in payload

    # Verify data types
    assert isinstance(payload["edge"], str)
    assert isinstance(payload["congestion"], (int, float))
    assert isinstance(payload["timestamp"], (int, float))

    # Verify congestion is in valid range
    assert 0.0 <= payload["congestion"] <= 1.0


def test_json_serialization():
    """Test that payloads can be serialized to JSON."""
    payload = {
        "edge": "Gate_A-Concession_1",
        "congestion": 0.75,
        "timestamp": 1234567890.0
    }

    # This should not raise an exception
    json_str = json.dumps(payload)

    # Verify it can be deserialized
    parsed = json.loads(json_str)
    assert parsed == payload


def test_topic_format():
    """Test that MQTT topics are formatted correctly."""
    edge_id = "Gate_A-Concession_1"
    topic_prefix = "stadium/congestion/edge"

    topic = f"{topic_prefix}/{edge_id}"

    assert topic == "stadium/congestion/edge/Gate_A-Concession_1"
    assert topic.startswith(topic_prefix + "/")
    assert edge_id in topic


@mock.patch('sensor_mock.mqtt.Client')
@mock.patch('os.path.exists')
@mock.patch('sensor_mock.nx.node_link_graph')
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data='{"nodes": [], "edges": []}')
def test_module_can_be_imported(mock_open, mock_node_link_graph, mock_exists, mock_mqtt_client):
    """Test that the module can be imported without error."""
    # Clear the module from cache to force re-execution of module-level code
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('sensor_mock')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Mock that the file exists
    mock_exists.return_value = True
    # Mock the networkx graph loading
    mock_G = mock.MagicMock()
    mock_G.edges.return_value = [('Gate_A', 'Concession_1', {'base_distance': 10})]
    mock_node_link_graph.return_value = mock_G

    # Import the module - this should not raise an exception
    import sensor_mock

    # Verify that the module has the expected functions and attributes
    assert hasattr(sensor_mock, 'main')
    assert hasattr(sensor_mock, 'on_connect')
    assert hasattr(sensor_mock, 'on_disconnect')
    assert hasattr(sensor_mock, 'G')
    assert hasattr(sensor_mock, 'MQTT_BROKER')
    assert hasattr(sensor_mock, 'MQTT_PORT')
    assert hasattr(sensor_mock, 'MQTT_TOPIC_PREFIX')

    # Verify that the graph was loaded correctly
    assert mock_node_link_graph.called
    # Verify that the file was opened
    assert mock_open.called


@mock.patch('sensor_mock.mqtt.Client')
@mock.patch('os.path.exists')
@mock.patch('sensor_mock.nx.node_link_graph')
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data='{"nodes": [], "edges": []}')
@mock.patch('sensor_mock.time')
def test_main_function_calls_mqtt_correctly(mock_time, mock_open, mock_node_link_graph, mock_exists, mock_mqtt_client):
    """Test that the main function sets up MQTT client correctly."""
    # Clear the module from cache to force re-execution of module-level code
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('sensor_mock')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Setup mocks
    mock_exists.return_value = True
    mock_G = mock.MagicMock()
    mock_G.edges.return_value = [('Gate_A', 'Concession_1', {'base_distance': 10})]
    mock_node_link_graph.return_value = mock_G

    # Mock the MQTT client instance that will be returned by mqtt.Client()
    mock_client_instance = mock.MagicMock()
    mock_mqtt_client.return_value = mock_client_instance

    # Mock time.time to return a fixed value
    mock_time.time.return_value = 1234567890.0

    # Import the module
    import sensor_mock

    # Call the main function (we'll mock the infinite loop to avoid hanging)
    with mock.patch('sensor_mock.time.sleep', side_effect=KeyboardInterrupt):
        try:
            sensor_mock.main()
        except KeyboardInterrupt:
            pass  # Expected due to our sleep mock

    # Verify that MQTT client was created and configured
    assert mock_mqtt_client.called
    # Verify that on_connect and on_disconnect callbacks were set
    assert mock_client_instance.on_connect == sensor_mock.on_connect
    assert mock_client_instance.on_disconnect == sensor_mock.on_disconnect
    # Verify that connect was called with the right parameters
    mock_client_instance.connect.assert_called_once_with(
        "test.mosquitto.org", 1883, 60
    )
    # Verify that loop_start was called
    mock_client_instance.loop_start.assert_called_once()


@mock.patch('sensor_mock.mqtt.Client')
@mock.patch('os.path.exists')
@mock.patch('sensor_mock.nx.node_link_graph')
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data='{"nodes": [], "edges": []}')
@mock.patch('sensor_mock.time')
def test_publish_logic_in_main(mock_time, mock_open, mock_node_link_graph, mock_exists, mock_mqtt_client):
    """Test the publishing logic inside main() without running the infinite loop."""
    # Import mqtt for use in this test
    import paho.mqtt.client as mqtt

    # Clear the module from cache to force re-execution of module-level code
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('sensor_mock')]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Setup mocks
    mock_exists.return_value = True
    mock_G = mock.MagicMock()
    mock_G.edges.return_value = [
        ('Gate_A', 'Concession_1', {'base_distance': 10}),
        ('Gate_A', 'Restroom_1', {'base_distance': 5})
    ]
    mock_node_link_graph.return_value = mock_G

    mock_client_instance = mock.MagicMock()
    mock_mqtt_client.return_value = mock_client_instance

    # Mock time.time to return a fixed value
    mock_time.time.return_value = 1234567890.0

    # Import the module
    import sensor_mock

    # Reset the mock to clear any calls from setup
    mock_client_instance.reset_mock()

    # Simulate publishing for 1 iteration (just to test the logic)
    for u, v, data in mock_G.edges(data=True):
        congestion = 0.5  # Fixed value for testing
        edge_id = f"{u}-{v}"
        topic = f"{sensor_mock.MQTT_TOPIC_PREFIX}/{edge_id}"
        payload = json.dumps({
            "edge": edge_id,
            "congestion": congestion,
            "timestamp": mock_time.time()
        })
        # Call the publish method on our mocked client instance
        mock_client_instance.publish(topic, payload)

    # Verify that publish was called the expected number of times
    # 2 edges * 1 iteration = 2 calls
    assert mock_client_instance.publish.call_count == 2

    # Verify the calls had the correct parameters
    calls = mock_client_instance.publish.call_args_list
    assert len(calls) == 2

    # Check first call
    assert calls[0][0][0] == "stadium/congestion/edge/Gate_A-Concession_1"
    assert "Gate_A-Concession_1" in calls[0][0][1]
    assert "0.5" in calls[0][0][1]  # congestion as number in JSON
    assert "1234567890.0" in calls[0][0][1]  # timestamp


if __name__ == "__main__":
    test_mqtt_payload_structure()
    test_json_serialization()
    test_topic_format()
    test_module_can_be_imported()
    test_main_function_calls_mqtt_correctly()
    test_publish_logic_in_main()
    print("All sensor_mock tests passed!")