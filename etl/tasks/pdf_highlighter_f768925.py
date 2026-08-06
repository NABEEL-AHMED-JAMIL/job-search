import io
import re
import time
import os
import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
# class imports
from etl.util.job_state_client import JobStateClient
from etl.util.minio_client import MinioClient
from etl.util.logging_config import get_logger

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
logger = get_logger(__name__)
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
minio_client = MinioClient()

_SELECTOR_PATH_RE = re.compile(r"^page\[(\d+)\]/text\(\)\[(\d+):(\d+)\]$")

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
        Read every PDF under targetInputFileFolder/organizationsTask in MinIO (bucket
        MINIO_BUCKET_NAME), crop each mapped field's bounding box out of its page with
        pdfplumber (coordinates are PDF points, top-left origin — the same space the field
        mapping was captured in), and upload one row per file to targetOutputFileFolder in
        MinIO in targetOutputType format. Path config (bucket/targetInputFileFolder/
        organizationsTask, bucket/targetOutputFileFolder/job_.../taskUuid) stays exactly the
        same as before — only the storage backend moved from local disk to MinIO.
        <pdfHighlighter>
            <targetInputFileFolder>/Users/nabeel.amd93/Desktop/PDFHighlighter/Input</targetInputFileFolder>
            <targetOutputFileFolder>/Users/nabeel.amd93/Desktop/PDFHighlighter/Output</targetOutputFileFolder>
            <targetOutputType>CSV</targetOutputType>
        </pdfHighlighter>
    """
    input_prefix = f"{pdf_highlighter.get('targetInputFileFolder')}/{pdf_highlighter.get('organizationsTask')}"
    output_folder = pdf_highlighter.get("targetOutputFileFolder")
    output_type = (pdf_highlighter.get("targetOutputType") or "CSV").upper()

    if not all([input_prefix, output_folder]):
        logger.error("Missing input/output folder information in task payload.")
        job_audit_log(task_payload, "Missing input/output folder information in task payload.")
        raise ValueError("Missing targetInputFileFolder/targetOutputFileFolder in task payload.")

    fields = pdf_highlighter_payload.get("fields") or []
    if not fields:
        logger.error("No field mapping returned for task.")
        job_audit_log(task_payload, "No field mapping returned for task.")
        raise ValueError("No field mapping returned for task; nothing to extract.")

    rows = []
    for object_name in sorted(minio_client.list_objects(minio_bucket, prefix=input_prefix)):
        file_name = object_name.rsplit("/", 1)[-1]
        if not file_name.lower().endswith(".pdf"):
            continue

        logger.info(f"Processing {file_name}")
        job_audit_log(task_payload, f"Processing {file_name}")
        pdf_bytes = minio_client.get_object_bytes(minio_bucket, object_name)
        if pdf_bytes is None:
            logger.error(f"Could not read {object_name} from MinIO bucket {minio_bucket}.")
            job_audit_log(task_payload, f"Could not read {object_name} from MinIO bucket {minio_bucket}.")
            continue
        rows.append(extract_fields_from_pdf(file_name, pdf_bytes, fields))

    if not rows:
        logger.error(f"No supported files found in {minio_bucket}/{input_prefix}.")
        job_audit_log(task_payload, f"No supported files found in {minio_bucket}/{input_prefix}.")
        raise ValueError(f"No supported files found in {minio_bucket}/{input_prefix}.")

    task_uuid = (pdf_highlighter_payload.get("task") or {}).get("uuid")
    if not task_uuid:
        logger.error("No task uuid returned in field mapping response.")
        job_audit_log(task_payload, "No task uuid returned in field mapping response.")
        raise ValueError("No task uuid returned in field mapping response.")

    job_output_prefix = "/".join([
        output_folder,
        f"job_{task_payload['job_id']}_queue_{task_payload['job_queue_id']}",
        task_uuid
    ])
    output_object_name = write_extracted_rows(job_output_prefix, rows, output_type)
    logger.info(f"Extraction complete. {len(rows)} file(s) written to {minio_bucket}/{output_object_name}")
    job_audit_log(task_payload, f"Extraction complete. {len(rows)} file(s) written to {minio_bucket}/{output_object_name}")

def _is_truthy(value):
    """
        Method use to interpret useXpathFirst whether the field mapping API gives it as a
        real JSON boolean or as a string (e.g. "True"/"false") — a bare truthiness check on
        a string is wrong here since a non-empty "False" would otherwise still be truthy.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)

