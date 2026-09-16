"""
    Reads medical images from a folder, asks a vision model what is visible in each, and writes
    one structured JSON result per image.
    Author: Nabeel Ahmed Jamil

    <b>This produces an image-analysis aid, never a diagnosis.</b> That is not a disclaimer bolted
    on at the end: `_envelope` stamps the non-diagnostic notice and the model's own limits onto
    every document this pipeline writes, including the failures, and it does so AFTER the model
    has spoken. The prompt is operator-editable -- which is the point, since the prompt is most of
    the quality -- and that means a prompt could be written that omits every caution. The stamp is
    outside the prompt's reach for exactly that reason. Clinical decisions stay with clinicians.

    Built to take other modalities without a second pipeline. Nothing here knows what a chest is:
    <modality> and <prompt> carry that, so pointing it at CT or MRI is a task-form change rather
    than a code change. The only image-specific thing in the file is which extensions it opens.

    Two measured facts shaped the design, both from llava:7b on this dataset on 2026-09-15:

      * <b>The prompt decides whether this works at all.</b> A first prompt offering "if the image
        is unreadable, say so" got "unreadable" back on a perfectly good chest film -- the model
        took the cheap exit. The same image, same model, without that exit, returned four
        anatomical findings. Hence <prompt> is a setting an operator can tune, not a constant.
      * <b>The confidence numbers are not calibrated.</b> Every finding came back at exactly 1.0.
        They are carried through because the schema asks for them and a better model may mean
        them, but `model.confidence_calibrated: false` is written beside them so nobody reads a
        1.0 here as the model being certain. It is the model having no opinion.
"""
import base64
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from etl.util.etl_helpers import Pipeline

# Where the vision model lives. The same host the worker already reaches MinIO on, so a
# deployment that can read images can also analyse them without further configuration.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

DEFAULT_MODEL = "llava:7b"
DEFAULT_MODALITY = "X-Ray"
DEFAULT_EXTENSIONS = ("jpg", "jpeg", "png")

# Longest edge handed to the model, in pixels.
#
# 672 rather than the source resolution: llava's vision tower works at a fixed patch grid, so a
# 2090x1858 film is downscaled inside the model anyway -- sending it whole spends upload and
# encode time to arrive at the same tensor. Measured on one film, 672 returned four findings in
# 7.4s where 896 returned one in 3.6s; the larger image was not better, it was terser.
DEFAULT_MAX_EDGE = 672

# A single analysis is seconds, but a folder is not.
#
# The dataset this was written against holds 12,534 images; at the measured 4-8s each that is
# most of a day inside one Kafka message, and the run would be killed as stalled long before it
# finished (reconcileStalledRuns closes anything in flight for six hours). <max_images> is how a
# scheduled run takes a bite instead: with skip-already-done below, successive runs advance
# through the folder on their own.
DEFAULT_MAX_IMAGES = 100

# Read timeout for one analysis. Generous because a cold model loads on the first call.
ANALYSIS_TIMEOUT_SECONDS = 300

# The default prompt. Deliberately without an "if you cannot read it, say so" clause -- see the
# module docstring for what that clause did. An operator can replace the whole of this through
# <prompt>; the safety stamp in _envelope does not come from here and cannot be edited out.
DEFAULT_PROMPT = """Describe what is visible in this medical image.

Return ONLY a JSON object with these keys:
{"body_part": "the anatomical region shown",
 "findings": [{"finding": "short name", "description": "what is visible", "confidence": 0.0}],
 "overall_assessment": "one or two sentences summarising what the image shows",
 "uncertainty": "what limits this analysis"}

List at least one finding describing what you can actually see, including normal structures.
confidence is between 0.0 and 1.0. Describe only what the image supports. Do not state a
diagnosis and do not invent findings."""

NON_DIAGNOSTIC_NOTICE = (
    "Automated image analysis for triage support only. This is NOT a diagnosis and has not been "
    "reviewed by a clinician. Findings may be incomplete or wrong. Clinical decisions must be "
    "made by a qualified healthcare professional."
)


