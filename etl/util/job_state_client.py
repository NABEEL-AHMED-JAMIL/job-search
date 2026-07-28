"""
    Job State Client
    @author: Nabeel Ahmed Jamil
"""
import requests
import logging
import colorlog

# Configure colored logging
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter('%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))
logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class JobStateClient:

    def __init__(self, base_url):
        self.base_url = base_url

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
            response = requests.post(url, json=payload)
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
            response = requests.post(url, json=payload)
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