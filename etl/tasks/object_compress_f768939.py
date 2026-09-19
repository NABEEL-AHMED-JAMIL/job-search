"""
    Gzips every object under an input folder for archival, and reports how much it saved.
    Author: Nabeel Ahmed Jamil

    The deletion of a source object is the only irreversible thing this pipeline does, so it is
    the last thing it does per object and it only happens once the compressed copy has been read
    back out of the bucket and decompressed to exactly the original bytes. Compress, verify,
    then delete -- in that order, per object, never in a batch at the end.
"""
import datetime
import gzip
import json

from etl.util.etl_helpers import Pipeline, minio

# What <delete_source> may say. The XML payload carries text, and an operator typing "yes" into
# the form field means yes; anything outside this set is a typo and is treated as a refusal to
# delete rather than as consent.
TRUE_WORDS = {"true", "yes", "y", "1", "on"}
FALSE_WORDS = {"false", "no", "n", "0", "off", ""}


def compress_objects_for_archival(task_payload):
    """Entry point. Gzips <input_folder> into <output_folder> and writes compression.json."""
    p = Pipeline(task_payload)
    input_folder, output_folder = p.require("input_folder", "output_folder")

    suffix = (task_payload.get("suffix") or "").strip() or None
    delete_source = _as_bool(task_payload.get("delete_source"), "delete_source")

    input_prefix = input_folder.strip().strip("/")
    output_prefix = output_folder.strip().strip("/")

    keys = p.list_keys(f"{input_prefix}/", suffix=suffix)
    # An output folder nested inside the input folder is a perfectly reasonable thing for an
    # operator to configure ("archive/in" -> "archive/in/gz"), but without this the run would
    # compress its own output, and a rerun would compress that again.
    keys = [k for k in keys if not k.startswith(f"{output_prefix}/")]

    if not keys:
        # Silence here would be indistinguishable from success. An empty match is nearly always
        # a wrong folder or a suffix with a missing dot, so it is a failure, not a no-op.
        raise ValueError(
            f"F768939 found no objects to compress under '{input_prefix}/' in bucket "
            f"'{p.bucket}'" + (f" matching suffix '{suffix}'" if suffix else "")
        )

    p.log(
        f"F768939 compressing {len(keys)} object(s) from '{input_prefix}/' into "
        f"'{output_prefix}/' in bucket '{p.bucket}'"
        + (f", filtered to '{suffix}'" if suffix else "")
        + (", deleting each source once its copy verifies" if delete_source
           else ", keeping the sources")
    )

    results = []
    total_original = 0
    total_compressed = 0

    for key in keys:
        original = p.read_bytes(key)
        # MinioClient.get_object_bytes logs and returns None instead of raising, so an
        # unreadable object would otherwise be compressed as the four bytes of "None".
        if original is None:
            raise RuntimeError(f"F768939 could not read {p.bucket}/{key}")

        # The full file name, not the stem: sales.csv and sales.json in one folder must not both
        # want to be sales.gz, and keeping the extension is what makes the .gz self-describing.
        target = p.output_key(output_prefix, f"{p.basename(key)}.gz")
        p.write_gzip(target, original)

        compressed = _verify_roundtrip(p, target, original)

        total_original += len(original)
        total_compressed += len(compressed)

        deleted = False
        if delete_source:
            # Only reachable past _verify_roundtrip, which is the whole point of this pipeline.
            if not p.delete(key):
                raise RuntimeError(
                    f"F768939 verified {target} but could not delete the source {key}; "
                    f"the compressed copy is safe, the source is still there"
                )
            deleted = True

        results.append({
            "source": key,
            "target": target,
            "original_bytes": len(original),
            "compressed_bytes": len(compressed),
            "compression_ratio": _ratio(len(original), len(compressed)),
            "source_deleted": deleted,
        })
        p.log(
            f"{key} -> {target}: {len(original)} -> {len(compressed)} bytes "
            f"({_percent_saved(len(original), len(compressed))})"
            + (" | source deleted" if deleted else "")
        )

    summary = {
        "pipeline": "F768939",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bucket": p.bucket,
        "input_folder": input_prefix,
        "output_folder": output_prefix,
        "suffix": suffix,
        "delete_source": delete_source,
        "object_count": len(results),
        "total_original_bytes": total_original,
        "total_compressed_bytes": total_compressed,
        # compressed / original: below 1.0 is a saving, and it is spelled out in the key name
        # because "compression ratio" is written both ways round in the wild.
        "compression_ratio": _ratio(total_original, total_compressed),
        "bytes_saved": total_original - total_compressed,
        "percent_saved": _percent_saved(total_original, total_compressed),
        "objects": results,
    }
    # Written last, so what it records is what actually happened -- including the deletions.
    summary_key = p.output_key(output_prefix, "compression.json")
    p.write_json(summary_key, summary)

    p.log(
        f"F768939 done: {len(results)} object(s), {total_original} -> {total_compressed} bytes "
        f"({_percent_saved(total_original, total_compressed)}, ratio "
        f"{summary['compression_ratio']}). Summary at {summary_key}"
    )
    return summary


def _verify_roundtrip(p, target, original):
    """Reads the just-written .gz back out of the bucket and proves it still holds `original`.

    Nothing above the client layer notices a failed upload on its own: upload_bytes logs the
    S3Error and returns False, and Pipeline.write_gzip discards that. Since <delete_source> is
    allowed to destroy the input, the copy is not trusted until the bucket has handed it back
    and it has decompressed byte for byte.
    """
    compressed = p.read_bytes(target)
    if compressed is None:
        raise RuntimeError(f"F768939 wrote {p.bucket}/{target} but could not read it back")
    try:
        restored = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise RuntimeError(f"F768939 wrote {p.bucket}/{target} but it is not valid gzip: {exc}")
    if restored != original:
        raise RuntimeError(
            f"F768939 round-trip mismatch for {target}: {len(restored)} bytes back from "
            f"{len(original)} bytes in"
        )
    return compressed


def _as_bool(value, field):
    """<delete_source> as a real boolean, refusing anything ambiguous.

    Defaulting an unrecognised word to True would let a typo delete an operator's only copy, and
    defaulting it to False would hide the typo; raising is the only reading that does neither.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    raise ValueError(
        f"F768939 could not read <{field}> value '{value}' as true or false; "
        f"use one of {sorted(TRUE_WORDS)} or {sorted(FALSE_WORDS - {''})}"
    )


def _ratio(original_bytes, compressed_bytes):
    """compressed / original, or None when there was nothing to divide by."""
    if not original_bytes:
        return None
    return round(compressed_bytes / original_bytes, 4)


def _percent_saved(original_bytes, compressed_bytes):
    if not original_bytes:
        return "n/a"
    return f"{(1 - compressed_bytes / original_bytes) * 100:.1f}% saved"


if __name__ == "__main__":
    # Local smoke run: the listener normally supplies job_id/job_queue_id, and without them
    # Pipeline.log() stays in the container log instead of calling the backend.
    print(json.dumps(compress_objects_for_archival({
        "id": "F768939",
        "input_folder": "etl-demo/f768939/in",
        "output_folder": "etl-demo/f768939/out",
        "job_id": None,
        "job_queue_id": None,
    }), indent=2))
