"""
    Job State Client
    @author: Nabeel Ahmed Jamil
"""
import os

import requests
from etl.util.logging_config import get_logger

# Configure colored logging
logger = get_logger(__name__)


class JobStateClient:

    def __init__(self, base_url):
        self.base_url = base_url

    @staticmethod
    def _auth_headers():
        """Shared secret the backend requires on /changeState and /addLogs (see NotifyResetApi).
        These callbacks sit outside the JWT chain because workers have no user session, so this
        header is what distinguishes a real worker from anyone else who can reach the port.
        Absent, the header is simply omitted -- a backend with no token configured still accepts
        the call, which keeps an un-migrated deployment working."""
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
            response = requests.post(url, json=payload, headers=self._auth_headers())
            if response.status_code == 200:
                try:
                    logger.info("SUCCESS: %s", response.json())
                    return response.json()
                except Exception:
                    logger.info("SUCCESS: %s", response.text)
                    return response.text
            else:
                logger.error("FAILED: status=%s response=%s", response.status_code, response.text)
                try:
                    return response.json()
                except Exception:
                    return response.text
        except Exception as e:
            logger.error(f"ERROR calling API: {e}")
            return None

    def job_audit_log(self, job_id, job_queue_id, message):
        """
          job_id: 1133 etc
          job_queue_id: 13 etc
          message: File added to s3 and etc....
        """
        url = f"{self.base_url}/addLogs/jobId/{job_id}/jobQueueId/{job_queue_id}"
        payload = {
            "jobStatusMessage": message
        }
        try:
            response = requests.post(url, json=payload, headers=self._auth_headers())
            if response.status_code == 200:
                try:
                    logger.info("SUCCESS: %s", response.json())
                    return response.json()
                except Exception:
                    logger.info("SUCCESS: %s", response.text)
                    return response.text
            else:
                logger.error("FAILED: status=%s response=%s", response.status_code, response.text)
                try:
                    return response.json()
                except Exception:
                    return response.text
        except Exception as e:
            logger.error("ERROR calling API: %s", str(e), exc_info=True)
            return None