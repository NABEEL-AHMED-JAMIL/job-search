"""
Kafka Listener for scrapping-topic (Production Style)
"""
from dotenv import load_dotenv
import os

import time
import logging
import colorlog
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
# Kafka
from etl.tpd.tpd_kafka_config import create_consumer
from etl.util.xml_parser import pipeline_xml_parser
from etl.util.job_state_client import JobStateClient
from etl.util.job_status import JobStatus
# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter("%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# ------------------------------------------------------------------------------
# ENV DATA LOAD
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
kafka_servers = os.getenv("KAFKA_SERVERS").split(",")
kafka_scrapping_topic = os.getenv("KAFKA_SCRAPPING_TOPIC")
scrapping_group_id = os.getenv("SCRAPPING_GROUP_ID")
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
def start_kafka_listener():
    """
        Kafka consumer running in a separate process.
        Each process has its own thread pool.
    """
    consumer = None

    try:
        logger.info("Connecting Kafka: %s", ",".join(kafka_servers))
        consumer = create_consumer(kafka_scrapping_topic, kafka_servers, scrapping_group_id)
        logger.info("Kafka consumer started (process=%s)", id(consumer))
        logger.info("Topic=%s Group=%s", kafka_scrapping_topic, scrapping_group_id)

        # Thread pool inside each consumer process
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for message in consumer:
                payload = message.value
                if not payload:
                    continue
                # Submit task to thread pool (non-blocking Kafka loop)
                executor.submit(execute_task, message, payload)

    except KeyboardInterrupt:
        logger.info("Listener stopped by user")
    except Exception as ex:
        logger.exception("Kafka listener error: %s", str(ex))
    finally:
        if consumer:
            consumer.close()
            logger.info("Kafka consumer closed")


# ------------------------------------------------------------------------------
# Job Processing
# ------------------------------------------------------------------------------
def execute_task(message, payload: dict):
    """
        Process a single job payload.
    """
    try:
        logger.info("Received msg partition=%s offset=%s", message.partition, message.offset)
        # JobQueue
        job_id = payload.get("jobId")
        job_queue_id = payload.get("jobQueueId")
        # TaskDetail
        pipeline_id = payload.get("pipelineId")

        if not job_id or not job_queue_id:
            raise ValueError("jobId or jobQueueId missing from payload")
        elif not pipeline_id:
            raise ValueError("pipelineId missing from payload")

        logger.info("Starting Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)
        update_job_status(job_id, job_queue_id, JobStatus.RUNNING,f"Job {job_id} is running.")
        # passing payload bz we may need to extract more info payload
        task_payload = extract_task_payload(pipeline_id, payload)
        logger.info("Processing Task Payload: %s", task_payload)

        task_payload['job_id'] = job_id
        task_payload['job_queue_id'] = job_queue_id
        if pipeline_id == 'F768925':
            # Imported lazily so a broken dependency chain in one task (e.g. mp3's
            # whisper/numba stack) can't block the listener from starting at all.
            from etl.tasks.pdf_highlighter_f768925 import pdf_highlighter_text_extraction_etl
            pdf_highlighter_text_extraction_etl(task_payload)
        elif pipeline_id == 'F768926':
            from etl.tasks.etl_hurricanes_f768926 import fetch_and_extract_all_seasons
            fetch_and_extract_all_seasons(task_payload)
        elif pipeline_id == 'F768927':
            from etl.tasks.mp3_noise_processing_extract_txt_f768927 import mp3_noise_processing_extract_txt
            mp3_noise_processing_extract_txt(task_payload)

        update_job_status(job_id, job_queue_id, JobStatus.COMPLETED,f"Job {job_id} completed successfully.")
        logger.info("Complete Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)
    except Exception as ex:
        logger.exception("Job failed. jobId=%s", job_id)
        update_job_status(job_id, job_queue_id, JobStatus.FAILED, f"Job {job_id} failed due to {str(ex)}")
        raise


def extract_task_payload(pipeline_id, payload: dict):
    """
        Extract and parse task payload.
    """
    parsed_payload = pipeline_xml_parser[pipeline_id](payload.get("taskPayload"))
    logger.info("Parsed Task Payload: %s", parsed_payload)
    return parsed_payload

# ==============================================================================
# Utility Methods
# ==============================================================================
def update_job_status(job_id, job_queue_id, status, message):
    """
        Update job status.
    """
    time.sleep(0.2)  # Simulate some processing delay
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
        p = Process(target=start_kafka_listener, name=f"consumer-{i}")
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 3 processes × 10 threads = 50 parallel workers
    start_consumers(num_processes=1)