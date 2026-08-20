"""
    Zanium Firebase Data Export (F768920)
    @author: Nabeel Ahmed Jamil

    Fetches the pipeline's Firebase service-account credential from the bucket
    (task_payload["credential"]), reads the configured Firestore collections
    (target_table_config/tables), exports each one to CSV under extracted_data/
    in the same bucket, and -- for the "users" table specifically -- imports
    those rows into the v4_backend database (app_user / app_user_preference /
    app_user_tenant / app_user_role), filling in v4_backend's own defaults for
    anything the Firestore data doesn't have a usable value for.
"""
import ast
import csv
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone

import bcrypt
import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

from etl.util.job_state_client import JobStateClient
from etl.util.minio_client import MinioClient
from etl.util.v4_backend_client import V4BackendClient
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
etl_event_url = os.getenv("ETL_EVENT_URL")
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
minio_client = MinioClient()
v4_backend_client = V4BackendClient()

# Logical table name (as configured in the pipeline's target_table_config) -> the
# Firestore collection it reads from.
FIRESTORE_COLLECTIONS = {
    "users": "users"
}

# Fields never written out even if present on a document (defense in depth --
# these shouldn't be in Firestore user docs, but never let them leak into a CSV).
SENSITIVE_FIELDS = {"password", "passwordHash", "password_hash"}

# Firestore "roles" values (this app's clinical-role shorthand) -> v4_backend
# app_role.code. ota/slp don't have an exact v4_backend counterpart -- OT/ST are
# the closest clinical match (Occupational/Speech Therapist covers the assistant
# and pathologist variants respectively until v4_backend grows dedicated roles).
ROLE_MAP = {
    "admin": "AGENCY_ADMIN",
    "clinical_supervisor": "CLINICAL_SUPERVISOR",
    "rn": "RN",
    "lpn": "LPN",
    "pt": "PT",
    "ota": "OT",
    "slp": "ST",
    "office_staff": "OFFICE_STAFF",
    "qa_company": "QA_COMPANY"
}

DEFAULT_PREFERENCE = {"language": "en", "theme": "light", "email_notifications": True, "push_notifications": True}


def get_firebase_app(service_account_info):
    """
        firebase_admin apps are named singletons -- initialize_app() raises if the
        same name is already registered, so reuse the existing one keyed by
        project_id instead of re-initializing on every job run.
    """
    app_name = service_account_info.get("project_id", "zanium-default")
    try:
        return firebase_admin.get_app(app_name)
    except ValueError:
        cred = credentials.Certificate(service_account_info)
        return firebase_admin.initialize_app(cred, name=app_name)


def fetch_service_account(bucket, credential_key):
    """
        Download and parse the Firebase service-account JSON from the bucket.
        This app's credential files bundle the service account under a
        "firebase" key alongside unrelated config (e.g. SMTP) -- unwrap that.
    """
    raw = minio_client.get_object_bytes(bucket, credential_key)
    if raw is None:
        raise ValueError(f"Credential file not found: {bucket}/{credential_key}")
    config = json.loads(raw)
    service_account_info = config.get("firebase") or config
    if "project_id" not in service_account_info or "private_key" not in service_account_info:
        raise ValueError(f"Credential file {bucket}/{credential_key} is missing a valid Firebase service account")
    return service_account_info


def collection_to_csv_bytes(db, collection_name):
    rows = []
    for doc in db.collection(collection_name).stream():
        row = doc.to_dict() or {}
        row["id"] = doc.id
        for field in SENSITIVE_FIELDS:
            row.pop(field, None)
        rows.append(row)

    if not rows:
        return b"", 0

    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    return buffer.getvalue().encode("utf-8"), len(rows)


def _parse_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("true", "1", "yes")


def _parse_timestamp(value):
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    text = str(value)
    for candidate in (text, text.split(".")[0] if "." in text else text):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_preferences(value):
    """
        preferences is stored as a Python-dict-repr string (Firestore map field
        written out via str()), e.g. "{'language': 'en', 'notifications':
        {'push': False, 'email': True}, 'theme': 'light'}". Fall back to
        DEFAULT_PREFERENCE wherever a key is missing or the whole thing fails
        to parse.
    """
    parsed = {}
    if value:
        try:
            parsed = ast.literal_eval(str(value)) or {}
        except (ValueError, SyntaxError):
            parsed = {}
    notifications = parsed.get("notifications") or {}
    return {
        "language": parsed.get("language") or DEFAULT_PREFERENCE["language"],
        "theme": parsed.get("theme") or DEFAULT_PREFERENCE["theme"],
        "email_notifications": _parse_bool(notifications.get("email"), DEFAULT_PREFERENCE["email_notifications"]),
        "push_notifications": _parse_bool(notifications.get("push"), DEFAULT_PREFERENCE["push_notifications"])
    }


