import io
import json
import os
import time
import logging
import colorlog
import pandas as pd
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

def authenticate_session(task_payload, username, password, auth_url):
    """
        Log in with a single username/password against auth_url and return the raw login
        response (token, organizationUuid, ...). Just the one API call -- the accounts-CSV
        loop and the skip-on-failure decision live in pdf_highlighter_form_film, which calls
        this once per account.
    """
    return _call_api(
        task_payload, "POST", auth_url, f"Authentication for {username}",
        json={"username": username, "password": password}
    )

def fetch_pdf_extract_data(task_payload, input_object_path):
    """
        Read the extracted PDF field-mapping rows (produced by F768925) from MinIO. This is
        shared source data for every account's form submission -- not per-user -- so
        pdf_highlighter_form_film fetches it exactly once, not once per login.
    """
    data_bytes = minio_client.get_object_bytes(minio_bucket, input_object_path)
    if data_bytes is None:
        logger.error(f"Could not read input object {input_object_path} from MinIO bucket {minio_bucket}.")
        job_audit_log(task_payload, f"Could not read input object {input_object_path} from MinIO bucket {minio_bucket}.")
        raise ValueError(f"Could not read input object {minio_bucket}/{input_object_path}.")

    try:
        return json.loads(data_bytes.decode("utf-8"))
    except Exception as e:
        logger.error(f"Could not parse input object {input_object_path} as JSON: {e}")
        job_audit_log(task_payload, f"Could not parse input object {input_object_path} as JSON: {e}")
        raise ValueError(f"Could not parse input object {minio_bucket}/{input_object_path} as JSON.")

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
    """
        Entry point for F768924. Fetches the extracted PDF field-mapping data
        (highlighter.input_object_path) once up front -- it's the same shared source data
        for every account, so failing fast here means a missing/corrupt input file doesn't
        waste time authenticating a whole batch of users first. Then reads every account
        from the session's accounts CSV (columns: username, password, active), logs each
        one in via authenticate_session, and skips (logs a warning, keeps going) any
        account that fails to log in -- one bad account does not stop the rest of the
        batch. Returns the extracted data plus the list of successfully authenticated
        accounts, one dict per user: {"username": ..., **login_response} (token,
        organizationUuid, ...) -- for the next step (calling the panel/fields/submissions
        APIs with each user's info + token, against the extracted data) to pass along later.
        <session>
            <accounts>highlighter/account/cvsh-user-account.csv</accounts>
            <auth_url> http://localhost:9999/v1/api/auth/login</auth_url>
        </session>
        <highlighter>
            <input_object_path>highlighter/output/job_1014_queue_1050/.../pdf_highlighter_extract_....json</input_object_path>
        </highlighter>
    """
    highlighter = task_payload.get("highlighter", {})
    # input object path the data that need to be filled in the form, produced by F768925
    input_object_path = highlighter.get("input_object_path")
    if not input_object_path:
        logger.error("Missing highlighter.input_object_path in task payload.")
        job_audit_log(task_payload, "Missing highlighter.input_object_path in task payload.")
        raise ValueError("Missing highlighter.input_object_path in task payload.")
    # target form which need to fill base on the uuid
    form_uuid = highlighter.get("form_uuid")
    if not form_uuid:
        logger.error("Missing highlighter.form_uui in task payload.")
        job_audit_log(task_payload, "Missing highlighter.form_uui in task payload.")
        raise ValueError("Missing highlighter.form_uui in task payload.")

    # Fetch the extracted PDF field-mapping data from MinIO (produced by F768925) once up front.
    extract_data = fetch_pdf_extract_data(task_payload, input_object_path)

    # Fetch the accounts CSV from MinIO and authenticate each account, skipping any that fail to log in.
    session_info = task_payload.get("session", {})
    accounts_object_name = session_info.get("accounts")
    auth_url = (session_info.get("auth_url") or "").strip()

    if not all([accounts_object_name, auth_url]):
        logger.error("Missing session information in task payload.")
        job_audit_log(task_payload, "Missing session information in task payload.")
        raise ValueError("Missing session information in task payload. Please provide accounts and auth_url.")

    # Read the accounts CSV from MinIO. If it can't be read, log an error and raise an exception.
    csv_bytes = minio_client.get_object_bytes(minio_bucket, accounts_object_name)
    if csv_bytes is None:
        logger.error(f"Could not read accounts file {accounts_object_name} from MinIO bucket {minio_bucket}.")
        job_audit_log(task_payload, f"Could not read accounts file {accounts_object_name} from MinIO bucket {minio_bucket}.")
        raise ValueError(f"Could not read accounts file {minio_bucket}/{accounts_object_name}.")

    # keep_default_na=False -- an empty username/password cell should read as "", not NaN
    # (str(NaN) is the literal text "nan", which would otherwise pass the blank-check below).
    accounts_df = pd.read_csv(io.BytesIO(csv_bytes), keep_default_na=False)
    if not {"username", "password"}.issubset(accounts_df.columns):
        logger.error(f"Accounts file {accounts_object_name} is missing required 'username'/'password' columns.")
        job_audit_log(task_payload, f"Accounts file {accounts_object_name} is missing required 'username'/'password' columns.")
        raise ValueError("Accounts CSV must have 'username' and 'password' columns.")

    authenticated_sessions = []
    for row in accounts_df.to_dict(orient="records"):
        username = str(row.get("username") or "").strip()
        password = str(row.get("password") or "").strip()
        active = str(row.get("active") or "").strip()
        if not username or not password or not active:
            logger.warning(f"Skipping account row with missing username/password: {row}")
            continue
        # Only attempt to authenticate accounts marked as active ("yes").
        elif active == "yes":
            try:
                login_payload = authenticate_session(task_payload, username, password, auth_url)
            except Exception as e:
                logger.warning(f"Skipping {username}: login failed ({e})")
                continue
            # If we got here, the login succeeded; add this account's info to the list of authenticated sessions.
            authenticated_sessions.append({"username": username, **login_payload})

    if not authenticated_sessions:
        logger.error("No accounts could be authenticated.")
        job_audit_log(task_payload, "No accounts could be authenticated.")
        raise ValueError("No accounts could be authenticated; nothing to process.")

    logger.info(f"Authenticated {len(authenticated_sessions)}/{len(accounts_df)} account(s).")
    job_audit_log(task_payload, f"Authenticated {len(authenticated_sessions)}/{len(accounts_df)} account(s).")
    # Next step (guided later): for each entry in authenticated_sessions, call the
    # panel/fields/submissions APIs with that user's info + token, against extract_data.
    return {
        "extract_data": extract_data,
        "authenticated_sessions": authenticated_sessions
    }

