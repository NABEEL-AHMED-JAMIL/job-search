"""
    Retention sweep: archives objects older than a cut-off, then deletes the originals.
    Author: Nabeel Ahmed Jamil

    The two irreversible things here are the copy and the delete, and they are ordered so that a
    crash anywhere leaves the data still readable: copy, read the copy back out of the bucket,
    prove it is the same size, and only then remove the original. Per object, never as a batch at
    the end -- a batch delete after a partial archive is exactly how a sweep loses a file.

    <dry_run> defaults to TRUE. A pipeline whose whole job is deleting things has to be told to
    delete; an operator who leaves the field alone gets a report, not an empty folder.
"""
import datetime
import json

from etl.util.etl_helpers import Pipeline, coerce_number, minio

# What <dry_run> may say. The XML payload carries text, and an operator typing "no" into the form
# field means no. Anything outside these sets is a typo, and a typo must not be read as consent
# to delete -- see _as_bool.
TRUE_WORDS = {"true", "yes", "y", "1", "on"}
FALSE_WORDS = {"false", "no", "n", "0", "off"}


def sweep_objects_for_retention(task_payload):
    """Entry point. Archives aged objects out of <input_folder> and writes retention.json."""
    p = Pipeline(task_payload)
    input_folder, archive_folder, older_than_days = p.require(
        "input_folder", "archive_folder", "older_than_days"
    )

    cutoff_days = _as_days(older_than_days)
    dry_run = _as_bool(task_payload.get("dry_run"))

    input_prefix = input_folder.strip().strip("/")
    archive_prefix = archive_folder.strip().strip("/")

    # An archive folder that contains the input folder would archive its own archive on the next
    # run, and the exclusion below would hide every candidate behind a bare "nothing found".
    # Caught here so the operator is told which of the two settings is wrong.
    if input_prefix == archive_prefix or input_prefix.startswith(f"{archive_prefix}/"):
        raise ValueError(
            f"F768944 cannot sweep '{input_prefix}/' into '{archive_prefix}/': the archive folder "
            f"contains the input folder, so every archived object would be swept again"
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=cutoff_days)

    found = p.list_keys(f"{input_prefix}/")
    if not found:
        # Nothing whatsoever under the prefix is a wrong folder, not a quiet bucket, and silence
        # here would be indistinguishable from a successful sweep.
        raise ValueError(
            f"F768944 found no objects under '{input_prefix}/' in bucket '{p.bucket}'"
        )

    # The archive is allowed to live under the input folder ("landing/in" -> "landing/in/old"),
    # which is a natural thing to configure; without this the sweep would re-archive yesterday's
    # archive every time it ran, burying the original path one level deeper each run.
    keys = [k for k in found if not k.startswith(f"{archive_prefix}/")]

    # Deliberately not an error, and the distinction above is the reason this is split in two: a
    # folder holding nothing but its own archive is a folder this pipeline has already finished
    # with. Raising here would make a scheduled daily sweep fail every day once it caught up.

    p.log(
        f"F768944 sweeping {len(keys)} object(s) under '{input_prefix}/' in bucket '{p.bucket}': "
        f"anything last modified before {cutoff.isoformat()} (older than {cutoff_days} day(s)) "
        f"goes to '{archive_prefix}/'"
        + (" -- DRY RUN, nothing will be copied or deleted" if dry_run
           else " and is then deleted from its original location")
    )

    archived = []
    skipped = 0
    total_bytes = 0

    for key in keys:
        last_modified, size = _stat(p, key)
        age_days = (now - last_modified).total_seconds() / 86400.0

        if last_modified >= cutoff:
            # Logged at all, because "why is this file still here" is the question an operator
            # brings to the console after a sweep.
            skipped += 1
            p.log(f"keeping {key}: {age_days:.2f} day(s) old, under the {cutoff_days} day cut-off")
            continue

        # Under the archive folder, at its full original key. Keeping the whole path rather than
        # just the file name is what makes the sweep reversible: two folders may each hold a
        # report.csv, and flattening them would silently drop one of the two.
        target = p.output_key(archive_prefix, key)

        if dry_run:
            archived.append(_record(key, target, size, last_modified, age_days,
                                    archived=False, deleted=False))
            total_bytes += size
            p.log(
                f"WOULD archive {key} -> {target} ({size} bytes, {age_days:.2f} day(s) old) "
                f"and delete the original"
            )
            continue

        original = p.read_bytes(key)
        # MinioClient.get_object_bytes logs the S3Error and returns None rather than raising, so
        # an unreadable object would otherwise be "archived" as the four bytes of "None" and the
        # real one deleted immediately afterwards.
        if original is None:
            raise RuntimeError(f"F768944 could not read {p.bucket}/{key}")

        p.write_bytes(target, original)
        _verify_archived_copy(p, key, target, len(original))

        # Only reachable once the copy has been read back out of the bucket at the right size.
        if not p.delete(key):
            raise RuntimeError(
                f"F768944 archived {key} to {target} but could not delete the original; "
                f"the archived copy is safe, the original is still in place"
            )

        archived.append(_record(key, target, size, last_modified, age_days,
                                archived=True, deleted=True))
        total_bytes += len(original)
        p.log(f"archived {key} -> {target} ({len(original)} bytes, {age_days:.2f} day(s) old), "
              f"original deleted")

    manifest = {
        "pipeline": "F768944",
        "generated_at": now.isoformat(),
        "bucket": p.bucket,
        "input_folder": input_prefix,
        "archive_folder": archive_prefix,
        "older_than_days": cutoff_days,
        "cutoff": cutoff.isoformat(),
        "dry_run": dry_run,
        "examined_count": len(keys),
        "retained_count": skipped,
        # Named for what the run did, so a dry-run manifest cannot be misread as a record of
        # deletions that never happened.
        "swept_count": len(archived),
        "swept_bytes": total_bytes,
        "objects": archived,
    }

    if dry_run:
        # A dry run that wrote a manifest would have modified the bucket it promised not to
        # touch, and would leave a retention.json describing deletions that never happened.
        # The plan goes to the audit log and back to the caller instead.
        p.log(
            f"F768944 dry run complete: {len(archived)} of {len(keys)} object(s) would be "
            f"archived to '{archive_prefix}/' and deleted ({total_bytes} bytes), "
            f"{skipped} retained. Nothing was written. Set <dry_run>false</dry_run> to apply."
        )
        return manifest

    # Written last, so it records what actually happened rather than what was intended. Each
    # sweep replaces the previous manifest; generated_at is what dates the one on disk.
    manifest_key = p.output_key(archive_prefix, "retention.json")
    p.write_json(manifest_key, manifest)

    p.log(
        f"F768944 done: archived and deleted {len(archived)} of {len(keys)} object(s) "
        f"({total_bytes} bytes), {skipped} retained. Manifest at {manifest_key}"
    )
    return manifest


