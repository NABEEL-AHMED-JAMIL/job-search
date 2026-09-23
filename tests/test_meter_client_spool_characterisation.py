"""
    MIG-200 -- characterisation of the pipelines' reporting clients, before the migration:
    etl/util/meter.py (the Meter: batch, retry, spool, replay) and etl/util/job_state_client.py
    (audit-log line batching).

    These pin what the code does TODAY. Where today's behaviour contradicts the rule it is meant to
    keep (no usage or log line lost silently, reporting never fails a job), the test still asserts
    TODAY's behaviour and its name ends in _DEFECT, so the gap is visible and a fix shows up as a
    deliberate test change. No network: the HTTP layer is a fake, or the real meter app in-process.
"""
import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

os.environ["METER_ROLLUP_SECONDS"] = "0"     # no background thread from create_app

import requests  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import etl.util.job_state_client as jsc_module  # noqa: E402
import etl.util.meter as meter_module  # noqa: E402
from etl.meter.app import create_app  # noqa: E402
from etl.meter.store import MemoryStore  # noqa: E402
from etl.util.meter import Meter  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOCK = lambda: datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)  # noqa: E731


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Records every POST (a deep copy of the body); answers what the test scripted, in order.
    Once the script runs out it accepts everything."""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": _copy(json), "headers": dict(headers or {})})
        answer = self.answers.pop(0) if self.answers else FakeResponse(200, {"accepted": len(json["events"]), "duplicates": 0, "rejected": []})
        if callable(answer) and not isinstance(answer, FakeResponse):
            answer = answer(url, json, headers)
        if isinstance(answer, Exception):
            raise answer
        return answer


class AppSession:
    """The real meter service in-process, as the Meter's session (drops `timeout`, which TestClient
    warns about)."""

    def __init__(self, test_client):
        self.client = test_client
        self.statuses = []

    def post(self, url, json=None, headers=None, timeout=None):
        response = self.client.post(url, json=json, headers=headers)
        self.statuses.append(response.status_code)
        return response


def _copy(body):
    return json.loads(json.dumps(body))


def events_sent(session, call=0):
    return session.calls[call]["json"]["events"]


def verify(job_id, job_queue_id, token):
    if token and token.startswith("tok-"):
        return 2905
    raise HTTPException(status_code=401, detail="refused")


class _SpoolCase(unittest.TestCase):

    def setUp(self):
        self.spool = tempfile.mkdtemp(prefix="meter-spool-char-")
        self._sleep = meter_module.time.sleep
        meter_module.time.sleep = lambda s: None          # no real back-off between retries

    def tearDown(self):
        shutil.rmtree(self.spool, ignore_errors=True)
        meter_module.time.sleep = self._sleep

    def meter(self, session, job_queue_id=6000, token="tok-6000", job_id=2600):
        return Meter(job_id, job_queue_id, token, url="http://testserver", session=session, spool_dir=self.spool, clock=CLOCK)

    def spooled(self):
        out = []
        for name in sorted(os.listdir(self.spool)):
            if os.path.isdir(os.path.join(self.spool, name)):
                continue
            with open(os.path.join(self.spool, name), encoding="utf-8") as handle:
                out.append((name, json.load(handle)))
        return out

    def parked(self):
        """What the client set aside for a person to look at: never retried, never deleted."""
        dead = os.path.join(self.spool, "dead")
        return sorted(os.listdir(dead)) if os.path.isdir(dead) else []

    def parked_body(self, name):
        with open(os.path.join(self.spool, "dead", name), encoding="utf-8") as handle:
            return handle.read()

    def write_spool(self, name, body):
        with open(os.path.join(self.spool, name), "w", encoding="utf-8") as handle:
            handle.write(body if isinstance(body, str) else json.dumps(body))


# ---------------------------------------------------------------------------------------------
class MeterSpoolTest(_SpoolCase):
    """
    MIG-200 -- a meter that cannot be reached loses nothing: the whole batch is spooled after three
    tries, and the next run replays it first, under the ORIGINAL run's token, with the events
    unchanged -- same order, same occurredAt, same dedupeKey ("{jobQueueId}#{meter}#{seq}") -- so a
    replay the service has already seen counts once.
    """

    def test_an_unreachable_meter_spools_the_whole_batch_nothing_dropped(self):
        down = FakeSession([requests.ConnectionError("refused")] * 3)
        with self.meter(down) as m:
            m.event("ai.tokens.in", 1240, unit="token", subject=("prompt", "abc"))
            m.event("storage.ops.read", 1, unit="op", subject=("bucket", "b"))
            m.event("storage.ops.read", 1, unit="op", subject=("bucket", "b"))
        self.assertEqual(len(down.calls), 3)                                   # three tries
        self.assertTrue(all(c["json"] == down.calls[0]["json"] for c in down.calls))
        [(name, saved)] = self.spooled()
        self.assertTrue(re.fullmatch(r"6000-\d+\.json", name), name)
        self.assertEqual((saved["jobId"], saved["jobQueueId"], saved["token"]), (2600, 6000, "tok-6000"))
        self.assertEqual(saved["events"], events_sent(down))                   # exactly what was attempted
        self.assertEqual([e["dedupeKey"] for e in saved["events"]],
                         ["6000#ai.tokens.in#1", "6000#storage.ops.read#1", "6000#storage.ops.read#2", "6000#pipeline.worker_minutes#1"])

    def test_a_5xx_is_retried_three_times_then_spooled(self):
        busy = FakeSession([FakeResponse(503)] * 3)
        with self.meter(busy) as m:
            m.event("pipeline.runs", 1)
        self.assertEqual(len(busy.calls), 3)
        self.assertEqual(len(self.spooled()), 1)

    def test_replay_sends_the_spooled_events_unchanged_in_order_with_their_dedupe_keys(self):
        down = FakeSession([requests.ConnectionError("x")] * 3)
        with self.meter(down) as m:
            for i in range(5):
                m.event("storage.ops.write", 1, unit="op", subject=("bucket", f"b{i}"))
        original = events_sent(down)

        up = FakeSession()
        with self.meter(up, job_queue_id=6001, token="tok-6001", job_id=2601) as m:
            m.event("pipeline.runs", 1)
        self.assertEqual(len(up.calls), 2)
        self.assertEqual(events_sent(up, 0), original)                        # byte-for-byte: order, occurredAt, dedupeKey
        self.assertEqual(up.calls[0]["headers"], {"X-Worker-Token": "tok-6000", "X-Job-Id": "2600", "X-Job-Queue-Id": "6000"})
        self.assertEqual(up.calls[1]["headers"]["X-Job-Queue-Id"], "6001")    # this run's own batch after
        self.assertEqual(self.spooled(), [])

    def test_a_replay_the_service_already_has_counts_once(self):
        # Against the real service: the same spooled batch replayed twice lands once.
        store = MemoryStore()
        app = AppSession(TestClient(create_app(store=store, verify_run=verify, service_key="k")))
        down = FakeSession([requests.ConnectionError("x")] * 3)
        with self.meter(down) as m:
            m.event("ai.tokens.in", 1000, unit="token")
        [(name, saved)] = self.spooled()
        self.write_spool("6000-0000000000001-copy.json", saved)               # the same file twice
        with self.meter(app, job_queue_id=6001, token="tok-6001") as m:
            pass
        self.assertEqual(app.statuses, [200, 200, 200])
        self.assertEqual(sorted(e["dedupe_key"] for e in store.events),
                         ["6000#ai.tokens.in#1", "6000#pipeline.worker_minutes#1", "6001#pipeline.worker_minutes#1"])
        self.assertEqual(self.spooled(), [])

    def test_a_failed_replay_keeps_the_file_and_is_tried_once_per_run(self):
        down = FakeSession([requests.ConnectionError("x")] * 3)
        with self.meter(down) as m:
            m.event("pipeline.runs", 1)
        still_down = FakeSession([requests.ConnectionError("x")])             # replay gets ONE try
        with self.meter(still_down, job_queue_id=6001, token="tok-6001") as m:
            pass
        self.assertEqual(still_down.calls[0]["headers"]["X-Job-Queue-Id"], "6000")
        self.assertEqual(still_down.calls[1]["headers"]["X-Job-Queue-Id"], "6001")
        self.assertEqual(len(still_down.calls), 2)
        self.assertEqual(sorted(s["jobQueueId"] for _, s in self.spooled()), [6000])

    def test_replay_is_capped_at_twenty_files_per_run_and_the_rest_wait(self):
        for i in range(25):
            self.write_spool(f"{7000 + i}-1.json", {"jobId": 1, "jobQueueId": 7000 + i, "token": "t", "events": [{"dedupeKey": f"k{i}"}]})
        up = FakeSession()
        with self.meter(up) as m:
            pass
        self.assertEqual(len(up.calls), 21)                                   # 20 replays + this run
        self.assertEqual([c["headers"]["X-Job-Queue-Id"] for c in up.calls[:20]], [str(7000 + i) for i in range(20)])
        self.assertEqual([s["jobQueueId"] for _, s in self.spooled()], [7020, 7021, 7022, 7023, 7024])

    def test_an_unparseable_spool_file_is_parked_and_logged_not_dropped(self):
        # MIG-200: kept for a person (dead/), but no longer retried on every run forever.
        self.write_spool("5000-1.json", "{not json")
        up = FakeSession()
        with self.assertLogs("etl.util.meter", level="WARNING") as logs:
            with self.meter(up) as m:
                m.event("pipeline.runs", 1)
        self.assertEqual(len(up.calls), 1)                                    # this run still reports
        self.assertNotIn("5000-1.json", os.listdir(self.spool))
        self.assertEqual(self.parked(), ["5000-1.json"])
        self.assertTrue(any("could not be read" in line for line in logs.output))

    def test_a_spool_write_failure_is_logged_as_usage_lost(self):
        # Not silent, but lost: the log line is the only trace of the batch.
        not_a_dir = os.path.join(self.spool, "file")
        open(not_a_dir, "w").close()
        down = FakeSession([requests.ConnectionError("x")] * 3)
        m = Meter(2600, 6000, "tok-6000", url="http://testserver", session=down, spool_dir=not_a_dir, clock=CLOCK)
        m.event("pipeline.runs", 1)
        with self.assertLogs("etl.util.meter", level="ERROR") as logs:
            m.close()
        self.assertTrue(any("usage lost" in line for line in logs.output))

    def test_a_400_or_401_refusal_is_final_not_retried_not_spooled(self):
        for status in (400, 401):
            refused = FakeSession([FakeResponse(status, {"detail": "no"})])
            with self.meter(refused) as m:
                m.event("pipeline.runs", 1)
            self.assertEqual(len(refused.calls), 1, status)
            self.assertEqual(self.spooled(), [], status)

    def test_a_refused_replay_deletes_the_spool_file(self):
        # By design (the docstring of _send_spooled): a run long over is refused and its file dropped.
        self.write_spool("6000-1.json", {"jobId": 2600, "jobQueueId": 6000, "token": "expired", "events": [{"dedupeKey": "k"}]})
        up = FakeSession([FakeResponse(401, {"detail": "refused"})])
        with self.meter(up, job_queue_id=6001, token="tok-6001") as m:
            pass
        self.assertEqual(self.spooled(), [])


# ---------------------------------------------------------------------------------------------
class MeterRejectionsAndDefectsTest(_SpoolCase):
    """
    MIG-200 -- what the client does with an answer it does not like, and where that loses usage or
    fails a job. Rule being measured: reporting never loses usage silently and is never a reason
    for a job to fail (etl/util/meter.py module docstring).
    """

    def test_rejected_events_are_parked_with_their_reasons(self):
        # MIG-200 / MIG-15: a 200 with rejected[] is not silent loss. The accepted events landed; each
        # rejected one is parked (dead/) with the meter's reason, and the log names it.
        answer = FakeResponse(200, {"accepted": 1, "duplicates": 0,
                                    "rejected": [{"index": 0, "reason": "unknown meter not.a.meter"}]})
        session = FakeSession([answer])
        with self.assertLogs("etl.util.meter", level="INFO") as logs:
            with self.meter(session) as m:
                m.event("not.a.meter", 3)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(self.spooled(), [])
        [parked] = self.parked()
        body = json.loads(self.parked_body(parked))
        self.assertEqual(body["jobQueueId"], 6000)
        self.assertEqual([(r["event"]["meter"], r["reason"]) for r in body["rejected"]], [("not.a.meter", "unknown meter not.a.meter")])
        self.assertTrue(any("not.a.meter" in line and "unknown meter" in line for line in logs.output), logs.output)

    def test_a_run_over_500_events_is_sent_in_batches_the_meter_accepts(self):
        # The service caps a batch at 500 (MAX_BATCH); the client sends at most that many at a time.
        store = MemoryStore()
        app = AppSession(TestClient(create_app(store=store, verify_run=verify, service_key="k")))
        with self.meter(app) as m:
            for _ in range(500):                                             # + worker_minutes = 501
                m.event("storage.ops.read", 1, unit="op")
        self.assertEqual(app.statuses, [200, 200])
        self.assertEqual(sum(1 for e in store.events if e["job_queue_id"] == 6000), 501)
        self.assertEqual(self.spooled(), [])

    def test_a_permanently_refused_spool_file_is_parked_and_never_starves_the_rest(self):
        # A 400/422 will not change its mind: the file is parked on the first refusal, so twenty such
        # files cost one run and every later file is sent.
        for i in range(20):
            self.write_spool(f"1{i:03d}-1.json", {"jobId": 1, "jobQueueId": 1000 + i, "token": "t", "events": [{"dedupeKey": f"p{i}"}]})
        self.write_spool("9000-2.json", {"jobId": 1, "jobQueueId": 9000, "token": "t", "events": [{"dedupeKey": "good"}]})
        poison = lambda url, body, headers: FakeResponse(422) if headers["X-Job-Queue-Id"] not in ("6000", "9000") else FakeResponse(200, {"accepted": 1})  # noqa: E731
        sent = []
        for _ in range(2):
            session = FakeSession([poison] * 22)
            with self.meter(session) as m:
                pass
            sent += [c["headers"]["X-Job-Queue-Id"] for c in session.calls]
        self.assertIn("9000", sent)
        self.assertEqual(len(self.parked()), 20)
        self.assertEqual(self.spooled(), [])

    def test_replay_follows_spool_time_not_the_file_name(self):
        # Run 999 spooled before run 1000, so it is replayed first, although "1000" sorts first as text.
        down = FakeSession([requests.ConnectionError("x")] * 7)          # 3 + (1 replay + 3)
        with self.meter(down, job_queue_id=999, token="tok-999") as m:
            m.event("pipeline.runs", 1)
        with self.meter(down, job_queue_id=1000, token="tok-1000") as m:
            m.event("pipeline.runs", 1)
        up = FakeSession()
        with self.meter(up, job_queue_id=1001, token="tok-1001") as m:
            pass
        self.assertEqual([c["headers"]["X-Job-Queue-Id"] for c in up.calls], ["999", "1000", "1001"])

    def test_a_spool_file_without_events_is_parked_and_the_run_still_reports(self):
        # A readable file that is not a batch (no events, or not an object) is parked, and it can no
        # longer fail a job that succeeded or cost this run its own report.
        for bad in ({"jobId": 1, "jobQueueId": 1}, []):
            shutil.rmtree(self.spool); os.makedirs(self.spool)
            self.write_spool("0001-1.json", bad)
            session = FakeSession()
            m = self.meter(session)
            m.event("pipeline.runs", 1)
            m.close()
            self.assertEqual(len(session.calls), 1)                          # this run's batch sent
            self.assertEqual(session.calls[0]["headers"]["X-Job-Queue-Id"], "6000")
            self.assertEqual(self.spooled(), [])
            self.assertEqual(self.parked(), ["0001-1.json"])


# ---------------------------------------------------------------------------------------------
class FakePost:
    """Stands in for requests.post in etl.util.job_state_client."""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": _copy(json), "headers": dict(headers or {}), "timeout": timeout})
        answer = self.answers.pop(0) if self.answers else FakeResponse(200, {"status": "SUCCESS"})
        if isinstance(answer, Exception):
            raise answer
        return answer


class JobStateLogBatchingTest(unittest.TestCase):
    """
    MIG-200 -- JobStateClient audit-log batching. Lines are buffered per run and sent in one
    request when 25 are waiting, or when a line arrives and the oldest has waited 5s, or on
    flush_logs(). Rule being measured: a flush failure must not lose lines silently.
    """

    def setUp(self):
        self._post, self._monotonic = jsc_module.requests.post, jsc_module.time.monotonic
        self.now = [1000.0]
        jsc_module.time.monotonic = lambda: self.now[0]
        self.client = jsc_module.JobStateClient("http://console/api")

    def tearDown(self):
        jsc_module.requests.post, jsc_module.time.monotonic = self._post, self._monotonic

    def use(self, fake):
        jsc_module.requests.post = fake
        return fake

    def test_twenty_five_lines_go_in_one_request_in_order(self):
        post = self.use(FakePost())
        for i in range(24):
            self.client.job_audit_log(1, 2, f"line {i}")
        self.assertEqual(post.calls, [])
        self.client.job_audit_log(1, 2, "line 24")
        self.assertEqual(len(post.calls), 1)
        self.assertEqual(post.calls[0]["url"], "http://console/api/addLogsBatch/jobId/1/jobQueueId/2")
        self.assertEqual(post.calls[0]["json"], {"messages": [f"line {i}" for i in range(25)]})
        self.assertEqual(post.calls[0]["timeout"], (5, 30))

    def test_the_age_cap_is_checked_only_when_a_line_arrives(self):
        post = self.use(FakePost())
        self.client.job_audit_log(1, 2, "first")
        self.now[0] += 60                              # a minute passes: no timer, nothing sent
        self.assertEqual(post.calls, [])
        self.client.job_audit_log(1, 2, "second")      # the next line trips the 5s cap
        self.assertEqual(post.calls[0]["json"]["messages"], ["first", "second"])

    def test_flush_sends_what_is_buffered_and_runs_are_kept_apart(self):
        post = self.use(FakePost())
        self.client.job_audit_log(1, 2, "a")
        self.client.job_audit_log(9, 8, "other run")
        self.client.job_audit_log(1, 2, "b")
        self.client.flush_logs(1, 2)
        self.client.flush_logs(1, 2)                   # nothing left: no second request
        self.assertEqual([(c["url"].rsplit("/", 4)[-3], c["json"]["messages"]) for c in post.calls], [("1", ["a", "b"])])
        self.client.flush_logs(9, 8)
        self.assertEqual(post.calls[-1]["json"]["messages"], ["other run"])

    def test_the_run_token_is_sent_with_a_batch(self):
        post = self.use(FakePost())
        self.client.remember_run_token(1, 2, "run-tok")
        self.client.job_audit_log(1, 2, "a")
        self.client.flush_logs(1, 2)
        self.assertEqual(post.calls[0]["headers"], {"X-Worker-Token": "run-tok"})

    def test_a_flush_that_raises_keeps_the_lines_for_the_next_send(self):
        post = self.use(FakePost([requests.ConnectionError("console down")]))
        self.client.job_audit_log(1, 2, "the line that explains the failure")
        with self.assertLogs("etl.util.job_state_client", level="ERROR"):
            self.client.flush_logs(1, 2)
        self.client.flush_logs(1, 2)                                                     # re-buffered, sent now
        self.assertEqual(len(post.calls), 2)
        self.assertEqual(post.calls[1]["json"]["messages"], ["the line that explains the failure"])

    def test_a_flush_answered_5xx_keeps_the_lines_for_the_next_send(self):
        post = self.use(FakePost([FakeResponse(500, {"error": "boom"})]))
        for i in range(3):
            self.client.job_audit_log(1, 2, f"l{i}")
        with self.assertLogs("etl.util.job_state_client", level="ERROR") as logs:
            self.client.flush_logs(1, 2)
        self.assertTrue(any("3 line(s) status=500" in line for line in logs.output), logs.output)
        self.client.flush_logs(1, 2)
        self.assertEqual(post.calls[1]["json"]["messages"], ["l0", "l1", "l2"])

    def test_a_batch_refused_401_is_dropped_and_not_raised_as_RunRefused(self):
        # Unlike change_job_state, which raises RunRefused on 401.
        self.use(FakePost([FakeResponse(401, {"message": "refused"})]))
        self.client.job_audit_log(1, 2, "x")
        with self.assertLogs("etl.util.job_state_client", level="ERROR"):
            self.client.flush_logs(1, 2)                   # no exception
        self.use(FakePost([FakeResponse(401, {"message": "refused"})]))
        with self.assertRaises(jsc_module.RunRefused):
            self.client.change_job_state(1, 2, "Completed", "done")

    def test_a_size_triggered_send_that_fails_keeps_its_lines_in_order(self):
        post = self.use(FakePost([requests.Timeout("slow")]))
        for i in range(25):
            self.client.job_audit_log(1, 2, f"l{i}")
        self.client.job_audit_log(1, 2, "after")
        self.client.flush_logs(1, 2)
        self.assertEqual(post.calls[1]["json"]["messages"], [f"l{i}" for i in range(25)] + ["after"])

    def test_lines_still_undelivered_when_a_run_ends_are_logged_in_full(self):
        # The run is over and the console never took them: the audit trail's last copy is the log.
        self.use(FakePost([requests.ConnectionError("down")] * 3))
        self.client.job_audit_log(1, 2, "the line that explains the failure")
        with self.assertLogs("etl.util.job_state_client", level="ERROR"):
            self.client.flush_logs(1, 2)
        with self.assertLogs("etl.util.job_state_client", level="ERROR") as logs:
            self.client.forget_run_token(1, 2)
        self.assertTrue(any("the line that explains the failure" in line for line in logs.output), logs.output)
        self.assertNotIn((1, 2), self.client._log_buffers)

    def test_a_run_buffers_no_more_than_its_cap_and_logs_what_it_let_go(self):
        post = self.use(FakePost([requests.ConnectionError("down")] * 10000))
        with self.assertLogs("etl.util.job_state_client", level="ERROR") as logs:
            for i in range(jsc_module.LOG_BUFFER_MAX + 30):
                self.client.job_audit_log(1, 2, f"line {i}")
            self.client.flush_logs(1, 2)
        self.assertLessEqual(len(self.client._log_buffers[(1, 2)]), jsc_module.LOG_BUFFER_MAX)
        self.assertTrue(any("line 0" in line for line in logs.output), "the oldest line let go is logged, not lost")
        # A down console is tried once, then left alone until the back-off ends; the final flush tries.
        self.assertEqual(len(post.calls), 2)

    def test_lines_on_one_client_are_never_sent_by_flushing_another(self):
        # Why every task module must log through the shared client the listener flushes (next test).
        post = self.use(FakePost())
        task_client = jsc_module.JobStateClient("http://console/api")
        task_client.job_audit_log(1, 2, "logged by the task module")
        self.client.flush_logs(1, 2)
        self.assertEqual(post.calls, [])
        self.assertEqual(task_client._log_buffers[(1, 2)], ["logged by the task module"])

    def test_task_modules_log_through_the_shared_client_the_listener_flushes(self):
        # tpd_scrapping_listener flushes the shared etl_helpers.job_state() client, so a task module
        # must log through that one: lines on a private client were never flushed (MIG-200). Source scan only -- importing the task modules
        # would build MinIO clients.
        found = set()
        for folder in ("etl",):
            for root, _, files in os.walk(os.path.join(REPO, folder)):
                for name in files:
                    if name.endswith(".py"):
                        path = os.path.join(root, name)
                        with open(path, encoding="utf-8") as handle:
                            if re.search(r"^\w+\s*=\s*JobStateClient\(", handle.read(), re.M):
                                found.add(os.path.relpath(path, REPO))
        self.assertEqual(found, {
            "etl/tpd/tpd_test_listener.py",   # builds and flushes its own, consistently
        })


if __name__ == "__main__":
    unittest.main()
