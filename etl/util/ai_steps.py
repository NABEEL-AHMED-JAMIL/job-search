"""
    AI steps handed to the worker
    @author: Nabeel Ahmed Jamil

    A pipeline can carry an AI step that runs in the worker rather than on the server before
    dispatch. The server puts it into the task's document as

        <ai_step prompt="<uuid>" version="3" output="summary" on_error="fail">
          <var name="claim_id" from="claim_id" as="text"/>
          <var name="document_text" from="document" as="file"/>
        </ai_step>

    The worker resolves each variable -- the text of a tag, or the contents of the object a tag
    names (that is the one thing the server cannot do for it) -- asks the console to run the
    prompt through POST /aiPrompt.json/run, proved by the run's own callback token, writes the
    answer to the output tag and drops the element. Every pipeline's parser then sees an
    ordinary tag; no task module knows a model was involved.

    The key never reaches this process: the console holds it, makes the call, records the run
    with its tokens and time, and hands back the text.

    A step whose variable reads `from="object"` runs once per object under the task's
    <input_folder> in its <bucket> -- the object's contents (as="text") or its key (as="name")
    -- and each answer is written to <output_folder>/<object basename>.<output tag>.json|txt,
    the same folders every object-storage pipeline reads and writes. The output tag then holds
    a small JSON manifest (how many objects, which were written, which failed) rather than one
    answer. The console records one run per object (tag#key), so a retried run skips the
    objects already answered.
"""
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

from etl.util.logging_config import get_logger

logger = get_logger(__name__)

# A model answers in seconds; a long document to a small local model can take a minute or two.
RUN_TIMEOUT = (5, 300)
# The largest object handed to a prompt as text. Past this the text is cut, and the run says so.
MAX_FILE_CHARS = 200_000
# The most objects one step runs over. A folder of thousands is a budget question, not a loop.
MAX_OBJECTS_PER_STEP = 200


class AiStepError(Exception):
    """A step failed and said the run must (on_error="fail")."""


def resolve_ai_steps(task_payload_xml, job_id, job_queue_id, callback_token, bucket=None, read_object=None, audit=None,
                     list_objects=None, write_object=None):
    """
        The document with every <ai_step> replaced by its answer as <output>…</output>.

        Returns the XML unchanged when there is no step, so every pipeline pays nothing for
        the check. `read_object(bucket, key)` supplies a file's bytes for a var read as a file;
        the default reads through the shared MinIO client, resolved lazily so this module
        stays importable without the minio package (the tests hand a fake in). `audit(line)`
        receives one line per step for the run's history -- what the server-side step writes
        for itself -- so a reader of the run's logs sees the same story whichever side ran it.
    """
    audit = audit or (lambda line: None)
    if not task_payload_xml or "<ai_step" not in task_payload_xml:
        return task_payload_xml
    root = ET.fromstring(task_payload_xml)
    steps = list(root.findall("ai_step"))
    if not steps:
        return task_payload_xml
    base_url = _console_base_url()
    # A file is read from the bucket the task names (<bucket>), else the caller's, else the
    # platform's -- the same rule every task in the object-storage family follows.
    if bucket is None:
        bucket_tag = root.find("bucket")
        bucket = (bucket_tag.text or "").strip() if bucket_tag is not None else None
    for step in steps:
        output = step.get("output")
        on_error = step.get("on_error") or "fail"
        try:
            if any(var.get("from") == "object" for var in step.findall("var")):
                manifest = _run_per_object(root, step, base_url, job_id, job_queue_id, callback_token, bucket,
                                           read_object, list_objects, write_object, audit, on_error)
                _set_tag(root, output, json.dumps(manifest))
                continue
            variables = _resolve_variables(root, step, bucket, read_object)
            started = time.monotonic()
            answer, run = _run(base_url, job_id, job_queue_id, callback_token, step, variables)
            _set_tag(root, output, answer)
            logger.info("AI step <%s> answered for job %s run %s", output, job_id, job_queue_id)
            audit("AI step <%s>: answered in the worker in %.1f s (%s in, %s out tokens)." % (
                output, time.monotonic() - started, run.get("tokensIn", "?"), run.get("tokensOut", "?")))
        except Exception as ex:
            if on_error == "continue":
                logger.warning("AI step <%s> failed and the pipeline continues with it empty: %s", output, ex)
                audit("AI step <%s> failed and the pipeline continues with it empty: %s" % (output, ex))
                _set_tag(root, output, "")
            else:
                audit("AI step <%s> failed: %s" % (output, ex))
                raise AiStepError("AI step <%s> failed: %s" % (output, ex)) from ex
        finally:
            root.remove(step)
    return ET.tostring(root, encoding="unicode")


