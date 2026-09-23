"""
    The pipelines' side of metering: count as the run goes, report once at the end.

    A `Meter` belongs to one run. It wraps the storage client the pipeline already uses, so every
    get, put and delete -- and the bytes each moved -- is counted without the pipeline knowing;
    anything else a pipeline wants counted (tokens it spent itself, minutes it ran) is one
    `event()` call. On close it sends one batch to the meter service with the run's own callback
    token, which is how the service knows whose usage it is.

    Reporting is never a reason for a job to fail, and no usage is lost without a trace: a meter
    that is down gets three tries, then the batch is spooled to a local file and sent ahead of the
    next run's batch, oldest spool first. A run's events go in batches of at most MAX_BATCH, the
    most the service takes. What the meter refuses for good -- events it rejects one by one, a
    spool file it refuses whole, a spool file that is not a batch -- is parked under dead/ with the
    reason, for a person, and never retried. Every event carries
    `dedupeKey = "{jobQueueId}#{meter}#{seq}"`, so a spool replayed twice, or a Kafka message
    replayed, counts once.
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

import requests

from etl.util.logging_config import get_logger

logger = get_logger(__name__)

METER_URL = os.getenv("METER_URL", "http://host.docker.internal:8200").rstrip("/")
SPOOL_DIR = os.getenv("METER_SPOOL_DIR", "/tmp/etl-meter-spool")
TIMEOUT = float(os.getenv("METER_TIMEOUT_SECONDS", "5"))
# The most events the service takes in one request (etl.meter.app MAX_BATCH); more is a 422.
MAX_BATCH = 500
# Replayed per run, oldest first.
REPLAY_PER_RUN = 20

SENT, REFUSED, FAILED = "sent", "refused", "failed"


class Meter:
    """One run's usage. Use as a context manager; `close()` reports."""

    def __init__(self, job_id, job_queue_id, token, url=None, session=None, spool_dir=None, clock=None):
        self.job_id = job_id
        self.job_queue_id = job_queue_id
        self.token = token
        self.url = (url or METER_URL).rstrip("/")
        self.session = session or requests.Session()
        self.spool_dir = spool_dir or SPOOL_DIR
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.started = time.monotonic()
        self._lock = threading.Lock()
        self._seq = {}
        self._pending = []
        self._closed = False

    # -- recording -----------------------------------------------------------
    def event(self, meter, quantity, unit=None, subject=None, note=None):
        """Records one event. `subject` is ("bucket", "name") / ("prompt", uuid) / ("object", key)."""
        if not quantity:
            return
        with self._lock:
            seq = self._seq.get(meter, 0) + 1
            self._seq[meter] = seq
            self._pending.append({
                "meter": meter, "quantity": float(quantity), "unit": unit,
                "occurredAt": self.clock().isoformat(), "source": "pipeline",
                "subjectType": subject[0] if subject else None, "subjectId": subject[1] if subject else None,
                "dedupeKey": f"{self.job_queue_id}#{meter}#{seq}", "note": note,
            })

    def elapsed_minutes(self):
        # Six places, not three: a run that finished inside a second is still a run that ran,
        # and rounding it to 0.000 would report no minutes at all.
        return round(max(time.monotonic() - self.started, 1e-3) / 60.0, 6)

    def storage(self, minio_client):
        """The storage client, counted. Same methods, same answers; the meter sees each call."""
        return MeteredStorage(minio_client, self)

    # -- reporting -----------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.event("pipeline.worker_minutes", self.elapsed_minutes(), unit="minute")
        with self._lock:
            batch = list(self._pending)
            self._pending = []
        try:
            self._send_spooled()
        except Exception as ex:      # noqa: BLE001 -- an old run's file must never cost this run its report
            logger.error("meter: replaying spooled usage failed: %s", ex)
        for start in range(0, len(batch), MAX_BATCH):
            chunk = batch[start:start + MAX_BATCH]
            if self._send(chunk, self.token, self.job_id, self.job_queue_id) == FAILED:
                self._spool(chunk)

    def _headers(self, token, job_id, job_queue_id):
        return {"X-Worker-Token": token or "", "X-Job-Id": str(job_id), "X-Job-Queue-Id": str(job_queue_id)}

    def _send(self, batch, token, job_id, job_queue_id, tries=3):
        """SENT, REFUSED (the meter will not take this batch whatever is retried) or FAILED (try later)."""
        for attempt in range(1, tries + 1):
            try:
                response = self.session.post(f"{self.url}/v1/events", json={"events": batch},
                                             headers=self._headers(token, job_id, job_queue_id), timeout=TIMEOUT)
                if response.status_code == 200:
                    body = response.json()
                    rejected = body.get("rejected") or []
                    logger.info("meter: run %s reported %d event(s), %d duplicate(s), %d rejected",
                                job_queue_id, body.get("accepted", 0), body.get("duplicates", 0), len(rejected))
                    if rejected:
                        self._park_rejected(batch, rejected, job_id, job_queue_id)
                    return SENT
                if response.status_code == 401:
                    # The meter refused the run itself; retrying will not change its mind, and
                    # the batch must not be spooled under a token that is not this run's.
                    logger.warning("meter: run %s refused (%s): %s", job_queue_id, response.status_code, response.text[:200])
                    return SENT
                if response.status_code in (400, 422):
                    logger.error("meter: run %s's batch of %d refused (%s): %s", job_queue_id, len(batch), response.status_code, response.text[:200])
                    self._park({"jobId": job_id, "jobQueueId": job_queue_id, "status": response.status_code,
                                "reason": response.text[:2000], "events": batch}, f"{job_queue_id}-{self._now_ms()}-refused.json")
                    return REFUSED
                logger.warning("meter: attempt %d for run %s answered %s", attempt, job_queue_id, response.status_code)
            except requests.RequestException as ex:
                logger.warning("meter: attempt %d for run %s failed: %s", attempt, job_queue_id, ex)
            time.sleep(0.5 * attempt)
        return FAILED

    def _park_rejected(self, batch, rejected, job_id, job_queue_id):
        """Events the meter rejected one by one: kept with the reason, never retried (the same event
        would be rejected the same way)."""
        parked = []
        for r in rejected:
            index = r.get("index")
            event = batch[index] if isinstance(index, int) and 0 <= index < len(batch) else None
            parked.append({"index": index, "reason": r.get("reason"), "event": event})
            logger.error("meter: run %s's event %s rejected: %s (%s)", job_queue_id, index,
                         r.get("reason"), (event or {}).get("meter"))
        self._park({"jobId": job_id, "jobQueueId": job_queue_id, "rejected": parked}, f"{job_queue_id}-{self._now_ms()}-rejected.json")

    def _park(self, body, name):
        try:
            dead = os.path.join(self.spool_dir, "dead")
            os.makedirs(dead, exist_ok=True)
            with open(os.path.join(dead, name), "w", encoding="utf-8") as handle:
                json.dump(body, handle)
        except OSError as ex:
            logger.error("meter: could not park %s: %s -- %s", name, ex, json.dumps(body)[:2000])

    def _park_file(self, path):
        try:
            dead = os.path.join(self.spool_dir, "dead")
            os.makedirs(dead, exist_ok=True)
            os.replace(path, os.path.join(dead, os.path.basename(path)))
        except OSError as ex:
            logger.error("meter: could not park %s: %s", path, ex)

    @staticmethod
    def _now_ms():
        return int(time.time() * 1000)

    def _spool(self, batch):
        try:
            os.makedirs(self.spool_dir, exist_ok=True)
            # Nanoseconds, so two runs spooled in the same millisecond still replay in the order they
            # were spooled (a legacy millisecond name is smaller, and older, and sorts first).
            path = os.path.join(self.spool_dir, f"{self.job_queue_id}-{time.time_ns()}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"jobId": self.job_id, "jobQueueId": self.job_queue_id, "token": self.token, "events": batch}, handle)
            logger.warning("meter: run %s's %d event(s) spooled to %s; sent with the next run", self.job_queue_id, len(batch), path)
        except OSError as ex:
            logger.error("meter: could not spool %d event(s) for run %s: %s -- usage lost", len(batch), self.job_queue_id, ex)

    @staticmethod
    def _spooled_at(name, path):
        """When a file was spooled: the epoch time its name carries ({jobQueueId}-{ns or ms}.json), else its mtime."""
        stem = name[:-5] if name.endswith(".json") else name
        tail = stem.rsplit("-", 1)[-1]
        if tail.isdigit() and len(tail) >= 10:
            return int(tail)
        try:
            return int(os.path.getmtime(path) * 1000)
        except OSError:
            return 0

    def _send_spooled(self):
        """Earlier runs' batches that never got through, oldest first, under their own tokens; the
        console decides if they are still good -- a run long over is refused, which is logged, and
        the file dropped. A file that is not a batch, or that the meter refuses whole, is parked."""
        try:
            names = [n for n in os.listdir(self.spool_dir) if not os.path.isdir(os.path.join(self.spool_dir, n))] \
                if os.path.isdir(self.spool_dir) else []
        except OSError:
            return
        names.sort(key=lambda n: (self._spooled_at(n, os.path.join(self.spool_dir, n)), n))
        for name in names[:REPLAY_PER_RUN]:
            path = os.path.join(self.spool_dir, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    saved = json.load(handle)
                if not isinstance(saved, dict) or not isinstance(saved.get("events"), list):
                    raise ValueError("not a spooled batch")
            except (OSError, ValueError) as ex:
                logger.warning("meter: spool file %s could not be read: %s -- parked", path, ex)
                self._park_file(path)
                continue
            outcome = self._send(saved["events"], saved.get("token"), saved.get("jobId"), saved.get("jobQueueId"), tries=1)
            if outcome in (SENT, REFUSED):
                try:
                    os.remove(path)
                except OSError as ex:
                    logger.warning("meter: could not remove replayed spool file %s: %s", path, ex)


class MeteredStorage:
    """MinioClient's methods, counted. Kept to the ones the pipelines use."""

    def __init__(self, client, meter):
        self.client = client
        self.meter = meter

    def _size(self, bucket, key):
        try:
            return int(self.client.client.stat_object(bucket, key).size)
        except Exception:      # noqa: BLE001 -- unknown size is a zero-byte count, not a failure
            return 0

    def get_object_bytes(self, bucket, key):
        data = self.client.get_object_bytes(bucket, key)
        self.meter.event("storage.ops.read", 1, unit="op", subject=("bucket", bucket))
        if data:
            self.meter.event("storage.bytes.read", len(data), unit="byte", subject=("bucket", bucket))
        return data

    def upload_bytes(self, bucket, key, data, content_type="application/octet-stream"):
        ok = self.client.upload_bytes(bucket, key, data, content_type=content_type)
        if ok:
            self.meter.event("storage.ops.write", 1, unit="op", subject=("bucket", bucket))
            self.meter.event("storage.bytes.written", len(data), unit="byte", subject=("bucket", bucket))
        return ok

    def upload_file(self, bucket, key, path, content_type="application/octet-stream"):
        ok = self.client.upload_file(bucket, key, path, content_type=content_type)
        if ok:
            self.meter.event("storage.ops.write", 1, unit="op", subject=("bucket", bucket))
            try:
                self.meter.event("storage.bytes.written", os.path.getsize(path), unit="byte", subject=("bucket", bucket))
            except OSError:
                pass
        return ok

    def list_objects(self, bucket, prefix=None, recursive=True):
        names = self.client.list_objects(bucket, prefix=prefix, recursive=recursive)
        self.meter.event("storage.ops.read", 1, unit="op", subject=("bucket", bucket), note="list")
        return names

    def object_exists(self, bucket, key):
        return self.client.object_exists(bucket, key)

    def delete_object(self, bucket, key):
        # The size before it goes: what a delete removed is the churn the bill shows.
        size = self._size(bucket, key)
        ok = self.client.delete_object(bucket, key)
        if ok:
            self.meter.event("storage.ops.delete", 1, unit="op", subject=("bucket", bucket))
            if size:
                self.meter.event("storage.bytes.deleted", size, unit="byte", subject=("object", f"{bucket}/{key}"))
        return ok

    def __getattr__(self, name):
        return getattr(self.client, name)
