"""
Kafka Listener for test-topic (Production Style)
"""
import os
import time
import threading
from dotenv import load_dotenv
from multiprocessing import Process
from concurrent.futures import ThreadPoolExecutor
from etl.tpd.tpd_kafka_config import create_consumer
from etl.tpd.offset_tracker import OffsetTracker
from etl.util.xml_parser import tpd_test_task_payload_parser
from etl.util.ai_steps import resolve_ai_steps
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
# Submission is bounded by a free worker: submit() never blocks, so without this the loop
# polls far faster than ten threads can drain and builds an unbounded backlog of futures.
semaphore = threading.Semaphore(MAX_WORKERS)
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
offset_tracker = OffsetTracker()

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

        # Thread pool inside each consumer process.
        #
        # The offsets are committed after a message has been handled, not when it was polled.
        # With auto-commit the consumer marked work done the moment it handed it to the pool,
        # so anything that did not finish -- a restart, a raised handler, a queued future that
        # never ran -- was gone for good: never redelivered, and its job left showing Running
        # for ever. A run of 500 ended with total lag zero and 68 jobs still in flight, which
        # is that hazard exactly.
        #
        # Waiting for the first future to finish and committing then was no better: a bare
        # commit() claims the consumer's position, which has already run past the other nine
        # in the batch. The OffsetTracker exists for that -- see its docstring -- and it is
        # shared with tpd_scrapping_listener so the two cannot drift apart again.
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while True:
                records = consumer.poll(timeout_ms=1000)
                # Committing is this thread's job: KafkaConsumer is not thread-safe, so the
                # workers only report what they finished and the commit happens here.
                offset_tracker.commit_ready(consumer)
                if not records:
                    continue
                for _, batch in records.items():
                    for message in batch:
                        payload = message.value
                        # An unreadable payload is not work that was done, so nothing is
                        # committed for it; the next record that succeeds carries it past.
                        if not payload:
                            continue
                        # Backpressure: wait for a free worker before accepting more.
                        semaphore.acquire()
                        offset_tracker.started(message.partition, message.offset)
                        executor.submit(handle_message, message, payload)

    except KeyboardInterrupt:
        logger.info("Listener stopped by user")
    except Exception as ex:
        logger.exception("Kafka listener error: %s", str(ex))
    finally:
        if consumer:
            # Leaving the pool waited for the running tasks, so what they finished on the way
            # out is still sitting in the tracker unclaimed.
            offset_tracker.commit_ready(consumer)
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
        offset_tracker.finished(message.topic, message.partition, message.offset)

    except Exception as ex:
        logger.exception(
            "Failed offset=%s error=%s",
            message.offset,
            str(ex)
        )
        # The job is already marked Failed, so the record is released rather than held --
        # but nothing is committed on its behalf.
        offset_tracker.failed(message.partition, message.offset)
    finally:
        semaphore.release()

# ------------------------------------------------------------------------------
# Job Processing
# ------------------------------------------------------------------------------
def execute_task(payload: dict):
    """
        Process a single job payload.
    """
    # The backend publishes these at the top level, the same as every other listener reads
    # them. Reading them from a nested "jobQueue" object -- which is not in the message --
    # meant every message was rejected before any work started, so this loop had never
    # actually run against a real dispatch.
    job_id = payload.get("jobId")
    job_queue_id = payload.get("jobQueueId")

    if not job_id or not job_queue_id:
        raise ValueError("jobId or jobQueueId missing from payload")

    try:
        logger.info("Starting Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)
        # The run's own proof for every callback (see JobStateClient._auth_headers).
        job_state_client.remember_run_token(job_id, job_queue_id, payload.get("callbackToken"))
        update_job_status(job_id, job_queue_id, JobStatus.RUNNING,f"Job {job_id} is running.")
        # AI steps handed to this worker run first and land in the document as ordinary tags.
        payload = dict(payload)
        payload["taskPayload"] = resolve_ai_steps(payload.get("taskPayload"), job_id, job_queue_id,
                                                  payload.get("callbackToken"),
                                                  audit=lambda line: job_state_client.job_audit_log(job_id, job_queue_id, line))
        task_payload = extract_task_payload(payload)
        process_batches(job_id, job_queue_id, task_payload)
        # Before the run is marked done: a reader opening a completed job's logs must not find
        # the last lines still sitting in a buffer.
        job_state_client.flush_logs(job_id, job_queue_id)
        update_job_status(job_id, job_queue_id, JobStatus.COMPLETED,f"Job {job_id} completed successfully.")
        logger.info("Complete Job. jobId=%s jobQueueId=%s",job_id, job_queue_id)

    except Exception as ex:
        logger.exception("Job failed. jobId=%s", job_id)
        # Flush on the failure path too -- the buffered lines are usually what explains it.
        job_state_client.flush_logs(job_id, job_queue_id)
        update_job_status(job_id, job_queue_id, JobStatus.FAILED, f"Job {job_id} failed due to {str(ex)}")
        raise
    finally:
        job_state_client.forget_run_token(job_id, job_queue_id)


def extract_task_payload(payload: dict) -> dict:
    """
        Extract and parse task payload.
    """
    # Also top level, as tpd_scrapping_listener reads it.
    task_payload_xml = payload.get("taskPayload")
    parsed_payload = tpd_test_task_payload_parser(task_payload_xml)
    logger.info("Parsed Task Payload: %s", parsed_payload)
    return parsed_payload


def require_batch_range(task_payload):
    """
        The <start> and <end> settings as ints, or a refusal naming the one that was not there.

        tpd_test_task_payload_parser answers None for a tag that is absent -- and for a payload
        it could not read at all it answers None for both -- so int() was handed None and the
        run died as "int() argument must be a string, a bytes-like object or a real number, not
        'NoneType'". That was observed while this listener drained the backlog on
        test-topic for job 2104, whose message predates these tags. The message names neither
        the tag nor the job, and points at a line inside a conversion rather than at the task
        payload an operator has to go and correct.

        A missing setting is deliberately NOT defaulted to zero: range(0, 0) processes nothing
        and the run would then be marked Completed, so a task with a broken payload would read
        as one that had done its work. Failing by name is the lesser harm -- the same fail-fast
        convention Pipeline.require applies to the pipeline family, and the same one
        tpd_scrapping_listener applies to a payload it cannot parse.
    """
    # Blank counts as absent: a tag the console rendered and the operator left empty means "not
    # set" exactly as an omitted one does -- and int("  ") is another stack trace from inside
    # the conversion.
    #
    # `is None` rather than `or ""`, which would have called an integer 0 missing. The parser
    # hands these back as strings today, so it costs nothing now; it stops a caller that passes
    # a real 0 -- a legitimate start of range -- from being refused for a tag it did supply.
    missing = [tag for tag in ("start", "end")
               if task_payload.get(tag) is None or not str(task_payload.get(tag)).strip()]
    if missing:
        raise ValueError(
            f"Task payload is missing required setting(s): {', '.join(missing)}"
        )

    batch_range = []
    for tag in ("start", "end"):
        value = str(task_payload.get(tag)).strip()
        try:
            batch_range.append(int(value))
        except ValueError:
            # Re-worded for the same reason as above: int()'s own "invalid literal for int()"
            # does not say which of the two settings carried the bad value.
            raise ValueError(f"Task payload <{tag}> must be a whole number, got '{value}'")
    return batch_range


def process_batches(job_id, job_queue_id, task_payload):
    """
        Execute business processing.
    """
    start, end = require_batch_range(task_payload)
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
