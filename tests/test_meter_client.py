"""
    The pipelines' meter: storage counted as it goes (deletes with their size), one batch at
    close with the run's own token, a spool when the meter is down, and never a reason for the
    job to fail.
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

import requests

from etl.util.etl_helpers import Pipeline
from etl.util.meter import GB, Meter


class FakeStat:
    def __init__(self, size):
        self.size = size


class FakeMinio:
    """Enough of MinioClient for the wrapper: a dict of bucket/key -> bytes."""

    def __init__(self):
        self.objects = {}
        self.client = self

    def stat_object(self, bucket, key):
        if (bucket, key) not in self.objects:
            raise KeyError(key)
        return FakeStat(len(self.objects[(bucket, key)]))

    def get_object_bytes(self, bucket, key):
        return self.objects.get((bucket, key))

    def upload_bytes(self, bucket, key, data, content_type="application/octet-stream"):
        self.objects[(bucket, key)] = data
        return True

    def list_objects(self, bucket, prefix=None, recursive=True):
        return [k for (b, k) in self.objects if b == bucket and k.startswith(prefix or "")]

    def delete_object(self, bucket, key):
        return self.objects.pop((bucket, key), None) is not None


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Records every POST; answers what the test scripted, in order."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        answer = self.answers.pop(0) if self.answers else FakeResponse(200, {"accepted": len(json["events"]), "duplicates": 0, "rejected": []})
        if isinstance(answer, Exception):
            raise answer
        return answer


def events_of(session, call=0):
    return session.calls[call]["json"]["events"]


class MeterClientTest(unittest.TestCase):

    def setUp(self):
        self.spool = tempfile.mkdtemp(prefix="meter-spool-")
        # No real sleeping between retries.
        import etl.util.meter as meter_module
        self._sleep = meter_module.time.sleep
        meter_module.time.sleep = lambda s: None

    def tearDown(self):
        shutil.rmtree(self.spool, ignore_errors=True)
        import etl.util.meter as meter_module
        meter_module.time.sleep = self._sleep

    def test_storage_is_counted_as_the_pipeline_goes_and_a_delete_carries_its_size(self):
        session = FakeSession([])
        store = FakeMinio()
        store.objects[("etl-bucket", "claims/in/a.txt")] = b"x" * 2048
        with Meter(2600, 6000, "tok-6000", url="http://meter", session=session, spool_dir=self.spool) as meter:
            p = Pipeline({"job_id": 2600, "job_queue_id": 6000, "bucket": "etl-bucket", "meter": meter})
            # Pipeline talks to the shared MinIO singleton; point it at the fake for this run.
            import etl.util.etl_helpers as helpers
            helpers._minio = store
            try:
                self.assertEqual(p.list_keys("claims/in/"), ["claims/in/a.txt"])
                self.assertEqual(len(p.read_bytes("claims/in/a.txt")), 2048)
                p.write_bytes("claims/out/a.gz", b"y" * 512)
                self.assertTrue(p.delete("claims/in/a.txt"))
                self.assertFalse(p.delete("claims/in/missing.txt"))
            finally:
                helpers._minio = None

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["headers"], {"X-Worker-Token": "tok-6000", "X-Job-Id": "2600", "X-Job-Queue-Id": "6000"})
        by_meter = {}
        for e in events_of(session):
            by_meter.setdefault(e["meter"], []).append(e)
        self.assertEqual(len(by_meter["storage.ops.read"]), 2)                 # the list and the get
        self.assertEqual(len(by_meter["storage.ops.write"]), 1)
        self.assertEqual(len(by_meter["storage.ops.delete"]), 1)               # the missing one is not a delete
        self.assertAlmostEqual(by_meter["storage.bytes.read"][0]["quantity"], 2048 / GB)
        self.assertAlmostEqual(by_meter["storage.bytes.written"][0]["quantity"], 512 / GB)
        self.assertAlmostEqual(by_meter["storage.bytes.deleted"][0]["quantity"], 2048 / GB)
        self.assertEqual(by_meter["storage.bytes.deleted"][0]["subjectId"], "etl-bucket/claims/in/a.txt")
        self.assertEqual(by_meter["storage.ops.write"][0]["subjectId"], "etl-bucket")
        self.assertEqual(by_meter["pipeline.worker_minutes"][0]["unit"], "minute")
        # Every key is the run's, the meter's, and numbered -- a replay of this batch is all duplicates.
        keys = [e["dedupeKey"] for e in events_of(session)]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(k.startswith("6000#") for k in keys))

    def test_a_pipeline_without_a_meter_talks_to_storage_directly(self):
        store = FakeMinio()
        import etl.util.etl_helpers as helpers
        helpers._minio = store
        try:
            p = Pipeline({"job_id": 1, "job_queue_id": 2, "bucket": "b"})
            p.write_text("k", "hello")
            self.assertEqual(p.read_text("k"), "hello")
            self.assertTrue(p.delete("k"))
        finally:
            helpers._minio = None

    def test_a_meter_that_is_down_spools_and_the_next_run_sends_it(self):
        down = FakeSession([requests.ConnectionError("refused")] * 3)
        with Meter(2600, 6000, "tok-6000", url="http://meter", session=down, spool_dir=self.spool) as meter:
            meter.event("ai.tokens.in", 1240, unit="token", subject=("prompt", "abc"))
        self.assertEqual(len(down.calls), 3)
        spooled = os.listdir(self.spool)
        self.assertEqual(len(spooled), 1)
        with open(os.path.join(self.spool, spooled[0])) as handle:
            saved = json.load(handle)
        self.assertEqual((saved["jobQueueId"], saved["token"]), (6000, "tok-6000"))
        self.assertEqual({e["meter"] for e in saved["events"]}, {"ai.tokens.in", "pipeline.worker_minutes"})

        up = FakeSession([])
        with Meter(2601, 6001, "tok-6001", url="http://meter", session=up, spool_dir=self.spool) as meter:
            meter.event("pipeline.runs", 1)
        # First the spooled batch under ITS run's token, then this run's under its own.
        self.assertEqual(len(up.calls), 2)
        self.assertEqual(up.calls[0]["headers"]["X-Job-Queue-Id"], "6000")
        self.assertEqual(up.calls[0]["headers"]["X-Worker-Token"], "tok-6000")
        self.assertEqual(up.calls[1]["headers"]["X-Job-Queue-Id"], "6001")
        self.assertEqual(os.listdir(self.spool), [])

    def test_a_refusal_is_final_and_not_spooled(self):
        refused = FakeSession([FakeResponse(401, {"detail": "The console refused this run's token."})])
        with Meter(2600, 6000, "stale", url="http://meter", session=refused, spool_dir=self.spool) as meter:
            meter.event("pipeline.runs", 1)
        self.assertEqual(len(refused.calls), 1)
        self.assertEqual(os.listdir(self.spool), [])

    def test_zero_quantities_are_not_events_and_close_is_idempotent(self):
        session = FakeSession([])
        meter = Meter(2600, 6000, "tok", url="http://meter", session=session, spool_dir=self.spool,
                      clock=lambda: datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc))
        meter.event("storage.bytes.deleted", 0)
        meter.event("ai.tokens.out", 80)
        meter.close(); meter.close()
        self.assertEqual(len(session.calls), 1)
        self.assertEqual([e["meter"] for e in events_of(session)], ["ai.tokens.out", "pipeline.worker_minutes"])
        self.assertEqual(events_of(session)[0]["occurredAt"], "2026-09-18T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
