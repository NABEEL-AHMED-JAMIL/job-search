import io
import json
import os
import re
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

    if 200 <= response.status_code < 300:
        logger.info("%s succeeded", action)
        return payload["data"] if isinstance(payload, dict) else payload
    else:
        logger.error("FAILED: status=%s response=%s", response.status_code, response.text)
        job_audit_log(task_payload, f"{action} failed with status {response.status_code}")
        raise ValueError(f"{action} failed with status {response.status_code}")

def _require(task_payload, values, error_message):
    """
        Fail fast with the same log+audit+raise sequence every required-config check in
        this file uses, instead of repeating it at each call site.
    """
    if not all(values):
        logger.error(error_message)
        job_audit_log(task_payload, error_message)
        raise ValueError(error_message)

def _render_url(template, **params):
    """
        Fill a URL template's {placeholder} tokens -- shared by every panels_url/fields_url/
        submissions_url construction instead of a repeated chain of .replace() calls.
    """
    rendered = template
    for key, value in params.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered

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

def fetch_panels(task_payload, panels_url, token):
    """
        GET the panels for a form. Each panel dict may already come back with its own
        'fields' array inlined -- callers should reuse that instead of calling fields_url
        again for that panel.
    """
    return _call_api(
        task_payload, "GET", panels_url, "Fetch form panels",
        headers={"Authorization": f"Bearer {token}"}
    ) or []

def fetch_panel_fields(task_payload, fields_url, token):
    """
        GET the fields for a single panel.
    """
    return _call_api(
        task_payload, "GET", fields_url, "Fetch panel fields",
        headers={"Authorization": f"Bearer {token}"}
    ) or []

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

def build_form_tree(task_payload, highlighter, organization_uuid, form_uuid, token):
    """
        Build the panels->fields tree for one user's session: fetch the form's panels with
        panels_url, then for each panel either reuse its already-inlined 'fields' (skipping
        the fields_url call and storing nothing further for it) or fetch them with
        fields_url. organization_uuid/token come from that user's login_payload (set by
        authenticate_session) -- both URLs are called with that user's bearer token.
        <highlighter>
            <panels_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels</panels_url>
            <fields_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels/{panel_uuid}/fields</fields_url>
        </highlighter>
    """
    panels_url_tpl = highlighter.get("panels_url")
    fields_url_tpl = highlighter.get("fields_url")
    _require(task_payload, [panels_url_tpl, fields_url_tpl], "Missing highlighter.panels_url/fields_url in task payload.")

    panels_url = _render_url(panels_url_tpl, organization_uuid=organization_uuid, form_uuid=form_uuid)
    panels = fetch_panels(task_payload, panels_url, token)

    tree = []
    for panel in panels:
        panel_uuid = panel.get("uuid")
        # Reuse already-inlined fields if the panels response gave us them -- otherwise
        # fetch them individually. Either way, nothing extra is stored beyond this list.
        if "fields" in panel:
            fields = panel["fields"]
        else:
            fields_url = _render_url(
                fields_url_tpl, organization_uuid=organization_uuid, form_uuid=form_uuid, panel_uuid=panel_uuid
            )
            fields = fetch_panel_fields(task_payload, fields_url, token)
        tree.append({**panel, "fields": fields})

    return tree

def _coerce_field_value(field, text_value):
    """
        Turn an already-validated, non-blank extracted string into the submissions payload
        fragment for this field's type -- {"valueNumber": ...} for NUMBER fields,
        {"valueText": ...} for everything else (every other field type in this form
        definition is free text).
    """
    if field.get("fieldType") == "NUMBER":
        try:
            numeric = float(text_value)
        except (TypeError, ValueError):
            raise ValueError(f"'{text_value}' is not a valid number")
        if numeric.is_integer():
            numeric = int(numeric)
        return {"valueNumber": numeric}
    return {"valueText": text_value}

def validate_field_value(field, raw_value):
    """
        Validate one extracted value against its field definition (required, pattern,
        minLength, maxLength), mirroring the frontend's own field-level validation.
        Raises ValueError with a human-readable reason on the first rule that fails.
        Returns None for a blank, non-required field (nothing to submit), otherwise the
        submissions payload value fragment (e.g. {"valueText": ...}) for this field.
    """
    label = field.get("label") or field.get("fieldKey")
    is_blank = raw_value is None or str(raw_value).strip() == ""

    if is_blank:
        if field.get("required"):
            raise ValueError(f"'{label}' is required but has no extracted value")
        return None

    text_value = str(raw_value).strip()

    pattern = field.get("pattern")
    if pattern and not re.fullmatch(pattern, text_value):
        raise ValueError(f"'{label}' value '{text_value}' does not match required pattern '{pattern}'")

    min_length = field.get("minLength")
    if min_length is not None and len(text_value) < min_length:
        raise ValueError(f"'{label}' value '{text_value}' is shorter than minLength {min_length}")

    max_length = field.get("maxLength")
    if max_length is not None and len(text_value) > max_length:
        raise ValueError(f"'{label}' value '{text_value}' is longer than maxLength {max_length}")

    return _coerce_field_value(field, text_value)

