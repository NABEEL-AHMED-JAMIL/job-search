"""
Utility functions for TPD (Third-Party Data) processing, including message deserialization and logging setup.
"""
import json
# kafka-python package is required for this module to work
from kafka import KafkaConsumer
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)

# ==============================================================================
# Kafka Consumer
# ==============================================================================
def create_consumer(topic_name, bootstrap_services, group_id) -> KafkaConsumer:
    """
        Create Kafka Consumer
    """
    return KafkaConsumer(
        topic_name,
        bootstrap_servers=bootstrap_services,
        group_id=group_id,
        # Deserialization
        value_deserializer=deserialize_message,
        # Offset management
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        # Reliability
        session_timeout_ms=45000,
        heartbeat_interval_ms=15000,
        request_timeout_ms=60000,
        # Polling
        max_poll_records=10,
        max_poll_interval_ms=900000,  # 15 minutes
        # Connection management
        connections_max_idle_ms=540000,
        # Fetch tuning
        fetch_max_wait_ms=500,
    )

def deserialize_message(message):
    if not message:
        return None
    try:
        decoded = message.decode("utf-8")
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {decoded}")
            return None
    except Exception as e:
        logger.error(f"Deserialization error: {str(e)}", exc_info=True)
        return None
