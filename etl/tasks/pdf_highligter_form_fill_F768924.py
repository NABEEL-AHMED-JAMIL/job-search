import os
import time
import logging
import colorlog
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
# class imports
from etl.util.job_state_client import JobStateClient
from etl.util.minio_client import MinioClient

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# ENV DATA LOAD
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
minio_bucket = os.getenv("MINIO_BUCKET_NAME", "etl-bucket")
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
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
minio_client = MinioClient()

def _build_retrying_session():
    """
        Method use to build a requests session that retries transient 5xx errors.
    """
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def _call_api(task_payload, method, url, action, **kwargs):
    """
        Method use to call an API and share the success/failure handling (status check,
        json/text parsing, logging, job-audit-log on failure) used by every PDF Highlighter
        HTTP call.
    """
    session = _build_retrying_session()
    try:
        response = session.request(method, url, timeout=10, **kwargs)
    except Exception as e:
        logger.error("ERROR calling %s API: %s", action, str(e), exc_info=True)
        job_audit_log(task_payload, f"{action} request failed: {e}")
        raise

    try:
        payload = response.json()
    except Exception:
        payload = response.text

    if response.status_code == 200:
        logger.info("%s succeeded", action)
        return payload["data"] if isinstance(payload, dict) else payload
    else:
        logger.error("FAILED: status=%s response=%s", response.status_code, response.text)
        job_audit_log(task_payload, f"{action} failed with status {response.status_code}")
        raise ValueError(f"{action} failed with status {response.status_code}")

def authenticate_session(task_payload):
    pass

def submissions_fill_form(payload):
    pass

def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)

# PDF Highlighter
def pdf_highlighter_form_film(task_payload):
    pass
