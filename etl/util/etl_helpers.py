"""
    Shared plumbing for the object-storage ETL pipelines.
    Author: Nabeel Ahmed Jamil

    Every pipeline in this family does the same four things around its actual work: resolve which
    bucket it is reading and writing, pull one or more objects out of MinIO, push a result back,
    and narrate what it did into the job's audit log so the run is readable in the console
    afterwards. Written once here so a pipeline file contains its transformation and almost
    nothing else -- the fifteen of them were otherwise going to carry the same forty lines each.

    WHY THE CLIENT IS BUILT LAZILY
    The older task modules construct `MinioClient()` at module scope, which means importing any
    of them requires MINIO_ACCESS_KEY/MINIO_SECRET_KEY to already be set -- importing the module
    to inspect it, or to read its parser, fails on a machine that has no credentials. Here the
    client is created on first use instead, so this module is safe to import anywhere.
"""
import csv
import gzip
import io
import json
import os

from dotenv import load_dotenv

from etl.util.job_state_client import JobStateClient
from etl.util.logging_config import get_logger
from etl.util.minio_client import MinioClient

load_dotenv()

logger = get_logger(__name__)

DEFAULT_BUCKET = os.getenv("MINIO_BUCKET_NAME", "etl-bucket")
ETL_EVENT_URL = os.getenv("ETL_EVENT_URL")

_minio = None
_job_state = None


def minio():
    """The shared MinIO client, built on first use. See the module docstring for why."""
    global _minio
    if _minio is None:
        _minio = MinioClient()
    return _minio


def job_state():
    global _job_state
    if _job_state is None:
        _job_state = JobStateClient(ETL_EVENT_URL)
    return _job_state


class Pipeline:
    """One run of one pipeline: where it reads, where it writes, and how it reports.

    Constructed from the dict a `parse_*` function returned, which the listener has already
    stamped with `job_id` and `job_queue_id` before calling the task
    (tpd_scrapping_listener.execute_task).
    """

    def __init__(self, task_payload):
        self.payload = task_payload
        self.job_id = task_payload.get("job_id")
        self.job_queue_id = task_payload.get("job_queue_id")
        # <bucket> is optional on every pipeline in this family, and absent means "the platform
        # bucket" -- the same convention parse_926 already established. Where it is set, it is
        # what routes a tenant's data into that tenant's own bucket.
        self.bucket = task_payload.get("bucket") or DEFAULT_BUCKET
        # The run's meter, when the listener opened one. Storage goes through it so every
        # read, write and delete is counted; a pipeline run outside a listener (a test, a
        # script) has none and talks to storage directly.
        self.meter = task_payload.get("meter")

    # -- storage, counted ------------------------------------------------------
    def _store(self):
        return self.meter.storage(minio()) if self.meter else minio()

    # -- reporting -----------------------------------------------------------
    def log(self, message):
        """Writes one line to the job's audit log AND the container log.

        Both, deliberately: the audit log is what an operator reads in the console, and the
        container log is what survives when the callback cannot reach the backend.
        """
        logger.info(message)
        if self.job_id and self.job_queue_id:
            job_state().job_audit_log(self.job_id, self.job_queue_id, message)

    def require(self, *names):
        """Fails fast, by name, when the task payload is missing something.

        A pipeline that runs half way and then dies on a KeyError deep in pandas leaves an
        operator with a stack trace instead of an answer; this turns that into one sentence.
        """
        missing = [n for n in names if not self.payload.get(n)]
        if missing:
            raise ValueError(
                f"{self.payload.get('id', 'pipeline')} is missing required setting(s): "
                f"{', '.join(missing)}"
            )
        return [self.payload.get(n) for n in names]

    # -- object storage ------------------------------------------------------
    def read_bytes(self, key):
        return self._store().get_object_bytes(self.bucket, key)

    def write_bytes(self, key, data, content_type="application/octet-stream"):
        self._store().upload_bytes(self.bucket, key, data, content_type=content_type)
        return key

    def delete(self, key):
        """Removes one object -- and counts it, size and all, because deleted bytes are billed."""
        return self._store().delete_object(self.bucket, key)

    def read_text(self, key, encoding="utf-8"):
        return self.read_bytes(key).decode(encoding)

    def write_text(self, key, text, content_type="text/plain", encoding="utf-8"):
        return self.write_bytes(key, text.encode(encoding), content_type=content_type)

    def write_json(self, key, obj):
        return self.write_text(key, json.dumps(obj, indent=2, default=str),
                               content_type="application/json")

    def write_gzip(self, key, data):
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
            handle.write(data)
        return self.write_bytes(key, buffer.getvalue(), content_type="application/gzip")

    def list_keys(self, prefix, suffix=None):
        """Object keys under a prefix, optionally filtered by extension, folder markers dropped.

        MinIO returns the zero-byte "directory" placeholders that some clients create; a pipeline
        that treats one as a CSV fails confusingly, so they are filtered out here once.
        """
        keys = []
        for name in self._store().list_objects(self.bucket, prefix=prefix, recursive=True):
            key = name if isinstance(name, str) else getattr(name, "object_name", str(name))
            if key.endswith("/"):
                continue
            if suffix and not key.lower().endswith(suffix.lower()):
                continue
            keys.append(key)
        return sorted(keys)

    # -- tabular data --------------------------------------------------------
    # Rows are carried as a list of dicts rather than a DataFrame. These pipelines are IO-bound
    # and the files are configuration-sized, so the dependency and the memory copy that pandas
    # brings buy nothing here -- and csv.DictReader preserves the exact column order the source
    # had, which several of these pipelines are specifically supposed to protect.
    def read_csv(self, key):
        text = self.read_text(key)
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return rows, (reader.fieldnames or [])

    def write_csv(self, key, rows, fieldnames=None):
        if fieldnames is None:
            fieldnames = list(rows[0].keys()) if rows else []
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return self.write_text(key, buffer.getvalue(), content_type="text/csv")

    # -- naming --------------------------------------------------------------
    def output_key(self, output_folder, name):
        """Joins a folder and a file name without doubling or dropping the separator."""
        folder = (output_folder or "").strip().strip("/")
        return f"{folder}/{name}" if folder else name

    @staticmethod
    def basename(key):
        return key.rsplit("/", 1)[-1]

    @staticmethod
    def stem(key):
        base = Pipeline.basename(key)
        return base.rsplit(".", 1)[0] if "." in base else base


def coerce_number(value):
    """Best-effort numeric read of a CSV cell, or None.

    CSV has no types, so every comparison and every sum in this family has to decide what a cell
    means. Returning None rather than raising lets a caller choose between skipping the row and
    treating it as a failure, which different pipelines here genuinely want to do differently.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
