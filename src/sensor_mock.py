import json
import time
import random
import paho.mqtt.client as mqtt
import networkx as nx
import os
from typing import Any

# Load graph to get edges
graph_path = 'data/stadium_graph.json'
if not os.path.exists(graph_path):
    # fallback to generating if not exist
    from generate_graph import create_stadium_graph
    G = create_stadium_graph()
else:
    with open(graph_path, 'r') as f:
        data = json.load(f)
    G = nx.node_link_graph(data)

# MQTT settings
MQTT_BROKER = "test.mosquitto.org"  # public test broker
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "stadium/congestion/edge"

def on_connect(client: Any, userdata: Any, flags: Any, rc: int) -> None:
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client: Any, userdata: Any, rc: int) -> None:
    print("Disconnected from MQTT broker")

def main() -> None:
    """Main function to run the MQTT publisher."""
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    try:
        while True:
            for u, v, data in G.edges(data=True):
                # Simulate congestion value between 0.0 and 1.0
                congestion = random.uniform(0.0, 1.0)
                edge_id = f"{u}-{v}"
                topic = f"{MQTT_TOPIC_PREFIX}/{edge_id}"
                payload = json.dumps({
                    "edge": edge_id,
                    "congestion": congestion,
                    "timestamp": time.time()
                })
                client.publish(topic, payload)
                # print(f"Published {topic}: {payload}")  # Uncomment for verbosity
            time.sleep(2)  # publish every 2 seconds
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