def _stat(p, key):
    """(last_modified, size) for one object, straight from MinIO's own metadata.

    MinioClient.list_objects returns bare name strings -- the Object records that carry
    last_modified are discarded inside it -- so age has to come from a stat call on the
    underlying client. Object age is deliberately the bucket's opinion and not anything parsed
    out of the key: a file named 2019-01-01.csv that was uploaded this morning is one day old,
    and deleting it because of its name would destroy data the operator just put there.
    """
    stat = minio().client.stat_object(p.bucket, key)
    last_modified = stat.last_modified
    if last_modified is None:
        raise RuntimeError(
            f"F768944 cannot age {p.bucket}/{key}: the bucket reports no last_modified"
        )
    # S3 hands these back tz-aware, but a naive value compared against an aware `now` raises
    # TypeError mid-sweep, which is a poor way to find out. UTC is what the protocol says.
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=datetime.timezone.utc)
    return last_modified, int(stat.size or 0)


def _verify_archived_copy(p, key, target, expected_bytes):
    """Reads the archived copy back out of the bucket and proves it is intact.

    Nothing above the client layer notices a failed upload on its own: upload_bytes logs the
    S3Error and returns False, and Pipeline.write_bytes discards that -- so an unwritten archive
    would look exactly like a written one right up to the delete. The original is not trusted to
    the archive until the bucket has handed the copy back at the right length.
    """
    copy = p.read_bytes(target)
    if copy is None:
        raise RuntimeError(
            f"F768944 wrote {p.bucket}/{target} but could not read it back; "
            f"the original {key} has been left in place"
        )
    if len(copy) != expected_bytes:
        raise RuntimeError(
            f"F768944 archive size mismatch for {target}: {len(copy)} bytes back from "
            f"{expected_bytes} bytes in; the original {key} has been left in place"
        )
    return copy


def _as_days(value):
    """<older_than_days> as a non-negative number of days.

    A negative cut-off is a future timestamp, which matches nothing and would report a clean
    sweep over a folder it never touched; that reads as success and is worth refusing.
    """
    days = coerce_number(value)
    if days is None:
        raise ValueError(
            f"F768944 could not read <older_than_days> value '{value}' as a number of days"
        )
    if days < 0:
        raise ValueError(
            f"F768944 was given a negative <older_than_days> ({value}); "
            f"use 0 to sweep everything"
        )
    return days


def _as_bool(value):
    """<dry_run> as a real boolean, defaulting to True and refusing anything ambiguous.

    Absent means True because deletion is opt-in: a payload written before this field existed, or
    a form field an operator left alone, must not delete anything. An unrecognised word raises
    rather than falling back to either default -- reading a typo as False would delete on a
    misspelling, and reading it as True would hide the typo behind a report that never applies.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return True
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    raise ValueError(
        f"F768944 could not read <dry_run> value '{value}' as true or false; "
        f"use one of {sorted(TRUE_WORDS)} or {sorted(FALSE_WORDS)}"
    )


def _record(key, target, size, last_modified, age_days, archived, deleted):
    return {
        "key": key,
        "archived_to": target,
        "size_bytes": size,
        "last_modified": last_modified.isoformat(),
        "age_days": round(age_days, 4),
        "archived": archived,
        "deleted": deleted,
    }


if __name__ == "__main__":
    # Local smoke run: the listener normally supplies job_id/job_queue_id, and without them
    # Pipeline.log() stays in the container log instead of calling the backend. Left as a dry
    # run, which is the only safe thing for a module you can execute by accident.
    print(json.dumps(sweep_objects_for_retention({
        "id": "F768944",
        "input_folder": "etl-demo/f768944/in",
        "archive_folder": "etl-demo/f768944/archive",
        "older_than_days": "30",
        "dry_run": "true",
        "job_id": None,
        "job_queue_id": None,
    }), indent=2))
