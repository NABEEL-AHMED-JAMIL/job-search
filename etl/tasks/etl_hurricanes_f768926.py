# Import required packages
import io
import pandas as pd
import time
import os
import requests  # To make HTTP requests to the Wikipedia page
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup  # To parse HTML content
from dotenv import load_dotenv  # To load environment variables, such as API keys
from typing import Optional, Union
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


def get_url_content(
    task_payload,
    url: str,
    timeout: int = 10,
    retries: int = 3,
    backoff_factor: float = 0.3,
    session: Optional[requests.Session] = None,
) -> Optional[Union[BeautifulSoup, str]]:
    """
        Fetch and parse HTML content from the given URL.
        Returns a BeautifulSoup object or raw text on success, or None on failure.
    """
    # Use an environment-configurable User-Agent. Set JOBSEARCH_USER_AGENT in your
    # .env or environment to a value like:
    # JobSearchBot/1.0 (+https://example.org; contact: ops@example.org)
    headers = {
        "User-Agent": os.getenv(
            "JOBSEARCH_USER_AGENT",
            "JobSearchBot/1.0 (+https://example.org; contact: ops@example.org)",
        )
    }
    # allow injection of a session for testing; otherwise create one
    sess = session or requests.Session()
    # attach retry strategy only when we created the session locally
    if session is None:
        retry_strategy = Retry(
            total=retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=backoff_factor,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)

    try:
        logger.debug("GET %s (timeout=%s, retries=%s)", url, timeout, retries)
        response = sess.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        job_audit_log(task_payload, f"Successfully fetched content from {url}")
    except requests.exceptions.RequestException as exc:
        logger.warning("Error fetching %s: %s", url, exc)
        job_audit_log(task_payload, f"Error fetching {url} :: {exc}")
        return None

    try:
        soup = BeautifulSoup(response.content, "html.parser")
    except Exception as exc:
        logger.warning("Error parsing HTML content from %s: %s", url, exc)
        job_audit_log(task_payload, f"Error parsing HTML content from {url}: {exc}")
        return None

    logger.info("Successfully fetched and parsed the content of %s", url)
    job_audit_log(task_payload, f"Successfully fetched and parsed the content of {url}")
    return soup

def extract_hurricane_name(task_payload, soup: BeautifulSoup, year: int) -> list:
    """
        Extract hurricane data from the BeautifulSoup object.
        Parses the Wikipedia Pacific hurricane season page to extract hurricane names and details from infoboxes.
        Returns a list of dictionaries, each containing hurricane data.
    """
    logger.debug(f"Extracting hurricanes for {year}")
    job_audit_log(task_payload, f"Extracting hurricanes for {year}")
    body_content = soup.find("div", {"class": "mw-body-content"})
    hurricane_storm = []
    if not body_content:
        return hurricane_storm
    # ----------------------------
    # STEP 1: Extract storm sections
    # ----------------------------
    headings = body_content.find_all("div", class_="mw-heading mw-heading3")
    for h3 in headings:
        h3_title = h3.find("h3")
        if not h3_title:
            continue
        storm_name = h3_title.get_text(strip=True)
        storm_obj = {
            "name": storm_name,
            "content": ""
        }
        # ----------------------------
        # Extract paragraph content
        # ----------------------------
        for sibling in h3.find_next_siblings():
            if sibling.name == "div" and "mw-heading3" in sibling.get("class", []):
                break
            if sibling.name == "p":
                storm_obj["content"] += sibling.get_text(strip=True) + " "

        hurricane_storm.append(storm_obj)

    return hurricane_storm


def save_to_bucket(task_payload, year, hurricane_storm):
    """
        Save the extracted hurricane data to a CSV file in MinIO, under
        {folder}/job_{job_id}_queue_{job_queue_id}/hurricane_data_{year}.csv
        (folder comes from the pipeline's <folder> config, e.g. "hurricane/output").
    """
    time.sleep(0.1)
    # folder should be jobId and queue id
    output_prefix = "/".join([
        task_payload["folder"],
        f"job_{task_payload['job_id']}_queue_{task_payload['job_queue_id']}"
    ])
    # Create DataFrame for clean the data
    df = pd.DataFrame(hurricane_storm)
    # remove the "Other system" entries which are not actual hurricanes
    df = df[df["name"] != "Other system"]
    # remove the extract stuff
    df["content"] = df["content"].str.replace(r"\[\d+\]", "", regex=True)
    df["content"] = df["content"].str.strip()
    # Save CSV file to MinIO
    object_name = f"{output_prefix}/hurricane_data_{year}.csv"
    job_audit_log(task_payload, f"Uploading {object_name} to {minio_bucket}...")
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    if not minio_client.upload_bytes(minio_bucket, object_name, buffer.getvalue(), content_type="text/csv"):
        logger.error(f"Could not upload {object_name} to MinIO bucket {minio_bucket}.")
        job_audit_log(task_payload, f"Could not upload {object_name} to MinIO bucket {minio_bucket}.")
        raise RuntimeError(f"Could not upload extracted output to {minio_bucket}/{object_name}")
    logger.info(f"Data for {year} saved successfully to {minio_bucket}/{object_name}.")
    job_audit_log(task_payload, f"Data for {year} saved successfully to {minio_bucket}/{object_name}.")

def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)

def fetch_and_extract_all_seasons(task_payload):
    """
        Fetch and extract hurricane data for multiple Pacific hurricane seasons.
        Returns a dictionary mapping year -> list of hurricane data
    """
    for year in range(int(task_payload["start_year"]), int(task_payload["end_year"]) + 1):
        season_url = str(task_payload["hurricanes_url"]).format(year=year)
        logger.info(f"Fetching data for {year}...")
        job_audit_log(task_payload, f"Fetching data for {year}...")
        soup = get_url_content(task_payload, season_url)

        if soup is None:
            logger.warning(f"Failed to fetch data for year {year}")
            job_audit_log(task_payload, f"Failed to fetch data for year {year}")
            continue

        hurricanes = extract_hurricane_name(task_payload, soup, year)
        logger.info(f"Extracted {len(hurricanes)} hurricanes from {year}")
        job_audit_log(task_payload, f"Extracted {len(hurricanes)} hurricanes from {year}")
        if len(hurricanes) > 0:
            save_to_bucket(task_payload, year, hurricanes)
