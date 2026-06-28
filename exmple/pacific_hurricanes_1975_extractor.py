# Import required packages
from datetime import datetime
import os
import logging
import json
import requests  # To make HTTP requests to the Wikipedia page
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup  # To parse HTML content
from dotenv import load_dotenv  # To load environment variables, such as API keys
from typing import Optional, Union

# Load environment variables from .env if present
load_dotenv()

# Base URL template for Pacific hurricane season pages
BASE_URL_TEMPLATE = os.getenv(
    "PACIFIC_HURRICANES_BASE_URL",
    "https://en.wikipedia.org/wiki/{year}_Pacific_hurricane_season",
)

def get_url_content(
    url: str,
    timeout: int = 10,
    retries: int = 3,
    backoff_factor: float = 0.3,
    session: Optional[requests.Session] = None,
) -> Optional[Union[BeautifulSoup, str]]:
    """
        Fetch and parse HTML content from the given URL.
        Parameters
        - url: URL to fetch
        - timeout: request timeout in seconds
        - retries: number of retries for transient errors
        - backoff_factor: backoff multiplier between retries
        - session: optional requests.Session to use (helps testing)

        Returns a BeautifulSoup object or raw text on success, or None on failure.
    """
    logger = logging.getLogger(__name__)
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
    except requests.exceptions.RequestException as exc:
        logger.warning("Error fetching %s: %s", url, exc)
        return None

    try:
        soup = BeautifulSoup(response.content, "html.parser")
    except Exception as exc:
        logger.warning("Error parsing HTML content from %s: %s", url, exc)
        return None

    logger.info("Successfully fetched and parsed the content of %s", url)
    return soup

