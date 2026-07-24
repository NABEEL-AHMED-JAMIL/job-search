import logging
import colorlog
import xml.etree.ElementTree as ET

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
# Parser Pipeline with Id
# ------------------------------------------------------------------------------
def parse_927(xml_payload):
    """
        Method use to parse F768927
    """
    try:
        root = ET.fromstring(xml_payload)
        return {
            "id": "F768927",
            "input_folder": root.find("input_folder").text,
            "output_folder": root.find("output_folder").text
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return None

def parse_926(xml_payload):
    """
        Method use to parse F768926
    """
    try:
        root = ET.fromstring(xml_payload)
        return {
            "id": "F768926",
            "start_year": root.find("start_year").text,
            "end_year": root.find("end_year").text,
            "hurricanes_url": root.find("hurricanes_url").text
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return None

def parse_925(xml_payload):
    """
        Method use to parse pipeline config (session, pdfHighlighter, description)
    """
    try:
        root = ET.fromstring(xml_payload)
        session = root.find("session")
        pdf_highlighter = root.find("pdfHighlighter")
        return {
            "session": {
                "username": session.find("username").text,
                "password": session.find("password").text,
                "auth": session.find("auth").text
            },
            "pdfHighlighter": {
                "organizationsTask": pdf_highlighter.find("organizationsTask").text,
                "fieldMappingUrl": pdf_highlighter.find("fieldMappingUrl").text,
                "targetInputFileFolder": pdf_highlighter.find("targetInputFileFolder").text,
                "targetOutputFileFolder": pdf_highlighter.find("targetOutputFileFolder").text,
                "targetOutputType": pdf_highlighter.find("targetOutputType").text,
            },
            "description": root.find("description").text
        }
    except Exception:
        logger.exception("Failed to parse pipeline config XML")
        return None

def parse_924(xml_payload):
    """
        Method use to parse F768924
    """
    return {
        "id": "F768924"
    }

def parse_923(xml_payload):
    """
        Method use to parse F768923
    """
    return {
        "id": "F768923"
    }

def parse_922(xml_payload):
    """
        Method use to parse F768922
    """
    return {
        "id": "F768922"
    }

def tpd_test_task_payload_parser(xml_payload):
    """
        Parse task payload xml string and extract task name and task parameters
    """
    try:
        root = ET.fromstring(xml_payload)
        start_el = root.find("start")
        end_el = root.find("end")
        start = start_el.text if start_el is not None else None
        end = end_el.text if end_el is not None else None
        return {
            "start": start,
            "end": end
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return {"start": None, "end": None}

# Mapping of pipeline id to parser function
pipeline_xml_parser = {
    'F768927': parse_927,
    'F768926': parse_926,
    'F768925': parse_925,
    'F768924': parse_924,
    'F768923': parse_923,
    'F768922': parse_922
}