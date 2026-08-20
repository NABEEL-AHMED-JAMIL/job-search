"""
    Send Email Batch (F76800)
    @author: Nabeel Ahmed Jamil

    Fetches SMTP + template config from the Dynamic Form submission
    referenced by email_config_uuid (a fetchSubmissionByUuid share link -- no
    auth needed), downloads the recipients CSV from MinIO, renders the
    {{variable}} template per row, and sends one email per recipient.

    NOTE: the submission payload only exposes "username" + "token_id" as
    credentials (no explicit "password" field) -- token_id is used as the
    SMTP password, which matches how Mailtrap sandbox inboxes hand out
    their SMTP creds. If a real provider later supplies a distinct
    password, add a "password" tag to the submission and prefer it here.
"""
import io
import json
import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import requests
from dotenv import load_dotenv

from etl.util.job_state_client import JobStateClient
from etl.util.minio_client import MinioClient
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
etl_event_url = os.getenv("ETL_EVENT_URL")
smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
smtp_timeout_seconds = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
smtp_send_delay_seconds = float(os.getenv("SMTP_SEND_DELAY_SECONDS", "1.2"))
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
minio_client = MinioClient()

TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def fetch_email_config(email_config_uuid):
    """
        GET the Dynamic Form submission (ResponseDto JSON) that carries the
        SMTP connection details and the email template config. The URL is built
        from ETL_EVENT_URL (env-configured per execution environment) plus the
        submission uuid -- never a URL stored in pipeline config, since that would
        only be valid for whichever environment happened to write it.
    """
    if not etl_event_url:
        raise ValueError("ETL_EVENT_URL is not configured")
    email_config_url = f"{etl_event_url}/dynamicForm.json/fetchSubmissionByUuid?uuid={email_config_uuid}"
    response = requests.get(email_config_url, timeout=15)
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "SUCCESS":
        raise ValueError(f"email_config fetch failed: {body.get('message')}")
    payload = (body.get("data") or {}).get("payload") or {}
    if not payload:
        raise ValueError("email_config response missing data.payload")
    from_email = payload.get("email")
    if not from_email:
        raise ValueError("email_config response missing data.payload.email (used as From address)")
    template_config_raw = payload.get("template_config")
    return {
        "host": payload.get("host"),
        "port": int(payload.get("port")),
        "username": payload.get("username"),
        "token_id": payload.get("token_id"),
        "from_email": from_email,
        "template_config": json.loads(template_config_raw) if template_config_raw else {}
    }


def load_recipients(task_payload):
    """
        Download the recipients CSV from MinIO and return it as a list of
        dict rows (one per recipient), keyed by CSV column name.
    """
    bucket = task_payload.get("recipients_bucket")
    object_name = task_payload.get("recipients_object")
    if not bucket or not object_name:
        raise ValueError("recipients_bucket/recipients_object missing from task payload")
    csv_bytes = minio_client.get_object_bytes(bucket, object_name)
    if csv_bytes is None:
        raise ValueError(f"recipients CSV not found bucket={bucket} object={object_name}")
    data_frame = pd.read_csv(io.BytesIO(csv_bytes), dtype=str).fillna("")
    return data_frame.to_dict(orient="records")


def render_template(template_text, row):
    """
        Replace every {{variable}} in template_text with the matching
        column value from row. Unknown variables are left blank.
    """
    return TEMPLATE_VAR_PATTERN.sub(lambda m: str(row.get(m.group(1), "")), template_text or "")


def send_smtp_email(smtp_config, to_email, subject, body):
    from_email = smtp_config["from_email"]
    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=smtp_timeout_seconds) as server:
        if smtp_use_tls:
            server.starttls()
        server.login(smtp_config["username"], smtp_config["token_id"])
        server.sendmail(from_email, [to_email], message.as_string())


def send_email_batch(task_payload):
    """
        Entry point routed from execute_task for pipeline F76800.
        task_payload: dict returned by xml_parser.parse_76800, plus job_id/job_queue_id.
    """
    smtp_config = fetch_email_config(task_payload["email_config_uuid"])
    template_config = smtp_config["template_config"]
    subject_template = template_config.get("subject", "")
    body_template = template_config.get("template", "")

    recipients = load_recipients(task_payload)
    logger.info(
        "Send Email Batch job_id=%s host=%s recipients=%d",
        task_payload.get("job_id"), smtp_config["host"], len(recipients)
    )

    sent_count = 0
    failed_recipients = []
    for index, row in enumerate(recipients):
        to_email = row.get("email")
        if not to_email:
            failed_recipients.append("(missing email)")
            continue
        if index > 0:
            # Space sends out so we don't trip the SMTP provider's per-second rate limit.
            time.sleep(smtp_send_delay_seconds)
        try:
            subject = render_template(subject_template, row)
            body = render_template(body_template, row)
            send_smtp_email(smtp_config, to_email, subject, body)
            sent_count += 1
            job_audit_log(task_payload, f"Email sent to {to_email}")
        except Exception as ex:
            logger.exception("Failed to send email to=%s", to_email)
            failed_recipients.append(to_email)
            job_audit_log(task_payload, f"Email FAILED to {to_email}: {ex}")

    summary = f"Send Email Batch finished: {sent_count} sent, {len(failed_recipients)} failed"
    job_audit_log(task_payload, summary)
    logger.info(summary)

    if recipients and sent_count == 0:
        raise RuntimeError(f"All {len(failed_recipients)} email(s) failed to send")


def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)