def extract_hurricane_name(soup: BeautifulSoup, year: int = 1975, use_ollama: bool = False) -> list:
    """
        Extract hurricane data from the BeautifulSoup object.
        Parses the Wikipedia Pacific hurricane season page to extract
        hurricane names and details from infoboxes.

        Parameters:
        - soup: BeautifulSoup object
        - year: year of the hurricane season (used for date parsing)
        - use_ollama: if True, use Ollama to extract deaths/areas from text

        Returns a list of dictionaries, each containing hurricane data.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Extracting hurricanes for %s", year)

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
            "content": "",
            "start_date": None,
            "end_date": None,
            "deaths": 0,
            "affected_areas": ""
        }
        # ----------------------------
        # Extract paragraph content
        # ----------------------------
        for sibling in h3.find_next_siblings():
            if sibling.name == "div" and "mw-heading3" in sibling.get("class", []):
                break
            if sibling.name == "p":
                storm_obj["content"] += sibling.get_text(strip=True) + " "

        # Use Ollama to extract structured info from text
        if use_ollama and storm_obj["content"]:
            logger.debug(f"Querying Ollama for {storm_name}...")
            info = extract_info_from_text(storm_obj["content"])
            storm_obj["deaths"] = info.get("number_of_deaths", 0)
            storm_obj["affected_areas"] = ",".join(info.get("areas_affected", []))

        hurricane_storm.append(storm_obj)

    # ----------------------------
    # STEP 2: Extract infobox dates
    # ----------------------------
    tables = body_content.find_all("table", class_="infobox")
    table_index = 0
    for table in tables:
        if table.get('class') != ['infobox']:
            continue
        date_cell = table.find("td", class_="infobox-data")
        if not date_cell:
            continue

        raw_dates = date_cell.get_text(strip=True).split("\xa0–")
        start_date = convert_date(raw_dates[0].strip(), year=year) if len(raw_dates) > 0 else None
        end_date = convert_date(raw_dates[1].strip(), year=year) if len(raw_dates) > 1 else None

        # attach safely (avoid index crash)
        if table_index < len(hurricane_storm):
            hurricane_storm[table_index]["start_date"] = start_date
            hurricane_storm[table_index]["end_date"] = end_date
        table_index += 1

    return hurricane_storm

def convert_date(date_string, year=1975):
    """
    Convert date string to YYYY-MM-DD format.
    Handles edge cases like "July 2 (Entered basin)" by extracting just the month/day.
    """
    logger = logging.getLogger(__name__)
    try:
        # Remove parenthetical suffixes like "(Entered basin)" or "(exited basin)"
        clean_date = date_string.split('(')[0].strip()
        date_object = datetime.strptime(f"{clean_date} {year}", "%B %d %Y")
        return date_object.strftime("%Y-%m-%d")
    except ValueError as e:
        logger.warning(f"Failed to parse date '{date_string}': {e}")
        return None

def fetch_and_extract_all_seasons(start_year: int = 1950, end_year: int = 2026, use_ollama: bool = False) -> dict:
    """
        Fetch and extract hurricane data for multiple Pacific hurricane seasons.

        Parameters:
            - start_year: beginning year (default 1950)
            - end_year: ending year inclusive (default 2026)
            - use_ollama: if True, use Ollama to extract deaths/areas info

        Returns a dictionary mapping year -> list of hurricane data
    """
    logger = logging.getLogger(__name__)
    all_seasons_data = {}

    for year in range(start_year, end_year + 1):
        season_url = BASE_URL_TEMPLATE.format(year=year)
        logger.info(f"Fetching data for {year}...")
        soup = get_url_content(season_url)
        if soup is None:
            logger.warning(f"Failed to fetch data for year {year}")
            all_seasons_data[year] = []
            continue

        hurricanes = extract_hurricane_name(soup, year=year, use_ollama=use_ollama)
        all_seasons_data[year] = hurricanes
        logger.info(f"Extracted {len(hurricanes)} hurricanes from {year}")

    return all_seasons_data

def extract_info_from_text(text: str, ollama_url: str = "http://localhost:11434") -> dict:
    """
    Use Ollama LLM to extract death counts and affected areas from hurricane text.

    Parameters:
    - text: hurricane description text
    - ollama_url: base URL for Ollama API (default localhost:11434)

    Returns a dictionary with 'number_of_deaths' and 'areas_affected' keys
    """
    logger = logging.getLogger(__name__)

    if not text or len(text.strip()) < 10:
        return {"number_of_deaths": 0, "areas_affected": []}

    prompt = f"""Extract from the text the following information in JSON format:
        1. The number of deaths (key='number_of_deaths') as an integer (if no deaths, return 0).
        2. A list of areas affected (key='areas_affected') as a list of strings (mention locations only).
        
        Text: {text[:1000]}
        
        Respond ONLY with valid JSON, no markdown or code blocks. Example:
        {{"number_of_deaths": 5, "areas_affected": ["California", "Mexico"]}}"""

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        response_text = result.get("response", "").strip()
        # Parse JSON from response
        data = json.loads(response_text)
        return {
            "number_of_deaths": int(data.get("number_of_deaths", 0)),
            "areas_affected": data.get("areas_affected", [])
        }
    except requests.exceptions.RequestException as e:
        logger.warning(f"Ollama request failed: {e}")
        return {"number_of_deaths": 0, "areas_affected": []}
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse Ollama response: {e}")
        return {"number_of_deaths": 0, "areas_affected": []}

# export OLLAMA_ENABLED=true && export TEST_MODE=true
# export OLLAMA_ENABLED=true && export TEST_MODE=false
if __name__ == "__main__":
    # Configure basic logging for CLI runs
    logging.basicConfig(level=logging.INFO)
    # Fetch and extract data for all seasons from 1950 to 2026
    logger = logging.getLogger(__name__)
    logger.info("Starting extraction for Pacific hurricane seasons 1950-2026...")

    # Use Ollama by default if available; disable with OLLAMA_ENABLED=false
    use_ollama = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"
    if use_ollama:
        logger.info("Ollama integration ENABLED - will extract deaths/areas from text")
    else:
        logger.info("Ollama integration DISABLED - skipping LLM text extraction")

    # For testing, only process recent years. Remove this in production.
    test_mode = os.getenv("TEST_MODE", "true").lower() == "true"
    if test_mode:
        logger.info("TEST MODE: Processing only 2023-2024")
        all_data = fetch_and_extract_all_seasons(start_year=2023, end_year=2024, use_ollama=use_ollama)
    else:
        logger.info("PRODUCTION MODE: Processing 1950-2026 (this will take a while)")
        all_data = fetch_and_extract_all_seasons(start_year=1950, end_year=2026, use_ollama=use_ollama)

    # Display summary
    total_hurricanes = sum(len(hurricanes) for hurricanes in all_data.values())
    logger.info(f"Total years processed: {len(all_data)}")
    logger.info(f"Total hurricanes extracted: {total_hurricanes}")

    # Print sample data from first available year
    for year in sorted(all_data.keys()):
        if all_data[year]:
            print(f"\n✓ Year {year}: {len(all_data[year])} hurricanes")
            print(f"  Sample: {all_data[year][0]}")
    else:
        print("No hurricane data extracted.")

