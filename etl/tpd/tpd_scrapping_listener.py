"""
    Kafka Listener for ETL Processing (Production Style)
    Author: Nabeel Ahmed Jamil
"""
import os
import time
import signal
import logging
import threading
import colorlog
from dotenv import load_dotenv
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
# Kafka
from etl.tpd.tpd_kafka_config import create_consumer
from etl.util.xml_parser import pipeline_xml_parser
from etl.util.job_state_client import JobStateClient
from etl.util.job_status import JobStatus

# ------------------------------------------------------------------------------
# Load Environment
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging
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
# Environment
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
kafka_servers = os.getenv("KAFKA_SERVERS").split(",")
kafka_scrapping_topic = os.getenv("KAFKA_SCRAPPING_TOPIC")
scrapping_group_id = os.getenv("SCRAPPING_GROUP_ID")
# ------------------------------------------------------------------------------
# Thread Configuration
# ------------------------------------------------------------------------------
MAX_WORKERS = 25
# Prevent unlimited tasks waiting in memory
MAX_QUEUE_SIZE = 50
semaphore = threading.Semaphore(MAX_WORKERS + MAX_QUEUE_SIZE)
shutdown_event = threading.Event()

# ------------------------------------------------------------------------------
# Graceful Shutdown
# ------------------------------------------------------------------------------
def shutdown_handler(signum, frame):
    logger.info("Shutdown signal received")
    shutdown_event.set()

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# ------------------------------------------------------------------------------
# Kafka Listener Process
# ------------------------------------------------------------------------------
def start_kafka_listener():
    consumer = None
    # Create dependencies inside process
    job_state_client = JobStateClient(etl_event_url)
    try:
        logger.info("Starting Kafka consumer")
        consumer = create_consumer(kafka_scrapping_topic, kafka_servers, scrapping_group_id)
        logger.info("Kafka connected topic=%s group=%s",kafka_scrapping_topic, scrapping_group_id)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while not shutdown_event.is_set():
                message = consumer.poll(timeout_ms=1000)
                if not message:
                    continue
                for _, records in message.items():
                    for record in records:
                        payload = record.value
                        if not payload:
                            continue
                        # Control memory
                        semaphore.acquire()
                        executor.submit(execute_task_wrapper,record, payload, consumer, job_state_client)
    except Exception as ex:
        logger.exception("Kafka listener failed %s",str(ex))
    finally:
        if consumer:
            consumer.close()
            logger.info("Kafka consumer closed")

# ------------------------------------------------------------------------------
# Thread Wrapper
# ------------------------------------------------------------------------------
def execute_task_wrapper(message, payload, consumer, job_state_client):
    try:
        execute_task(message, payload, job_state_client)
        # Commit only after success
        consumer.commit()
        logger.info("Kafka offset committed offset=%s",message.offset)
    except Exception as ex:
        logger.exception("Task failed %s",str(ex))
    finally:
        semaphore.release()

# ------------------------------------------------------------------------------
# ETL Task Processing
# ------------------------------------------------------------------------------
def execute_task(message, payload, job_state_client):
    job_id = None
    job_queue_id = None
    try:
        logger.info("Processing partition=%s offset=%s",message.partition, message.offset)
        job_id = payload.get("jobId")
        job_queue_id = payload.get("jobQueueId")
        pipeline_id = payload.get("pipelineId")

        if not job_id:
            raise ValueError("jobId missing")

        if not job_queue_id:
            raise ValueError("jobQueueId missing")

        if not pipeline_id:
            raise ValueError("pipelineId missing")

        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.RUNNING,"Job started")
        task_payload = extract_task_payload(pipeline_id, payload)
        task_payload["job_id"] = job_id
        task_payload["job_queue_id"] = job_queue_id
        # --------------------------------------------------
        # Pipeline Router
        # --------------------------------------------------
        if pipeline_id == "F768924":
            from etl.tasks.pdf_highligter_form_fill_F768924 import (pdf_highlighter_form_film)
            pdf_highlighter_form_film(task_payload)
        elif pipeline_id == "F768925":
            from etl.tasks.pdf_highlighter_f768925 import (pdf_highlighter_text_extraction_etl)
            pdf_highlighter_text_extraction_etl(task_payload)
        elif pipeline_id == "F768926":
            from etl.tasks.etl_hurricanes_f768926 import (fetch_and_extract_all_seasons)
            fetch_and_extract_all_seasons(task_payload)
        elif pipeline_id == "F768927":
            from etl.tasks.mp3_noise_processing_extract_txt_f768927 import (mp3_noise_processing_extract_txt)
            mp3_noise_processing_extract_txt(task_payload)
        else:
            raise ValueError(f"Unknown pipeline {pipeline_id}")

        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.COMPLETED,"Job completed successfully")
    except Exception as ex:
        logger.exception("Job failed job_id=%s",job_id)
        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.FAILED, str(ex))
        raise

# ------------------------------------------------------------------------------
# Payload Parser
# ------------------------------------------------------------------------------
def extract_task_payload(pipeline_id, payload):
    parser = pipeline_xml_parser.get(pipeline_id)
    if not parser:
        raise ValueError(f"No parser found for {pipeline_id}")
    return parser(payload.get("taskPayload"))

# ------------------------------------------------------------------------------
# Job Status
# ------------------------------------------------------------------------------
def update_job_status(job_state_client, job_id, job_queue_id, status, message):
    time.sleep(0.2)
    job_state_client.change_job_state(job_id, job_queue_id, status, message)

# ------------------------------------------------------------------------------
# Process Starter
# ------------------------------------------------------------------------------
def start_consumers(num_processes=1):
    processes = []
    for i in range(num_processes):
        process = Process(target=start_kafka_listener, name=f"consumer-{i}")
        process.start()
        processes.append(process)
    for process in processes:
        process.join()

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    start_consumers(num_processes=1)