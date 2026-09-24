"""
    MIG-190: the usage-reporting contract (etl/meter/CONTRACT.md), one test per clause. The part a split
    puts most at risk is who may report as whom -- it decides which workspace a usage event bills.
"""
import os
import unittest
from unittest import mock

os.environ["METER_ROLLUP_SECONDS"] = "0"     # no background thread in the tests

from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from etl.meter import app as meter_app  # noqa: E402
from etl.meter.app import MAX_BATCH, create_app, key_matches  # noqa: E402
from etl.meter.store import MemoryStore  # noqa: E402

KEY = "test-service-key"
SVC = {"X-Service-Key": KEY}
RUN = {"X-Worker-Token": "tok-6000", "X-Job-Id": "2600", "X-Job-Queue-Id": "6000"}


def verify(job_id, job_queue_id, token):
    """The console's verdict, faked: run 6000 of job 2600 belongs to tenant 2905 with token 'tok-6000'."""
    from fastapi import HTTPException
    if (job_id, job_queue_id, token) == (2600, 6000, "tok-6000"):
        return 2905
    raise HTTPException(status_code=401, detail="refused")


def client(service_key=KEY):
    store = MemoryStore()
    return TestClient(create_app(store=store, verify_run=verify, service_key=service_key)), store


def event(**over):
    e = {"meter": "pipeline.runs", "quantity": 1, "dedupeKey": "k-" + str(len(over))}
    e.update(over)
    return e


class ReportingContractTest(unittest.TestCase):

    # -- 1. a service names any tenant; a run reports only as its own workspace ----------------

    def test_a_run_token_cannot_report_for_another_tenant_or_another_run(self):
        c, store = client()
        r = c.post("/v1/events", json={"events": [event(tenantId=2901, jobQueueId=9999, dedupeKey="r1")]}, headers=RUN)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((store.events[0]["tenant_id"], store.events[0]["job_queue_id"]), (2905, 6000))

    def test_a_service_names_any_tenant(self):
        c, store = client()
        c.post("/v1/events", json={"events": [event(tenantId=2901, dedupeKey="s1"), event(tenantId=2905, dedupeKey="s2")]}, headers=SVC)
        self.assertEqual([e["tenant_id"] for e in store.events], [2901, 2905])

    def test_every_row_says_forever_which_kind_of_caller_vouched_for_it(self):
        c, store = client()
        c.post("/v1/events", json={"events": [event(tenantId=2901, dedupeKey="v1")]}, headers=SVC)
        c.post("/v1/events", json={"events": [event(dedupeKey="v2")]}, headers=RUN)
        self.assertEqual([e["vouched_by"] for e in store.events], ["service", "run"])

    # -- 2. who is refused, and how ------------------------------------------------------------

    def test_neither_credential_is_a_401_and_a_token_without_its_run_is_a_400(self):
        c, _ = client()
        self.assertEqual(c.post("/v1/events", json={"events": []}).status_code, 401)
        self.assertEqual(c.post("/v1/events", json={"events": []}, headers={"X-Worker-Token": "tok-6000"}).status_code, 400)
        self.assertEqual(c.post("/v1/events", json={"events": []}, headers={**RUN, "X-Worker-Token": "wrong"}).status_code, 401)

    def test_a_run_token_can_write_but_never_read_never_roll_up_and_never_set_a_card(self):
        c, _ = client()
        for method, path, extra in (("get", "/v1/usage", {"params": {"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}}),
                                    ("get", "/v1/usage/subjects", {"params": {"tenantId": 2905, "meter": "pipeline.runs", "start": "2026-09-01", "end": "2026-09-30"}}),
                                    ("get", "/v1/usage/events", {"params": {"tenantId": 2905}}),
                                    ("get", "/v1/ratecard", {}), ("get", "/v1/ratecards", {}),
                                    ("post", "/v1/rollup", {}),
                                    ("put", "/v1/ratecard", {"json": {"name": "x", "effective_from": "2026-10-01", "items": []}})):
            r = getattr(c, method)(path, headers=RUN, **extra)
            self.assertEqual(r.status_code, 401, f"{method.upper()} {path} answered {r.status_code} to a run token")

    def test_an_empty_configured_key_refuses_everything(self):
        c, store = client(service_key="")
        for sent in ("", " ", "anything"):
            self.assertEqual(c.post("/v1/events", json={"events": [event(tenantId=2905)]}, headers={"X-Service-Key": sent}).status_code, 401)
            self.assertEqual(c.get("/v1/ratecard", headers={"X-Service-Key": sent}).status_code, 401)
        self.assertEqual(store.events, [])
        self.assertFalse(key_matches("", ""))

    def test_the_key_is_compared_in_constant_time(self):
        with mock.patch.object(meter_app.hmac, "compare_digest", wraps=meter_app.hmac.compare_digest) as compared:
            self.assertTrue(key_matches(KEY, KEY))
            self.assertFalse(key_matches("nope", KEY))
        self.assertEqual(compared.call_count, 2)

    # -- 3. batch size ---------------------------------------------------------------------------

    def test_a_batch_past_the_limit_is_a_422_and_nothing_of_it_is_kept(self):
        c, store = client()
        self.assertEqual(MAX_BATCH, 500)
        at_limit = [event(tenantId=2905, dedupeKey=f"b{i}") for i in range(MAX_BATCH)]
        self.assertEqual(c.post("/v1/events", json={"events": at_limit}, headers=SVC).status_code, 200)
        over = [event(tenantId=2905, dedupeKey=f"o{i}") for i in range(MAX_BATCH + 1)]
        self.assertEqual(c.post("/v1/events", json={"events": over}, headers=SVC).status_code, 422)
        self.assertEqual(len(store.events), MAX_BATCH)

    def test_a_dedupe_key_past_200_characters_is_a_422(self):
        # The Java reporter parks such an event before sending it (MeterReporterTest), so it never takes its batch down.
        c, _ = client()
        self.assertEqual(c.post("/v1/events", json={"events": [event(tenantId=2905, dedupeKey="x" * 201)]}, headers=SVC).status_code, 422)

    # -- 4. the open surface -------------------------------------------------------------------

    def test_health_is_the_only_route_that_answers_without_a_credential(self):
        app = create_app(store=MemoryStore(), verify_run=verify, service_key=KEY)
        open_routes = []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                open_routes.append(getattr(route, "path", repr(route)))
                continue
            guards = {d.call.__name__ for d in route.dependant.dependencies if d.call is not None}
            if not guards & {"caller", "reader"}:
                open_routes.append(route.path)
        self.assertEqual(open_routes, ["/health"])

    def test_no_generated_docs_are_served(self):
        c, _ = client()
        for path in ("/docs", "/redoc", "/openapi.json"):
            self.assertEqual(c.get(path).status_code, 404, path)


if __name__ == "__main__":
    unittest.main()
