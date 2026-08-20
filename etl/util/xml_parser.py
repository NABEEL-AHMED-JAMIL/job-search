"""
    Xml parser
    @author: Nabeel Ahmed Jamil
"""
import xml.etree.ElementTree as ET
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)

# ------------------------------------------------------------------------------
# Parser Pipeline with Id
# ------------------------------------------------------------------------------
def parse_927(xml_payload):
    """
        Method use to parse F768927
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
          <input_folder>audio_text/input</input_folder>
          <output_folder>audio_text/output</output_folder>
        </pipeline>
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
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
            <start_year>1975</start_year>
            <end_year>2026</end_year>
            <hurricanes_url>https://en.wikipedia.org/wiki/{year}_Pacific_hurricane_season</hurricanes_url>
            <folder>hurricane/output</folder>
        </pipeline>
    """
    try:
        root = ET.fromstring(xml_payload)
        return {
            "id": "F768926",
            "start_year": root.find("start_year").text,
            "end_year": root.find("end_year").text,
            "hurricanes_url": root.find("hurricanes_url").text,
            "folder": root.find("folder").text
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return None

def parse_925(xml_payload):
    """
        Method use to parse pipeline config (session, pdfHighlighter, description)
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
            <session>
                <username>jessica.davis</username>
                <password>jessica.davis</password>
                <auth> http://localhost:9999/v1/api/auth/login</auth>
            </session>
            <pdfHighlighter>
                <organizationsTask>ZER23428</organizationsTask>
                <fieldMappingUrl>http://localhost:9999/v1/api/organizations/{organizationUuid}/pdf-highlighters/by-name/{organizationsTask}</fieldMappingUrl>
                <targetInputFileFolder>highlighter/input</targetInputFileFolder>
                <targetOutputFileFolder>highlighter/output</targetOutputFileFolder>
                <targetOutputType>JSON</targetOutputType>
            </pdfHighlighter>
            <description>Executes the complete form automation workflow by retrieving form definitions and field mappings from FormCraft, reading all supported files from the target folder, extracting and transforming the data into CSV format, invoking the form-filling API to populate the target form, and submitting the completed form once processing is finished.</description>
        </pipeline>
    """
    try:
        root = ET.fromstring(xml_payload)
        session = root.find("session")
        pdf_highlighter = root.find("pdfHighlighter")
        return {
            "id": "F768925",
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
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
            <session>
                <accounts>highlighter/account/cvsh-user-account.csv</accounts>
                <auth_url> http://localhost:9999/v1/api/auth/login</auth_url>
            </session>
            <highlighter>
                <input_object_path>highlighter/output/job_1014_queue_1050/0dcb58be-435f-44b7-8706-cf86b5c53c10/pdf_highlighter_extract_1785025740.json</input_object_path>
                <form_uuid>915419ee-296e-4708-b168-868c8bd5b8bd</form_uuid>
                <form_description>Unique UUID of the form used by the ETL process.</form_description>
                <panel_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels</panel_url>
                <panel_description>URL of the source panel or web page that the ETL process accesses to extract data.</panel_description>
                <fields_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}/panels/{panel_uuid}/fields</fields_url>
                <fields_description>URL of the page or endpoint containing the form fields that the ETL process uses to extract or map data.</fields_description>
                <submissions_url>http://localhost:9999/v1/api/organizations/{organization_uuid}/forms/{form_uuid}submissions</submissions_url>
                <submissions_description>URL of the page or endpoint used by the ETL process to access and retrieve form submission data.</submissions_description>
            </highlighter>
        </pipeline>
    """
    try:
        root = ET.fromstring(xml_payload)
        session = root.find("session")
        highlighter = root.find("highlighter")
        return {
            "id": "F768924",
            "session": {
                "accounts": session.find("accounts").text,
                "auth_url": session.find("auth_url").text
            },
            "highlighter": {
                "input_object_path": highlighter.find("input_object_path").text,
                "form_uuid": highlighter.find("form_uuid").text,
                "panels_url": highlighter.find("panels_url").text,
                "fields_url": highlighter.find("fields_url").text,
                "submissions_url": highlighter.find("submissions_url").text,
            }
        }
    except Exception:
        logger.exception("Failed to parse pipeline config XML")
        return None

def parse_920(xml_payload):
    """
        Method use to parse F768920
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
            <bucket>zanium-bucket</bucket>
            <credential>zanium-dev/myConfig.json</credential>
            <extracted_data>zanium-dev/data/</extracted_data>
            <target_type>CSV</target_type>
            <target_table_config>
                <tables>users</tables>
            </target_table_config>
        </pipeline>
    """
    try:
        root = ET.fromstring(xml_payload)
        target_table_config = root.find("target_table_config")
        tables = []
        if target_table_config is not None:
            tables = [table_el.text.strip() for table_el in target_table_config.findall("tables") if table_el.text]
        return {
            "id": "F768920",
            "bucket": root.find("bucket").text,
            "credential": root.find("credential").text,
            "extracted_data": root.find("extracted_data").text,
            "target_type": root.find("target_type").text,
            "target_table_config": tables
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return None

def parse_76800(xml_payload):
    """
        Method use to parse F76800
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <pipeline>
            <email_config_uuid>50240e3f-45e3-466a-be44-ad1503d7c9ff</email_config_uuid>
            <recipients_bucket>etl-bucket</recipients_bucket>
            <recipients_object>email-batch/input/recipients.csv</recipients_object>
        </pipeline>

        email_config_uuid is just the submission's uuid -- NOT a full URL. The full
        fetchSubmissionByUuid URL is built at runtime from ETL_EVENT_URL (env-configured
        per execution environment: host.docker.internal inside a container, localhost for
        the host-venv workflow), since a URL baked into stored pipeline config would only
        be correct for whichever environment happened to write it.
    """
    try:
        root = ET.fromstring(xml_payload)
        recipients_bucket_el = root.find("recipients_bucket")
        recipients_object_el = root.find("recipients_object")
        return {
            "id": "F76800",
            "email_config_uuid": root.find("email_config_uuid").text,
            "recipients_bucket": recipients_bucket_el.text if recipients_bucket_el is not None else None,
            "recipients_object": recipients_object_el.text if recipients_object_el is not None else None
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
        return None

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
    'F768922': parse_922,
    'F768920': parse_920,
    'F76800': parse_76800
}

if __name__ == '__main__':
    # Test the parser with a sample XML payload
    sample_xml = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <pipeline>
        <input_folder>audio_text/input</input_folder>
        <output_folder>audio_text/output</output_folder>
    </pipeline>"""

    parsed_data = parse_927(sample_xml)
    logger.info(f"Parsed Data: {parsed_data}")