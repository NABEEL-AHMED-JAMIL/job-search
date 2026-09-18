"""
    Kafka Listener for ETL Processing (Production Style)
    Author: Nabeel Ahmed Jamil
"""
import os
import time
import signal
import threading
import importlib
from dotenv import load_dotenv
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
# Kafka
from etl.tpd.tpd_kafka_config import create_consumer
from etl.tpd.offset_tracker import OffsetTracker
from etl.util.xml_parser import pipeline_xml_parser
from etl.util.ai_steps import resolve_ai_steps
from etl.util.etl_helpers import job_state
from etl.util.job_status import JobStatus
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load Environment
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logger = get_logger(__name__)
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

offset_tracker = OffsetTracker()
shutdown_event = threading.Event()

# ------------------------------------------------------------------------------
# Pipeline Router
#
# pipeline id -> (module, entry function). A table rather than a chain of elif
# branches: with nineteen pipelines the chain was most of execute_task, and a
# pipeline whose branch was added but whose parser was not (or the reverse) is
# invisible in a chain and a one-line diff to check against a table.
#
# The import stays inside the dispatch, not at module scope, and that is load-bearing:
# F768927 pulls in torch and whisper, F768920 the firebase SDK. Importing all of them
# to run one would make every worker pay for every pipeline's dependencies.
# ------------------------------------------------------------------------------
PIPELINE_TASKS = {
    "F768926": ("etl.tasks.etl_hurricanes_f768926", "fetch_and_extract_all_seasons"),
    "F768927": ("etl.tasks.mp3_noise_processing_extract_txt_f768927", "mp3_noise_processing_extract_txt"),
    "F768920": ("etl.tasks.zanium_firebase_data_export_f768920", "zanium_firebase_data_export"),
    "F76800": ("etl.tasks.send_email_batch_f76800", "send_email_batch"),
    # Object-storage ETL family
    "F768930": ("etl.tasks.csv_to_json_f768930", "csv_to_json"),
    "F768931": ("etl.tasks.csv_schema_validate_f768931", "csv_schema_validate"),
    "F768932": ("etl.tasks.csv_deduplicate_f768932", "csv_deduplicate"),
    "F768933": ("etl.tasks.csv_filter_rows_f768933", "filter_csv_rows"),
    "F768934": ("etl.tasks.csv_merge_f768934", "merge_csv_files"),
    "F768935": ("etl.tasks.csv_aggregate_f768935", "csv_group_by_aggregate"),
    "F768936": ("etl.tasks.csv_select_rename_f768936", "csv_select_rename"),
    "F768937": ("etl.tasks.csv_quality_report_f768937", "csv_quality_report"),
    "F768938": ("etl.tasks.csv_split_f768938", "split_csv_into_chunks"),
    "F768939": ("etl.tasks.object_compress_f768939", "compress_objects_for_archival"),
    "F768940": ("etl.tasks.csv_to_postgres_f768940", "csv_to_postgres"),
    "F768941": ("etl.tasks.postgres_to_csv_f768941", "export_postgres_query_to_csv"),
    "F768942": ("etl.tasks.csv_join_f768942", "join_csv_objects"),
    "F768943": ("etl.tasks.csv_snapshot_diff_f768943", "csv_snapshot_diff"),
    "F768944": ("etl.tasks.object_retention_f768944", "sweep_objects_for_retention"),
    "F768945": ("etl.tasks.csv_partition_f768945", "csv_partition"),
    "F768946": ("etl.tasks.folder_for_each_f768946", "folder_for_each"),
    # Medical imaging. Pillow and the vision model are reached only when this one runs.
    "F768947": ("etl.tasks.xray_ai_analysis_f768947", "xray_ai_analysis")
}

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
    # The SHARED client, not a second one.
    #
    # Pipeline.log() buffers its lines on the singleton in etl_helpers.job_state(); this used to
    # build a JobStateClient of its own and then call flush_logs on it, which emptied a buffer
    # nothing had ever written to. Any run that ended before the batch-size or batch-age
    # threshold tripped lost every line it had logged, which in practice was all of them -- the
    # audit log for a pipeline run came out empty and there was nothing to say why.
    job_state_client = job_state()
    try:
        logger.info("Starting Kafka consumer")
        consumer = create_consumer(kafka_scrapping_topic, kafka_servers, scrapping_group_id)
        logger.info("Kafka connected topic=%s group=%s",kafka_scrapping_topic, scrapping_group_id)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while not shutdown_event.is_set():
                message = consumer.poll(timeout_ms=1000)
                # The workers hand their finished offsets back through the tracker and the
                # commit happens here, because the consumer belongs to this thread alone.
                offset_tracker.commit_ready(consumer)
                if not message:
                    continue
                for _, records in message.items():
                    for record in records:
                        payload = record.value
                        if not payload:
                            continue
                        # Control memory
                        semaphore.acquire()
                        offset_tracker.started(record.partition, record.offset)
                        executor.submit(execute_task_wrapper,record, payload, job_state_client)
    except Exception as ex:
        logger.exception("Kafka listener failed %s",str(ex))
    finally:
        if consumer:
            # Leaving the pool waited for the running tasks, so what they finished on the way
            # out is still sitting in the tracker unclaimed.
            offset_tracker.commit_ready(consumer)
            consumer.close()
            logger.info("Kafka consumer closed")