def _run_per_object(root, step, base_url, job_id, job_queue_id, callback_token, bucket,
                    read_object, list_objects, write_object, audit, on_error):
    """
        The step once per object under <input_folder>: each answer written to <output_folder>,
        the manifest of what happened handed back for the output tag. With on_error="fail" the
        first failure stops the loop and fails the run; with "continue" the object is listed as
        failed and the rest go on.
    """
    output = step.get("output")
    input_folder = _tag_text_of(root, "input_folder")
    output_folder = _tag_text_of(root, "output_folder")
    if not input_folder:
        raise AiStepError("the task names no <input_folder> for the step to read")
    lister = list_objects or _default_list_objects
    reader = read_object or _default_read_object
    writer = write_object or _default_write_object
    prefix = input_folder.strip().strip("/") + "/"
    keys = [k for k in (lister(bucket, prefix) or []) if not k.endswith("/")]
    if len(keys) > MAX_OBJECTS_PER_STEP:
        raise AiStepError("%d objects under %s; a step runs over at most %d" % (len(keys), prefix, MAX_OBJECTS_PER_STEP))
    manifest = {"objects": len(keys), "written": [], "failed": []}
    audit("AI step <%s>: %d object(s) under %s." % (output, len(keys), prefix))
    json_mode = None
    for key in keys:
        started = time.monotonic()
        try:
            variables = _resolve_variables(root, step, bucket, reader, object_key=key)
            answer, run = _run(base_url, job_id, job_queue_id, callback_token, step, variables, item=key)
            written = None
            if output_folder:
                base = key.rsplit("/", 1)[-1]
                looks_json = answer.lstrip().startswith("{")
                written = "%s/%s.%s.%s" % (output_folder.strip().strip("/"), base, output, "json" if looks_json else "txt")
                writer(bucket, written, answer.encode("utf-8"), "application/json" if looks_json else "text/plain")
            manifest["written"].append({"object": key, "output": written})
            audit("AI step <%s>: %s answered in %.1f s (%s in, %s out tokens)%s." % (
                output, key, time.monotonic() - started, run.get("tokensIn", "?"), run.get("tokensOut", "?"),
                (" -> " + written) if written else ""))
        except Exception as ex:
            manifest["failed"].append({"object": key, "error": str(ex)[:300]})
            audit("AI step <%s>: %s failed: %s" % (output, key, ex))
            if on_error != "continue":
                raise AiStepError("%s failed: %s" % (key, ex)) from ex
    return manifest


def _tag_text_of(root, tag):
    element = root.find(tag)
    return (element.text or "").strip() if element is not None else ""


def _default_list_objects(bucket, prefix):
    from etl.util.etl_helpers import DEFAULT_BUCKET, minio
    return minio().list_objects(bucket or DEFAULT_BUCKET, prefix=prefix, recursive=True)


def _default_write_object(bucket, key, data, content_type):
    from etl.util.etl_helpers import DEFAULT_BUCKET, minio
    minio().upload_bytes(bucket or DEFAULT_BUCKET, key, data, content_type=content_type)


def _console_base_url():
    """The console's API root. ETL_EVENT_URL already names it for the status callbacks."""
    url = (os.getenv("ETL_EVENT_URL") or "").strip().rstrip("/")
    if not url:
        raise AiStepError("ETL_EVENT_URL is not set; the worker cannot ask the console to run a prompt")
    return url


def _resolve_variables(root, step, bucket, read_object, object_key=None):
    values = {}
    for var in step.findall("var"):
        name = var.get("name")
        source = var.get("from") or ""
        if source == "object":
            # The object this iteration is on: its key, or its contents read from the bucket.
            if (var.get("as") or "text") == "name":
                values[name] = object_key or ""
                continue
            reader = read_object or _default_read_object
            data = reader(bucket, object_key) if object_key else None
            if data is None:
                raise AiStepError("object %s for {{%s}} could not be read" % (object_key, name))
            text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + "\n[content truncated -- the file continues beyond what's shown here]"
            values[name] = text
            continue
        element = root.find(source) if source else None
        text = (element.text or "").strip() if element is not None else ""
        if (var.get("as") or "text") == "file":
            if not text:
                values[name] = ""
                continue
            reader = read_object or _default_read_object
            data = reader(bucket, text)
            if data is None:
                raise AiStepError("object %s for {{%s}} could not be read" % (text, name))
            text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + "\n[content truncated -- the file continues beyond what's shown here]"
        values[name] = text
    return values


def _default_read_object(bucket, key):
    from etl.util.etl_helpers import DEFAULT_BUCKET, minio
    return minio().get_object_bytes(bucket or DEFAULT_BUCKET, key)


def _run(base_url, job_id, job_queue_id, callback_token, step, variables, item=None):
    """POST /aiPrompt.json/run and hand back the answer text, or raise with the console's reason."""
    body = {
        "jobId": job_id,
        "jobQueueId": job_queue_id,
        "promptUuid": step.get("prompt"),
        "version": int(step.get("version") or 0) or None,
        "stepTag": step.get("output"),
        "item": item,
        "variables": variables,
    }
    headers = {"X-Worker-Token": callback_token} if callback_token else {}
    response = requests.post(base_url + "/aiPrompt.json/run", json=body, headers=headers, timeout=RUN_TIMEOUT)
    if response.status_code == 401:
        raise AiStepError("the console refused the run's token")
    if response.status_code != 200:
        raise AiStepError("HTTP %s from the console: %s" % (response.status_code, response.text[:300]))
    answer = response.json()
    if answer.get("status") != "SUCCESS":
        raise AiStepError(answer.get("message") or "the console could not run the prompt")
    run = answer.get("data") or {}
    return run.get("output") or "", run


def _set_tag(root, tag, value):
    element = root.find(tag)
    if element is None:
        element = ET.SubElement(root, tag)
        element.tail = "\n"
    element.text = value or ""
    for child in list(element):
        element.remove(child)