def _page_spans(fitz_page):
    """
        Method use to list a PyMuPDF page's text spans in reading order, skipping blank
        ones. A "span" here is a run of text from one PDF content-stream text-show
        operation (Tj/TJ) with consistent formatting — the same granularity pdf.js's
        getTextContent() items use in the browser, verified index-for-index against a real
        ticket PDF (page[1]/text()[13:13] and [49:49] both matched exactly). pdfplumber's
        extract_words() instead re-tokenizes by whitespace, which does not line up.
    """
    spans = []
    for block in fitz_page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    spans.append(span["text"])
    return spans

def extract_field_by_path(fitz_doc, path):
    """
        Method use to resolve a field's value from its selector `path`
        (e.g. "page[1]/text()[13:13]") by indexing into the page's PyMuPDF text spans.
        Index/order-based (rather than coordinate-based) so it keeps resolving correctly
        even if the section's position shifts between PDF instances of the same template —
        as long as the spans before it on the page stay the same in count and order.
        Returns None if the path is malformed, the page doesn't exist, or the index is out
        of range, so the caller can fall back to coordinates.
    """
    match = _SELECTOR_PATH_RE.match(path or "")
    if not match:
        return None
    page_number, start, end = (int(g) for g in match.groups())
    if page_number < 1 or page_number > fitz_doc.page_count:
        return None

    spans = _page_spans(fitz_doc[page_number - 1])
    if start > end or start < 0 or end >= len(spans):
        return None

    value = " ".join(spans[start:end + 1]).strip()
    return value or None

def extract_fields_from_pdf(file_name, pdf_bytes, fields):
    """
        Method use to resolve each field's value and return one
        {file_name, label1: text1, label2: text2, ...} row for the file. When a field's
        useXpathFirst is set, its selector `path` is tried first (PyMuPDF span index); if
        that doesn't resolve, or useXpathFirst is off, the field's bounding box is cropped
        directly via pdfplumber (the original coordinate-only behavior).
    """
    row = {"file_name": file_name}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf, fitz.open(stream=pdf_bytes, filetype="pdf") as fitz_doc:
        for field in fields:
            label = field.get("label")
            page_number = field.get("page") or 1
            if page_number < 1 or page_number > len(pdf.pages):
                logger.error(f"{file_name}: field '{label}' references page {page_number}, but file has {len(pdf.pages)} page(s).")
                row[label] = None
                continue
            page = pdf.pages[page_number - 1]

            value = None
            selector_path = field.get("selectorPath")
            if _is_truthy(field.get("useXpathFirst")) and selector_path:
                value = extract_field_by_path(fitz_doc, selector_path)
                if value is None:
                    logger.warning(f"{file_name}: field '{label}' path selector did not resolve on page {page_number}; falling back to coordinates.")

            if value is None:
                bbox = (field["x"], field["y"], field["x"] + field["width"], field["y"] + field["height"])
                value = (page.crop(bbox).extract_text() or "").strip()

            row[label] = value
    return row

def write_extracted_rows(output_prefix, rows, output_type):
    """
        Method use to upload extracted rows to targetOutputFileFolder in MinIO in the
        requested format.
    """
    df = pd.DataFrame(rows)
    file_stem = f"pdf_highlighter_extract_{int(time.time())}"
    buffer = io.BytesIO()

    if output_type == "CSV":
        object_name = f"{output_prefix}/{file_stem}.csv"
        df.to_csv(buffer, index=False)
        content_type = "text/csv"
    elif output_type in ("XLSX", "EXCEL"):
        object_name = f"{output_prefix}/{file_stem}.xlsx"
        df.to_excel(buffer, index=False)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif output_type == "JSON":
        object_name = f"{output_prefix}/{file_stem}.json"
        buffer.write(df.to_json(orient="records", indent=2).encode("utf-8"))
        content_type = "application/json"
    else:
        raise ValueError(f"Unsupported targetOutputType: {output_type}")

    if not minio_client.upload_bytes(minio_bucket, object_name, buffer.getvalue(), content_type=content_type):
        raise RuntimeError(f"Could not upload extracted output to {minio_bucket}/{object_name}")
    return object_name

def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)

def pdf_highlighter_text_extraction_etl(task_payload):
    """
        Extract text from PDF files and highlight specific terms.
        This function will handle the ETL process for PDF text extraction and highlighting.
    """
    auth_payload = authenticate_session(task_payload)
    pdf_highlighter = task_payload.get("pdfHighlighter", {})
    pdf_highlighter_payload = fetch_highlighters_mapping(task_payload, pdf_highlighter, auth_payload)
    extract_fields_to_output(task_payload, pdf_highlighter, pdf_highlighter_payload)