def _parse_role_codes(value):
    """ roles is a Python-list-repr string, e.g. "['admin']". """
    if not value:
        return []
    try:
        raw_roles = ast.literal_eval(str(value)) or []
    except (ValueError, SyntaxError):
        raw_roles = [str(value)]
    return [ROLE_MAP[r] for r in raw_roles if isinstance(r, str) and r.lower() in ROLE_MAP]


def _default_password_hash():
    """
        The Firestore export never carries a usable plaintext/compatible password
        (axxess_password_enc is ciphertext in a different app's scheme) -- every
        imported user gets a random bcrypt-hashed placeholder and must reset their
        password through v4_backend's normal flow.
    """
    random_password = uuid.uuid4().hex + uuid.uuid4().hex
    return bcrypt.hashpw(random_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_users_in_v4_backend(task_payload, csv_bytes):
    """
        Reads the just-exported users CSV and creates each row in v4_backend
        (app_user, app_user_preference, app_user_tenant, app_user_role), using
        v4_backend's own schema/defaults for anything Firestore's data doesn't
        map cleanly onto. Safe to re-run -- rows whose email already exists in
        app_user are skipped, not duplicated.
    """
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    if not rows:
        job_audit_log(task_payload, "v4_backend import: no user rows to import.")
        return

    role_ids = v4_backend_client.role_id_by_code()
    tenant_id = v4_backend_client.default_tenant_id()
    if not tenant_id:
        job_audit_log(task_payload, "v4_backend import FAILED: no app_tenant row exists to assign users to.")
        raise RuntimeError("v4_backend has no app_tenant to default new users into")

    created = 0
    skipped = 0
    failed = 0
    pending_audit_links = []  # (new_user_id, created_by_email, updated_by_email)

    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if not email:
            skipped += 1
            job_audit_log(task_payload, f"v4_backend import: skipped a row with no email (firebase_uid={row.get('firebase_uid')}).")
            continue
        try:
            if v4_backend_client.find_user_id_by_email(email):
                skipped += 1
                continue

            user_id = str(uuid.uuid4())
            name = (row.get("name") or "").strip() or email.split("@")[0]
            active = _parse_bool(row.get("active"), True)
            profile_image = (row.get("profile_picture") or "").strip() or None
            created_at = _parse_timestamp(row.get("created_at"))
            updated_at = _parse_timestamp(row.get("updated_at"))
            password_hash = _default_password_hash()

            v4_backend_client.execute(
                """
                INSERT INTO app_user (id, name, email, password, active, profile_image, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, name, email, password_hash, active, profile_image, created_at, updated_at)
            )

            preference = _parse_preferences(row.get("preferences"))
            v4_backend_client.execute(
                """
                INSERT INTO app_user_preference
                    (id, user_id, language, theme, email_notifications, push_notifications, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, preference["language"], preference["theme"],
                 preference["email_notifications"], preference["push_notifications"], created_at, updated_at)
            )

            v4_backend_client.execute(
                """
                INSERT INTO app_user_tenant (id, user_id, tenant_id, status, is_default_tenant, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, tenant_id, "ACTIVE", True, created_at, updated_at)
            )

            matched_role_codes = _parse_role_codes(row.get("roles"))
            for role_code in matched_role_codes:
                role_id = role_ids.get(role_code)
                if role_id:
                    v4_backend_client.execute(
                        "INSERT INTO app_user_role (user_id, role_id) VALUES (%s, %s)",
                        (user_id, role_id)
                    )
            if row.get("roles") and not matched_role_codes:
                job_audit_log(task_payload, f"v4_backend import: '{email}' has unmapped role(s) {row.get('roles')} -- user created with no role assigned.")

            pending_audit_links.append((user_id, row.get("created_by"), row.get("updated_by")))
            created += 1
        except Exception as ex:
            failed += 1
            logger.exception("Failed to import v4_backend user email=%s", email)
            job_audit_log(task_payload, f"v4_backend import FAILED for '{email}': {ex}")

    # Second pass: created_by/updated_by in the source data are emails, not the
    # uuids app_user actually stores -- resolve them now that every user in this
    # batch has a v4_backend id (including users created_by one another).
    for user_id, created_by_email, updated_by_email in pending_audit_links:
        try:
            created_by_id = v4_backend_client.find_user_id_by_email((created_by_email or "").strip().lower()) if created_by_email else None
            updated_by_id = v4_backend_client.find_user_id_by_email((updated_by_email or "").strip().lower()) if updated_by_email else None
            if created_by_id or updated_by_id:
                v4_backend_client.execute(
                    "UPDATE app_user SET created_by = COALESCE(%s, created_by), updated_by = COALESCE(%s, updated_by) WHERE id = %s",
                    (created_by_id, updated_by_id, user_id)
                )
        except Exception:
            logger.exception("Failed to resolve created_by/updated_by for user_id=%s", user_id)

    summary = f"v4_backend import finished: {created} created, {skipped} skipped (already existed), {failed} failed"
    job_audit_log(task_payload, summary)
    logger.info(summary)

    if rows and not created and not skipped:
        raise RuntimeError(f"v4_backend import: all {failed} row(s) failed")


def zanium_firebase_data_export(task_payload):
    """
        Entry point routed from execute_task for pipeline F768920.
        task_payload: dict returned by xml_parser.parse_920, plus job_id/job_queue_id.
    """
    job_id = task_payload.get("job_id")
    bucket = task_payload.get("bucket")
    credential_key = task_payload.get("credential")
    extracted_data = task_payload.get("extracted_data") or ""
    tables = task_payload.get("target_table_config") or []

    logger.info(
        "Zanium Firebase Data Export job_id=%s bucket=%s credential=%s tables=%s",
        job_id, bucket, credential_key, tables
    )

    if not tables:
        job_audit_log(task_payload, "No tables configured in target_table_config -- nothing to export.")
        return

    try:
        service_account_info = fetch_service_account(bucket, credential_key)
        app = get_firebase_app(service_account_info)
        db = firestore.client(app)
    except Exception as ex:
        logger.exception("Failed to initialize Firebase from credential=%s", credential_key)
        job_audit_log(task_payload, f"Could not load Firebase credential: {ex}")
        raise

    exported = []
    failed = []
    for table in tables:
        collection_name = FIRESTORE_COLLECTIONS.get(table)
        if not collection_name:
            failed.append(table)
            job_audit_log(task_payload, f"Table '{table}' is not mapped to a Firestore collection yet -- skipped.")
            continue
        try:
            csv_bytes, row_count = collection_to_csv_bytes(db, collection_name)
            if not row_count:
                job_audit_log(task_payload, f"Collection '{collection_name}' is empty -- nothing to export.")
                exported.append(table)
                continue
            object_name = f"{extracted_data}{table}_job_{job_id}.csv"
            uploaded = minio_client.upload_bytes(bucket, object_name, csv_bytes, content_type="text/csv")
            if not uploaded:
                raise RuntimeError(f"upload_bytes returned False for {object_name}")
            exported.append(table)
            job_audit_log(task_payload, f"Exported {row_count} row(s) from Firestore '{collection_name}' to {bucket}/{object_name}")

            if table == "users":
                try:
                    create_users_in_v4_backend(task_payload, csv_bytes)
                except Exception as v4_ex:
                    logger.exception("v4_backend import failed after a successful CSV export")
                    job_audit_log(task_payload, f"v4_backend import step FAILED (CSV export itself succeeded): {v4_ex}")
        except Exception as ex:
            failed.append(table)
            logger.exception("Failed to export Firestore collection=%s", collection_name)
            job_audit_log(task_payload, f"Export FAILED for table '{table}': {ex}")

    summary = f"Zanium Firebase Data Export finished: {len(exported)} exported, {len(failed)} failed"
    job_audit_log(task_payload, summary)
    logger.info(summary)

    if tables and not exported:
        raise RuntimeError(f"All {len(failed)} table export(s) failed")


def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)