def _image_id(source_key):
    """A stable id for an image, derived from its path.

    Deterministic rather than random: a re-run of the same image has to produce the same id, or
    the output folder accumulates a new identity for a file every time the pipeline is forced
    over it and nothing downstream can tell the versions apart.
    """
    return hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:16]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _preprocess(raw, max_edge):
    """Open the image, normalise it for the model, and return PNG bytes.

    Never touches the stored object -- this is a copy in memory, and the original is not written
    back under any path in this file.

    Converted to RGB because these films are 8-bit greyscale (mode "L") and the model's encoder
    expects three channels; PNG rather than JPEG because a second lossy pass over an already
    compressed film adds artefacts to the very thing being examined.
    """
    from PIL import Image  # imported here, not at module scope: see PIPELINE_TASKS in the listener

    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        source_size = image.size
        source_mode = image.mode
        # EXIF orientation is applied rather than ignored. A film stored rotated and displayed
        # upright by its viewer would otherwise reach the model on its side, and left/right is
        # not a detail that can be wrong in a chest image.
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass
        if image.mode != "RGB":
            image = image.convert("RGB")
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), {
            "source_size": list(source_size),
            "source_mode": source_mode,
            "analysed_size": list(image.size),
        }


def _analyse(model, prompt, png_bytes):
    """One call to the vision model. Returns the parsed JSON object it produced.

    `format: json` is asked for rather than hoped for: without it the model wraps its object in
    prose and every caller has to go hunting for the braces.
    """
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [base64.b64encode(png_bytes).decode("ascii")],
        "stream": False,
        "format": "json",
        # Low but not zero. This is description, not creative writing, and a run repeated over
        # the same folder should not disagree with itself about what is in a film.
        "options": {"temperature": 0.1},
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=ANALYSIS_TIMEOUT_SECONDS) as response:
        outer = json.loads(response.read().decode("utf-8"))

    text = (outer.get("response") or "").strip()
    if not text:
        raise ValueError("the model returned an empty response")
    return json.loads(text)


def _clean_findings(raw_findings):
    """Coerce whatever the model produced into the finding shape, dropping what cannot be used.

    Models return this field as a list of objects, a list of bare strings, or a single object.
    All three are accepted because the alternative is discarding a good analysis over its
    packaging; anything else becomes an empty list and the caller says so in `uncertainty`.
    """
    if isinstance(raw_findings, dict):
        raw_findings = [raw_findings]
    if not isinstance(raw_findings, list):
        return []

    findings = []
    for item in raw_findings:
        if isinstance(item, str):
            item = {"finding": item}
        if not isinstance(item, dict):
            continue
        name = str(item.get("finding") or item.get("name") or "").strip()
        if not name:
            continue
        entry = {
            "finding": name,
            "description": str(item.get("description") or "").strip(),
        }
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)):
            # Clamped rather than rejected. A model answering 95 means 0.95, and refusing the
            # finding over its scale would throw away the only content in it.
            value = float(confidence)
            if value > 1.0:
                value = value / 100.0 if value <= 100.0 else 1.0
            entry["confidence"] = round(max(0.0, min(1.0, value)), 3)
        findings.append(entry)
    return findings


def _envelope(source_key, modality, model, status, **extra):
    """The parts of the document that do not come from the model.

    Every result passes through here, including failures, and this is where the non-diagnostic
    notice is applied. Keeping it out of the prompt is deliberate: <prompt> is operator-editable,
    so a caution that lived only in the prompt could be deleted by editing a form field, and the
    one sentence that must survive every edit is this one.
    """
    document = {
        "image_id": _image_id(source_key),
        "source_file": source_key,
        "processed_at": _now(),
        "modality": modality,
        "analysis_status": status,
        "model": {
            "name": model,
            "version": model,
            # Stated because the numbers look like they mean something and do not. llava:7b
            # returned exactly 1.0 for every finding across this dataset; a reader filtering on
            # "confidence > 0.9" would be filtering on nothing.
            "confidence_calibrated": False,
        },
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }
    document.update(extra)
    return document


