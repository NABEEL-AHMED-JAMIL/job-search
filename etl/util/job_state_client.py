"""
    Job State Client
    @author: Nabeel Ahmed Jamil
"""
import os

import requests

# requests blocks for ever without this: a server that accepts the connection and never
# replies holds the calling worker thread indefinitely. With a fixed pool that is how a
# whole consumer stops -- every thread ends up parked on a socket that will never answer.
# Connect is quick or hopeless; read is given longer because the backend queues under load.
CALLBACK_TIMEOUT = (5, 30)

# How many lines to hold before sending, and how long a partial batch may wait.
#
# A run producing fifty log lines was making fifty round trips, each repeating the same job
# lookup on the server. Measured across a 500-job run, that path accounted for roughly 97% of
# every run's elapsed time once thirty workers were competing for it -- the calls were not slow
# individually (8ms direct) but they queued.
#
# The age cap matters as much as the size: a job that logs slowly should still have its lines
# appear while it runs, not all at once when it finishes.
LOG_BATCH_SIZE = 25
LOG_BATCH_MAX_AGE_SECONDS = 5

import threading
import time
from collections import defaultdict

from etl.util.logging_config import get_logger

# Configure colored logging
logger = get_logger(__name__)


class RunRefused(Exception):
    """The console refused this run's callback (401): the run is over, or the token is not
    the run's own. Whatever this worker is doing for the run is wasted -- a replayed Kafka
    message for a run that already finished, most often -- and nothing it reports will land."""


class JobStateClient:

    def __init__(self, base_url):
        self.base_url = base_url
        # Buffered log lines per run. Threads share one client, so the buffer is guarded.
        self._log_buffers = defaultdict(list)
        self._log_first_seen = {}
        self._log_lock = threading.Lock()
        # The per-run callback token each dispatch carries, keyed by (job_id, job_queue_id).
        self._run_tokens = {}
        self._token_lock = threading.Lock()

    def remember_run_token(self, job_id, job_queue_id, token):
        """The token the dispatch carried (payload.callbackToken): the run's own proof, echoed
        on every callback for that run and forgotten once it is over."""
        if not token:
            return
        with self._token_lock:
            self._run_tokens[(job_id, job_queue_id)] = token

    def forget_run_token(self, job_id, job_queue_id):
        with self._token_lock:
            self._run_tokens.pop((job_id, job_queue_id), None)

    def run_token(self, job_id, job_queue_id):
        with self._token_lock:
            return self._run_tokens.get((job_id, job_queue_id))

    def _auth_headers(self, job_id=None, job_queue_id=None):
        """What proves a callback (see NotifyResetApi and RunCallbackTokens on the server).

        Since 2026-09-18 every dispatch carries a token good for that run alone, and the server
        checks it against a hash on the queue row: a callback that echoes it can only touch the
        run it was handed. The shared WORKER_CALLBACK_TOKEN is honoured only for a run dispatched
        before tokens existed, so it is the fallback here, not the rule. Absent both, the header
        is simply omitted."""
        token = self.run_token(job_id, job_queue_id) if job_id is not None else None
        if not token:
            token = os.getenv("WORKER_CALLBACK_TOKEN", "").strip()
        return {"X-Worker-Token": token} if token else {}

    def change_job_state(self, job_id, job_queue_id, job_status, message):
        """
            job_status: Running | Failed | Completed
            message: jobStatusMessage
        """
        url = f"{self.base_url}/changeState/jobId/{job_id}/jobQueueId/{job_queue_id}/jobStatus/{job_status}"
        payload = {
            "jobStatusMessage": message
        }
        try:
            response = requests.post(url, json=payload, headers=self._auth_headers(job_id, job_queue_id),
                                     timeout=CALLBACK_TIMEOUT)
            if response.status_code == 200:
                try:
                    logger.info("SUCCESS: %s", response.json())
                    return response.json()
                except Exception:
                    logger.info("SUCCESS: %s", response.text)
                    return response.text
            elif response.status_code == 401:
                # Not retried and not swallowed: the caller decides whether to keep working.
                logger.warning("REFUSED: the console will not take callbacks for job %s run %s (%s)",
                               job_id, job_queue_id, response.text[:120])
                raise RunRefused(response.text)
            else:
                logger.error("FAILED: status=%s response=%s", response.status_code, response.text)
                try:
                    return response.json()
                except Exception:
                    return response.text
        except RunRefused:
            raise
        except Exception as e:
            logger.error(f"ERROR calling API: {e}")
            return None

    def job_audit_log(self, job_id, job_queue_id, message):
        """
            Buffer a log line, sending once the batch is full or has waited long enough.

            job_id: 1133 etc
            job_queue_id: 13 etc
            message: File added to s3 and etc....

            Returns nothing useful now: the send happens later, so there is no per-line
            response to hand back. Nothing was reading it.
        """
        key = (job_id, job_queue_id)
        due = []
        with self._log_lock:
            self._log_buffers[key].append(message)
            self._log_first_seen.setdefault(key, time.monotonic())
            waited = time.monotonic() - self._log_first_seen[key]
            if len(self._log_buffers[key]) >= LOG_BATCH_SIZE or waited >= LOG_BATCH_MAX_AGE_SECONDS:
                due = self._take(key)
        if due:
            self._send_log_batch(job_id, job_queue_id, due)

    def flush_logs(self, job_id, job_queue_id):
        """
            Send whatever is buffered for this run.

            Called before a run reports its final status, so the lines land before the job is
            marked done -- a reader opening the logs of a completed job must not find them
            still in a buffer somewhere.
        """
        key = (job_id, job_queue_id)
        with self._log_lock:
            due = self._take(key)
        if due:
            self._send_log_batch(job_id, job_queue_id, due)

    def _take(self, key):
        """Remove and return this run's buffered lines. Caller must hold the lock."""
        lines = self._log_buffers.pop(key, [])
        self._log_first_seen.pop(key, None)
        return lines

    def _send_log_batch(self, job_id, job_queue_id, messages):
        """
            One request for many lines.

            A failure is logged and the lines are dropped rather than retried. They are audit
            lines: losing a few is survivable, and retrying inside a worker thread is how the
            callback path became the bottleneck in the first place.
        """
        url = f"{self.base_url}/addLogsBatch/jobId/{job_id}/jobQueueId/{job_queue_id}"
        try:
            response = requests.post(url, json={"messages": messages},
                                     headers=self._auth_headers(job_id, job_queue_id), timeout=CALLBACK_TIMEOUT)
            if response.status_code == 200:
                logger.info("SUCCESS: %s line(s) for job %s queue %s",
                            len(messages), job_id, job_queue_id)
            else:
                logger.error("FAILED: %s line(s) status=%s response=%s",
                             len(messages), response.status_code, response.text)
        except Exception as ex:
            logger.error("FAILED: %s line(s) for job %s queue %s: %s",
                         len(messages), job_id, job_queue_id, str(ex))