def build_submission_values(form_tree, row):
    """
        Validate every field across every panel in form_tree against `row` (one extracted
        PDF record, keyed by the form field's fieldKey -- e.g. {"ticket_date": "02.02.2018",
        "ticket_number": "113494", ...}) and build the submissions_url payload's "values"
        list. Raises ValueError naming the first field that fails validation -- the caller
        catches this, audit-logs it, and skips the whole row rather than submitting a
        partially-invalid form.
    """
    values = []
    for panel in form_tree:
        for field in panel.get("fields", []):
            value = validate_field_value(field, row.get(field.get("fieldKey")))
            if value is None:
                continue
            values.append({"fieldUuid": field["uuid"], **value})
    return values

def submit_form(task_payload, submissions_url, token, values):
    """
        POST one filled-out, already-validated form submission to submissions_url.
    """
    return _call_api(
        task_payload, "POST", submissions_url, "Form submission",
        headers={"Authorization": f"Bearer {token}"},
        json={"values": values}
    )

def submissions_fill_form(task_payload, highlighter, form_uuid, extract_data, authenticated_sessions):
    """
        Entry point for the submit step: for every authenticated user and every extracted
        PDF record, validate the record's values against that user's form_tree field
        definitions (required/pattern/minLength/maxLength) and POST it to submissions_url.
        A record that fails validation, or that the API rejects, is skipped -- logged via
        job_audit_log so it shows up in the job's audit trail -- without stopping the rest
        of the batch: both later rows for that user and later users still get processed.
        <highlighter>
            <submissions_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/submissions</submissions_url>
        </highlighter>
    """
    submissions_url_tpl = highlighter.get("submissions_url")
    _require(task_payload, [submissions_url_tpl], "Missing highlighter.submissions_url in task payload.")

    submitted = 0
    skipped = 0
    for session in authenticated_sessions:
        username = session.get("username")
        organization_uuid = session["organizationUuid"]
        token = session["token"]
        form_tree = session.get("form_tree") or []
        submissions_url = _render_url(submissions_url_tpl, organization_uuid=organization_uuid, form_uuid=form_uuid)

        for row in extract_data:
            file_name = row.get("file_name", "<unknown file>")

            try:
                values = build_submission_values(form_tree, row)
            except ValueError as e:
                logger.warning(f"Skipping {file_name} for {username}: {e}")
                job_audit_log(task_payload, f"Skipping {file_name} for {username}: validation failed -- {e}")
                skipped += 1
                continue

            try:
                submit_form(task_payload, submissions_url, token, values)
            except Exception as e:
                # _call_api already audit-logged the failure detail -- just track/skip here.
                logger.warning(f"Skipping {file_name} for {username}: submission failed ({e})")
                skipped += 1
                continue

            submitted += 1
            job_audit_log(task_payload, f"Submitted {file_name} for {username}")

    logger.info(f"Submission complete: {submitted} submitted, {skipped} skipped.")
    job_audit_log(task_payload, f"Submission complete: {submitted} submitted, {skipped} skipped.")
    return {"submitted": submitted, "skipped": skipped}

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
            <form_uuid>46d0608b-cf1b-47f2-a9dd-bcd940ca2373</form_uuid>
            <panels_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels</panels_url>
            <fields_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels/{panel_uuid}/fields</fields_url>
            <submissions_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/submissions</submissions_url>
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

    # Build the panels->fields tree for each authenticated session, using that user's own
    # organizationUuid + token from their login_payload.
    for session in authenticated_sessions:
        session["form_tree"] = build_form_tree(
            task_payload, highlighter, session["organizationUuid"], form_uuid, session["token"]
        )
        logger.debug(f"Built form tree for {session['username']}: {len(session['form_tree'])} panel(s)")

    # Validate every extracted record against each user's form_tree and submit it;
    # invalid/rejected records are skipped (and audit-logged) without stopping the batch.
    submissions_fill_form(task_payload, highlighter, form_uuid, extract_data, authenticated_sessions)