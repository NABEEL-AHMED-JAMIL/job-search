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
        # <bucket> is optional: tasks written before it existed have none, and those keep
        # falling back to MINIO_BUCKET_NAME. Where it is set, it is what routes a tenant's
        # output into that tenant's own bucket.
        bucket = root.find("bucket")
        return {
            "id": "F768926",
            "start_year": root.find("start_year").text,
            "end_year": root.find("end_year").text,
            "hurricanes_url": root.find("hurricanes_url").text,
            "folder": root.find("folder").text,
            "bucket": bucket.text if bucket is not None else None
        }
    except Exception:
        logger.exception("Failed to parse task payload XML")
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

# ------------------------------------------------------------------------------
# Object-storage ETL pipelines (F768930 - F768944)
#
# Every one of these takes a flat list of tags -- no nesting, no namespaces -- so they
# are declared rather than hand-written. Fifteen near-identical try/find/except blocks
# would be fifteen chances to typo a tag name into a silent None, and the tag list is
# the interesting part of each parser anyway; here it is the whole of it.
# ------------------------------------------------------------------------------
def _tag_text(root, name):
    """Text of a direct child tag: stripped, or None when the tag is absent or blank.

    Stripped because XmlOutTagInfoUtil indents its output, so a value can arrive
    surrounded by newlines; blank-to-None because a tag the console rendered but the
    operator left empty means "not set", exactly as an absent one does.
    """
    element = root.find(name)
    if element is None:
        return None
    value = (element.text or "").strip()
    return value or None


def _flat_parser(pipeline_id, tags):
    """A parser for a pipeline whose payload is a flat list of tags.

    Absent tags come back as None rather than raising. Deciding which of them a run
    cannot proceed without belongs to the task -- Pipeline.require names the missing
    setting in one sentence an operator can act on, where a KeyError in here would
    surface as a stack trace against a line number in the parser.
    """
    def parse(xml_payload):
        try:
            root = ET.fromstring(xml_payload)
            parsed = {"id": pipeline_id}
            for tag in tags:
                parsed[tag] = _tag_text(root, tag)
            return parsed
        except Exception:
            logger.exception("Failed to parse %s task payload XML", pipeline_id)
            return None

    parse.__name__ = "parse_" + pipeline_id.lower()
    parse.__doc__ = (
        f"Method use to parse {pipeline_id}\n"
        f"        Tags: {', '.join(tags)}"
    )
    return parse


# <bucket> is optional on all fifteen and absent means "the platform bucket", the
# convention parse_926 established. It is what routes a tenant's data into that
# tenant's own bucket, so every pipeline in the family accepts it.
parse_f768930 = _flat_parser("F768930", (
    "input_folder", "output_folder", "format", "bucket"))
parse_f768931 = _flat_parser("F768931", (
    "input_folder", "output_folder", "required_columns", "numeric_columns",
    "summary_name", "bucket"))
parse_f768932 = _flat_parser("F768932", (
    "input_folder", "output_folder", "key_columns", "keep", "bucket"))
parse_f768933 = _flat_parser("F768933", (
    "input_folder", "output_folder", "column", "operator", "value", "bucket"))
parse_f768934 = _flat_parser("F768934", (
    "input_folder", "output_folder", "output_name", "add_source_column", "bucket"))
parse_f768935 = _flat_parser("F768935", (
    "input_folder", "output_folder", "group_by", "aggregation", "aggregate_column",
    "bucket"))
parse_f768936 = _flat_parser("F768936", (
    "input_folder", "output_folder", "column_mapping", "bucket"))
parse_f768937 = _flat_parser("F768937", (
    "input_folder", "output_folder", "bucket"))
parse_f768938 = _flat_parser("F768938", (
    "input_key", "output_folder", "rows_per_chunk", "bucket"))
parse_f768946 = _flat_parser("F768946", (
    "input_folder", "output_folder", "suffix", "bucket"))

# The imaging analyser. <prompt> and <model> are settings rather than constants because the
# prompt is most of the quality -- a first draft offering the model an "unreadable" exit got
# "unreadable" back on a good film -- and because the same pipeline serves CT and MRI once
# <modality> and <prompt> say so.
parse_f768947 = _flat_parser("F768947", (
    "input_folder", "output_folder", "prompt", "model", "modality", "extensions",
    "max_images", "max_edge", "force_reprocess", "bucket"))
parse_f768939 = _flat_parser("F768939", (
    "input_folder", "output_folder", "suffix", "delete_source", "bucket"))
parse_f768940 = _flat_parser("F768940", (
    "input_folder", "target_table", "db_host", "db_port", "db_name", "db_user",
    "db_password", "db_schema", "truncate_before_load", "bucket"))
parse_f768941 = _flat_parser("F768941", (
    "query", "output_folder", "output_name", "db_host", "db_port", "db_name",
    "db_user", "db_password", "bucket"))
parse_f768942 = _flat_parser("F768942", (
    "left_object", "right_object", "join_key", "output_folder", "output_name",
    "join_type", "right_suffix", "bucket"))
parse_f768943 = _flat_parser("F768943", (
    "previous_object", "current_object", "output_folder", "key_columns", "prefix",
    "bucket"))
parse_f768945 = _flat_parser("F768945", (
    "input_object", "partition_column", "output_folder", "prefix", "max_partitions",
    "bucket"))
parse_f768944 = _flat_parser("F768944", (
    "input_folder", "archive_folder", "older_than_days", "dry_run", "bucket"))


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
    'F768920': parse_920,
    'F76800': parse_76800,
    # Object-storage ETL family
    'F768930': parse_f768930,
    'F768931': parse_f768931,
    'F768932': parse_f768932,
    'F768933': parse_f768933,
    'F768934': parse_f768934,
    'F768935': parse_f768935,
    'F768936': parse_f768936,
    'F768937': parse_f768937,
    'F768938': parse_f768938,
    'F768939': parse_f768939,
    'F768940': parse_f768940,
    'F768941': parse_f768941,
    'F768942': parse_f768942,
    'F768943': parse_f768943,
    'F768944': parse_f768944,
    'F768945': parse_f768945,
    # The for-each. <suffix> is optional -- absent means every object in the folder.
    'F768946': parse_f768946,
    # Imaging analysis. Everything past <output_folder> is optional and has a default in the task.
    'F768947': parse_f768947
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