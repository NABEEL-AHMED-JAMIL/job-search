import time
import os
import logging
import colorlog
import pandas as pd
import pdfplumber
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from etl.util.job_state_client import JobStateClient

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# ENV DATA LOAD
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
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
    """
        Log in with the session credentials in the task payload and return the auth response
        (token + organizationUuid) used by downstream calls.
        <session>
            <username>nabeel91</username>
            <password>LHR-B@llistic1</password>
            <auth> http://localhost:9999/v1/api/auth/login</auth>
        </session>
    """
    session_info = task_payload.get("session", {})
    username = session_info.get("username")
    password = session_info.get("password")
    auth_url = session_info.get("auth")

    if not all([username, password, auth_url]):
        logger.error("Missing session information in task payload.")
        job_audit_log(task_payload, "Missing session information in task payload.")
        raise ValueError("Missing session information in task payload. Please provide username, password, and auth URL.")

    return _call_api(task_payload, "POST", auth_url, "Authentication", json={"username": username, "password": password})


def fetch_highlighters_mapping(task_payload, pdf_highlighter, auth_payload):
    """
        Fetch the task + field mapping for the PDF highlighter task named in the task payload.
        <pdfHighlighter>
            <organizationsTask>ZER23423</organizationsTask>
            <fieldMappingUrl>http://localhost:9999/v1/api/organizations/{orgUuid}/pdf-highlighters/by-name/{organizationsTask}</fieldMappingUrl>
        </pdfHighlighter>
    """
    organizations_task = pdf_highlighter.get("organizationsTask")
    field_mapping_url = pdf_highlighter.get("fieldMappingUrl")

    if not all([organizations_task, field_mapping_url]):
        logger.error("Missing task information in task payload.")
        job_audit_log(task_payload, "Missing task information in task payload.")
        raise ValueError("Missing task information in task payload. Please provide task information in task payload.")

    organization_uuid = auth_payload["organizationUuid"]
    organization_token = auth_payload["token"]
    field_mapping_url = field_mapping_url.replace("{organizationUuid}", organization_uuid).replace("{organizationsTask}", organizations_task)

    return _call_api(
        task_payload, "GET", field_mapping_url, "Field mapping fetch",
        headers={"Authorization": f"Bearer {organization_token}"}
    )


def extract_fields_to_output(task_payload, pdf_highlighter, pdf_highlighter_payload):
    """
        Read every PDF in targetInputFileFolder, crop each mapped field's bounding box out of
        its page with pdfplumber (coordinates are PDF points, top-left origin — the same
        space the field mapping was captured in), and write one row per file to
        targetOutputFileFolder in targetOutputType format.
        <pdfHighlighter>
            <targetInputFileFolder>/Users/nabeel.amd93/Desktop/PDFHighlighter/Input</targetInputFileFolder>
            <targetOutputFileFolder>/Users/nabeel.amd93/Desktop/PDFHighlighter/Output</targetOutputFileFolder>
            <targetOutputType>CSV</targetOutputType>
        </pdfHighlighter>
    """
    input_folder = f"{pdf_highlighter.get('targetInputFileFolder')}/{pdf_highlighter.get('organizationsTask')}"
    output_folder = pdf_highlighter.get("targetOutputFileFolder")
    output_type = (pdf_highlighter.get("targetOutputType") or "CSV").upper()

    if not all([input_folder, output_folder]):
        logger.error("Missing input/output folder information in task payload.")
        job_audit_log(task_payload, "Missing input/output folder information in task payload.")
        raise ValueError("Missing targetInputFileFolder/targetOutputFileFolder in task payload.")

    fields = pdf_highlighter_payload.get("fields") or []
    if not fields:
        logger.error("No field mapping returned for task.")
        job_audit_log(task_payload, "No field mapping returned for task.")
        raise ValueError("No field mapping returned for task; nothing to extract.")

    rows = []
    for file_name in sorted(os.listdir(input_folder)):
        input_file_path = os.path.join(input_folder, file_name)
        if not (os.path.isfile(input_file_path) and file_name.lower().endswith(".pdf")):
            continue

        logger.info(f"Processing {file_name}")
        job_audit_log(task_payload, f"Processing {file_name}")
        rows.append(extract_fields_from_pdf(file_name, input_file_path, fields))

    if not rows:
        logger.error(f"No supported files found in {input_folder}.")
        job_audit_log(task_payload, f"No supported files found in {input_folder}.")
        raise ValueError(f"No supported files found in {input_folder}.")

    task_uuid = (pdf_highlighter_payload.get("task") or {}).get("uuid")
    if not task_uuid:
        logger.error("No task uuid returned in field mapping response.")
        job_audit_log(task_payload, "No task uuid returned in field mapping response.")
        raise ValueError("No task uuid returned in field mapping response.")

    job_output_folder = os.path.join(
        output_folder,
        f"job_{task_payload['job_id']}_queue_{task_payload['job_queue_id']}",
        task_uuid
    )
    output_file_path = write_extracted_rows(job_output_folder, rows, output_type)
    logger.info(f"Extraction complete. {len(rows)} file(s) written to {output_file_path}")
    job_audit_log(task_payload, f"Extraction complete. {len(rows)} file(s) written to {output_file_path}")


def extract_fields_from_pdf(file_name, input_file_path, fields):
    """
        Method use to crop each field's bounding box out of its page and return one
        {file_name, label1: text1, label2: text2, ...} row for the file.
    """
    row = {"file_name": file_name}
    with pdfplumber.open(input_file_path) as pdf:
        for field in fields:
            label = field.get("label")
            page_number = field.get("page") or 1
            if page_number < 1 or page_number > len(pdf.pages):
                logger.error(f"{file_name}: field '{label}' references page {page_number}, but file has {len(pdf.pages)} page(s).")
                row[label] = None
                continue
            page = pdf.pages[page_number - 1]
            bbox = (field["x"], field["y"], field["x"] + field["width"], field["y"] + field["height"])
            row[label] = (page.crop(bbox).extract_text() or "").strip()
    return row


def write_extracted_rows(output_folder, rows, output_type):
    """
        Method use to write extracted rows to targetOutputFileFolder in the requested format.
    """
    os.makedirs(output_folder, exist_ok=True)
    df = pd.DataFrame(rows)
    file_stem = f"pdf_highlighter_extract_{int(time.time())}"

    if output_type == "CSV":
        output_file_path = os.path.join(output_folder, f"{file_stem}.csv")
        df.to_csv(output_file_path, index=False)
    elif output_type in ("XLSX", "EXCEL"):
        output_file_path = os.path.join(output_folder, f"{file_stem}.xlsx")
        df.to_excel(output_file_path, index=False)
    elif output_type == "JSON":
        output_file_path = os.path.join(output_folder, f"{file_stem}.json")
        df.to_json(output_file_path, orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported targetOutputType: {output_type}")

    return output_file_path


def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)

# PDF Highlighter
def pdf_highlighter_text_extraction_etl(task_payload):
    """
        Extract text from PDF files and highlight specific terms.
        This function will handle the ETL process for PDF text extraction and highlighting.
    """
    auth_payload = authenticate_session(task_payload)
    pdf_highlighter = task_payload.get("pdfHighlighter", {})
    pdf_highlighter_payload = fetch_highlighters_mapping(task_payload, pdf_highlighter, auth_payload)
    extract_fields_to_output(task_payload, pdf_highlighter, pdf_highlighter_payload)