def _validate(document):
    """Refuse to write a document that is not the shape this pipeline promises.

    Checked before the write rather than after, so a malformed result never reaches the output
    folder at all -- a downstream reader finding half a schema there cannot tell whether the
    pipeline is broken or the image was.
    """
    required = ("image_id", "source_file", "processed_at", "modality", "analysis_status", "model")
    missing = [key for key in required if not document.get(key)]
    if missing:
        raise ValueError(f"result is missing required field(s): {', '.join(missing)}")

    status = document["analysis_status"]
    if status not in ("completed", "failed"):
        raise ValueError(f"analysis_status must be 'completed' or 'failed', got '{status}'")

    if status == "completed":
        if not isinstance(document.get("findings"), list):
            raise ValueError("a completed result must carry a findings list")
        for finding in document["findings"]:
            confidence = finding.get("confidence")
            if confidence is not None and not 0.0 <= confidence <= 1.0:
                raise ValueError(f"confidence out of range: {confidence}")
    elif not isinstance(document.get("error"), dict):
        raise ValueError("a failed result must carry an error object")

    # Proves the document survives a round trip before it is written. A value the model produced
    # that json.dumps cannot serialise would otherwise fail inside write_json, after the log line
    # claiming the image was analysed.
    json.dumps(document)
    return document


def _failure(source_key, modality, model, error_type, message):
    return _envelope(source_key, modality, model, "failed",
                     error={"type": error_type, "message": str(message)[:500]})


