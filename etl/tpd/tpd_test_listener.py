"""
Kafka Listener for test-topic (Production Style)
"""
import os
import time
from dotenv import load_dotenv
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from etl.tpd.tpd_kafka_config import create_consumer
from etl.util.xml_parser import tpd_test_task_payload_parser
from etl.util.job_state_client import JobStateClient
from etl.util.job_status import JobStatus
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)
# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
kafka_servers = os.getenv("KAFKA_SERVERS").split(",")
kafka_test_topic = os.getenv("KAFKA_TEST_TOPIC")
test_group_id = os.getenv("TEST_GROUP_ID")
# ------------------------------------------------------------------------------
# Thread Pool per process
# ------------------------------------------------------------------------------
MAX_WORKERS = 10
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)

# ------------------------------------------------------------------------------
# MAIN LISTENER (PROCESS LEVEL)
# ------------------------------------------------------------------------------
def start_test_listener():
    """
        Kafka consumer running in a separate process.
        Each process has its own thread pool.
    """

    consumer = None

    try:
        logger.info("Connecting Kafka: %s", ",".join(kafka_servers))
        consumer = create_consumer(kafka_test_topic, kafka_servers, test_group_id)
        logger.info("Kafka consumer started (process=%s)", id(consumer))
        logger.info("Topic=%s Group=%s", kafka_test_topic, test_group_id)

        # Thread pool inside each consumer process
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for message in consumer:
                payload = message.value
                if not payload:
                    continue
                # Submit task to thread pool (non-blocking Kafka loop)
                executor.submit(handle_message, message, payload)

    except KeyboardInterrupt:
        logger.info("Listener stopped by user")
    except Exception as ex:
        logger.exception("Kafka listener error: %s", str(ex))
    finally:
        if consumer:
            consumer.close()
            logger.info("Kafka consumer closed")

# ------------------------------------------------------------------------------
# MESSAGE HANDLER (THREAD LEVEL)
# ------------------------------------------------------------------------------
def handle_message(message, payload):
    try:
        logger.info("Received msg partition=%s offset=%s",message.partition, message.offset)
        execute_task(payload)
        logger.info("Completed offset=%s", message.offset)

    except Exception as ex:
        logger.exception(
            "Failed offset=%s error=%s",
            message.offset,
            str(ex)
        )

# ------------------------------------------------------------------------------
# Job Processing
# ------------------------------------------------------------------------------
def execute_task(payload: dict):
    """
        Process a single job payload.
    """
    job_queue = payload.get("jobQueue", {})
    job_id = job_queue.get("jobId")
    job_queue_id = job_queue.get("jobQueueId")

    if not job_id or not job_queue_id:
        raise ValueError("jobId or jobQueueId missing from payload")

    try:
        logger.info("Starting Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)
        update_job_status(job_id, job_queue_id, JobStatus.RUNNING,f"Job {job_id} is running.")
        task_payload = extract_task_payload(payload)
        process_batches(job_id, job_queue_id, task_payload)
        update_job_status(job_id, job_queue_id, JobStatus.COMPLETED,f"Job {job_id} completed successfully.")
        logger.info("Complete Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)

    except Exception as ex:
        logger.exception("Job failed. jobId=%s", job_id)
        update_job_status(job_id, job_queue_id, JobStatus.FAILED, f"Job {job_id} failed due to {str(ex)}")
        raise


def extract_task_payload(payload: dict) -> dict:
    """
        Extract and parse task payload.
    """
    task_payload_xml = (
        payload.get("taskDetail", {})
        .get("taskPayload", {})
    )
    parsed_payload = tpd_test_task_payload_parser(task_payload_xml)
    logger.info("Parsed Task Payload: %s", parsed_payload)
    return parsed_payload


def process_batches(job_id, job_queue_id, task_payload):
    """
        Execute business processing.
    """
    start = int(task_payload["start"])
    end = int(task_payload["end"])
    logger.info("Processing range %s -> %s", start, end)
    for batch_no in range(start, end):
        logger.info("Processing batch %s", batch_no)
        # Simulate work
        time.sleep(0.1)
        # DB/log call
        job_state_client.job_audit_log(job_id, job_queue_id, message=f"Processing batch {batch_no}")

# ==============================================================================
# Utility Methods
# ==============================================================================
def update_job_status(job_id, job_queue_id, status, message):
    """
        Update job status.
    """
    time.sleep(0.2);
    job_state_client.change_job_state(job_id, job_queue_id, status, message)


# ------------------------------------------------------------------------------
# PROCESS STARTER (SCALING LAYER)
# ------------------------------------------------------------------------------
def start_consumers(num_processes=3):
    """
        Start multiple Kafka consumer processes
    """
    processes = []

    for i in range(num_processes):
        p = Process(target=start_test_listener, name=f"consumer-{i}")
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 3 processes × 10 threads = 30 parallel workers
    start_consumers(num_processes=3)