# ------------------------------------------------------------------------------
# Thread Wrapper
# ------------------------------------------------------------------------------
def execute_task_wrapper(message, payload, job_state_client):
    try:
        execute_task(message, payload, job_state_client)
        # Record the offset only after success, and only up to the lowest offset still being
        # worked on. The polling thread is the one that commits it.
        offset_tracker.finished(message.topic, message.partition, message.offset)
    except Exception as ex:
        logger.exception("Task failed %s",str(ex))
        # A failed record must not hold its partition's commit point for ever; the job is already
        # marked Failed, so let the offsets past it move on -- without claiming this one.
        offset_tracker.failed(message.partition, message.offset)
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

        # The run's own proof for every callback below (see JobStateClient._auth_headers).
        job_state_client.remember_run_token(job_id, job_queue_id, payload.get("callbackToken"))
        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.RUNNING,"Job started")
        # AI steps the pipeline hands to this worker run first, and land in the document as
        # ordinary tags, so the parser and the task below know nothing about them.
        payload = dict(payload)
        payload["taskPayload"] = resolve_ai_steps(payload.get("taskPayload"), job_id, job_queue_id,
                                                  payload.get("callbackToken"),
                                                  audit=lambda line: job_state_client.job_audit_log(job_id, job_queue_id, line))
        task_payload = extract_task_payload(pipeline_id, payload)
        task_payload["job_id"] = job_id
        task_payload["job_queue_id"] = job_queue_id
        # --------------------------------------------------
        # Pipeline Router
        # --------------------------------------------------
        route = PIPELINE_TASKS.get(pipeline_id)
        if not route:
            raise ValueError(f"Unknown pipeline {pipeline_id}")
        module_name, function_name = route
        task_function = getattr(importlib.import_module(module_name), function_name)
        task_function(task_payload)

        # Log lines are buffered, so they must be sent before the run is marked done -- a
        # reader opening a completed job's logs must not find the last of them in a buffer.
        job_state_client.flush_logs(job_id, job_queue_id)
        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.COMPLETED,"Job completed successfully")
    except Exception as ex:
        logger.exception("Job failed job_id=%s",job_id)
        # Flush on failure too: the buffered lines are usually what explains it.
        job_state_client.flush_logs(job_id, job_queue_id)
        update_job_status(job_state_client, job_id, job_queue_id, JobStatus.FAILED, str(ex))
        raise
    finally:
        # The run is over either way; its token is spent on the server too.
        job_state_client.forget_run_token(job_id, job_queue_id)

# ------------------------------------------------------------------------------
# Payload Parser
# ------------------------------------------------------------------------------
def extract_task_payload(pipeline_id, payload):
    parser = pipeline_xml_parser.get(pipeline_id)
    if not parser:
        raise ValueError(f"No parser found for {pipeline_id}")
    task_payload = parser(payload.get("taskPayload"))
    # Every parser answers None for XML it could not read. Without this the caller's
    # task_payload["job_id"] = ... is what fails, and the operator is shown
    # "'NoneType' object does not support item assignment" for what is really a
    # malformed payload on their task.
    if task_payload is None:
        raise ValueError(
            f"Task payload for {pipeline_id} could not be parsed; check the task's XML"
        )
    return task_payload

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