def xray_ai_analysis(task_payload):
    """Entry point. One JSON result per image under <input_folder>, into <output_folder>.

    Required: <input_folder>, <output_folder>.
    Optional: <bucket>, <model>, <prompt>, <modality>, <extensions>, <max_images>,
              <max_edge>, <force_reprocess>.
    """
    pipeline = Pipeline(task_payload)
    input_folder, output_folder = pipeline.require("input_folder", "output_folder")

    model = pipeline.payload.get("model") or DEFAULT_MODEL
    prompt = pipeline.payload.get("prompt") or DEFAULT_PROMPT
    modality = pipeline.payload.get("modality") or DEFAULT_MODALITY
    force = str(pipeline.payload.get("force_reprocess") or "").strip().lower() in ("true", "1", "yes")

    extensions = tuple(
        part.strip().lower().lstrip(".")
        for part in (pipeline.payload.get("extensions") or ",".join(DEFAULT_EXTENSIONS)).split(",")
        if part.strip()
    ) or DEFAULT_EXTENSIONS

    max_images = _positive_int(pipeline.payload.get("max_images"), DEFAULT_MAX_IMAGES)
    max_edge = _positive_int(pipeline.payload.get("max_edge"), DEFAULT_MAX_EDGE)

    started_at = datetime.now(timezone.utc)
    execution_id = str(pipeline.job_queue_id or _image_id(f"{input_folder}{started_at}"))

    # Discovery. Every object under the folder is listed and then filtered here rather than by
    # passing one suffix to list_keys, because a folder of images holds several extensions and
    # the point is to take all of them.
    all_keys = pipeline.list_keys(input_folder)
    images = [key for key in all_keys
              if os.path.splitext(key)[1].lower().lstrip(".") in extensions]
    ignored = len(all_keys) - len(images)

    # Already-done detection, which is what makes a scheduled run over a large folder work at
    # all. One listing of the output folder rather than a HEAD per image: 12,000 round trips to
    # decide what to skip would cost more than the analyses.
    existing = set() if force else {
        pipeline.stem(key) for key in pipeline.list_keys(output_folder, suffix=".json")
    }

    pipeline.log(
        f"{modality} analysis of {pipeline.bucket}/{input_folder}: {len(images)} image(s) found"
        + (f", {ignored} non-image object(s) ignored" if ignored else "")
        + (f", {len(existing)} already analysed" if existing else "")
        + f". Model {model}, up to {max_images} this run"
        + (" (force re-processing)" if force else "")
    )

    processed, skipped, failed = [], [], []
    for key in images:
        if len(processed) + len(failed) >= max_images:
            # Not an error, and not silent. Stopping quietly here is how a half-swept folder gets
            # reported as a finished one; the summary carries the remainder so the next run --
            # or the operator raising max_images -- knows there is more.
            break

        name = pipeline.stem(key)
        if name in existing:
            skipped.append(key)
            continue

        output_key = pipeline.output_key(output_folder, f"{name}.json")
        position = len(processed) + len(failed) + 1
        try:
            raw = pipeline.read_bytes(key)
            png_bytes, geometry = _preprocess(raw, max_edge)

            started = time.time()
            analysis = _analyse(model, prompt, png_bytes)
            elapsed = round(time.time() - started, 2)

            findings = _clean_findings(analysis.get("findings"))
            uncertainty = str(analysis.get("uncertainty") or "").strip()
            if not findings:
                # Said plainly in the document rather than left as an empty list for a reader to
                # interpret. An empty findings list and "the model described nothing" are the
                # same fact, and only one of them survives being skim-read.
                uncertainty = (uncertainty + " " if uncertainty else "") + \
                    "The model returned no usable findings for this image."

            document = _envelope(
                key, modality, model, "completed",
                body_part=str(analysis.get("body_part") or "").strip() or "unspecified",
                findings=findings,
                overall_assessment=str(analysis.get("overall_assessment") or "").strip(),
                recommendation="Clinical review recommended.",
                uncertainty=uncertainty or "No limitations were reported by the model.",
                source=dict(geometry, bytes=len(raw)),
                analysis_seconds=elapsed,
            )
            pipeline.write_json(output_key, _validate(document))
            processed.append(key)
            pipeline.log(
                f"[{position}] {pipeline.basename(key)} -> {output_key} "
                f"({len(findings)} finding(s), {elapsed}s)"
            )
        except Exception as exc:
            # One bad image does not end the sweep, and it does not vanish either: the failure
            # is written to the same output folder in the same shape, so a reader counting
            # results finds one per input whatever happened. This is the lesson folder_for_each
            # records -- a sweep that stops at the first unreadable file leaves the rest
            # unexamined until somebody removes that file by hand.
            error_type = _error_type(exc)
            try:
                pipeline.write_json(
                    output_key, _validate(_failure(key, modality, model, error_type, exc)))
            except Exception as write_failure:
                # The error document itself could not be written -- storage is unreachable or
                # full. Nothing further can be recorded for this image, so say so in the run log,
                # which is the one channel left.
                pipeline.log(f"[{position}] {key} -- failed, and its error file could not be "
                             f"written either: {write_failure}")
            failed.append({"key": key, "type": error_type, "error": str(exc)[:300]})
            pipeline.log(f"[{position}] {pipeline.basename(key)} -- {error_type}: {exc}")

    remaining = len(images) - len(processed) - len(failed) - len(skipped)
    summary = {
        "execution_id": execution_id,
        "job_id": pipeline.job_id,
        "modality": modality,
        "model": model,
        "input_folder": input_folder,
        "output_folder": output_folder,
        "total_files": len(images),
        "processed": len(processed),
        "skipped": len(skipped),
        "failed": len(failed),
        "remaining": max(0, remaining),
        "ignored_non_images": ignored,
        "failures": failed[:50],
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed_at": _now(),
        "duration_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 1),
        "disclaimer": NON_DIAGNOSTIC_NOTICE,
    }
    summary_key = pipeline.output_key(output_folder, f"_execution-{execution_id}.json")
    pipeline.write_json(summary_key, summary)

    pipeline.log(
        f"{modality} analysis complete: {len(processed)} analysed, {len(skipped)} skipped, "
        f"{len(failed)} failed, {summary['remaining']} left for the next run. "
        f"Summary at {summary_key}"
    )

    # Every image failing is a pipeline failure, not a set of individual ones. The usual cause is
    # one thing wrong for all of them -- the model is not pulled, the host is unreachable -- and
    # a run that writes 100 error documents and reports success hides that behind a green tick.
    if images and not processed and failed:
        raise RuntimeError(
            f"all {len(failed)} image(s) failed; first error was "
            f"{failed[0]['type']}: {failed[0]['error']}"
        )
    return summary


def _error_type(exc):
    """A stable, greppable classification of what went wrong with one image."""
    if isinstance(exc, (urllib.error.URLError, urllib.error.HTTPError, TimeoutError)):
        return "AI_MODEL_ERROR"
    if isinstance(exc, json.JSONDecodeError):
        return "AI_RESPONSE_ERROR"
    if isinstance(exc, ValueError):
        return "VALIDATION_ERROR"
    return "IMAGE_PROCESSING_ERROR"


def _positive_int(value, fallback):
    """A positive integer from a form field, or the fallback.

    Operator-typed, so "", "abc" and "0" all have to mean "leave it alone" rather than crash a
    run or set a limit of zero images.
    """
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback
