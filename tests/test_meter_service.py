"""
    The metering service's contract: what a pipeline may report and as whom, that a repeated
    event is a duplicate and never a second row, and that the rollup prices with the card that
    was current for the day.
"""
import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

os.environ["METER_ROLLUP_SECONDS"] = "0"     # no background thread in the tests

from fastapi.testclient import TestClient  # noqa: E402

from etl.meter.app import create_app  # noqa: E402
from etl.meter.rates import price  # noqa: E402
from etl.meter.store import MemoryStore  # noqa: E402

KEY = "test-service-key"


def verify(job_id, job_queue_id, token):
    """The console's verdict, faked: run 6000 of job 2600 belongs to tenant 2905 with token 'tok-6000'."""
    from fastapi import HTTPException
    if (job_id, job_queue_id, token) == (2600, 6000, "tok-6000"):
        return 2905
    raise HTTPException(status_code=401, detail="refused")


def client():
    store = MemoryStore()
    return TestClient(create_app(store=store, verify_run=verify, service_key=KEY)), store


RUN = {"X-Worker-Token": "tok-6000", "X-Job-Id": "2600", "X-Job-Queue-Id": "6000"}
SVC = {"X-Service-Key": KEY}


class MeterServiceTest(unittest.TestCase):

    def test_a_run_reports_as_its_own_workspace_whatever_it_claims(self):
        c, store = client()
        r = c.post("/v1/events", json={"events": [
            {"tenantId": 9999, "meter": "storage.bytes.deleted", "quantity": 0.5, "unit": "GB", "dedupeKey": "6000#storage.bytes.deleted#1"},
            {"meter": "storage.ops.delete", "quantity": 3, "dedupeKey": "6000#storage.ops.delete#1"},
        ]}, headers=RUN)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"accepted": 2, "duplicates": 0, "rejected": []})
        self.assertEqual({e["tenant_id"] for e in store.events}, {2905})
        self.assertEqual({e["job_queue_id"] for e in store.events}, {6000})
        self.assertEqual({e["vouched_by"] for e in store.events}, {"run"})

    def test_a_refused_token_reports_nothing(self):
        c, store = client()
        r = c.post("/v1/events", json={"events": [{"meter": "pipeline.runs", "quantity": 1, "dedupeKey": "x"}]},
                   headers={"X-Worker-Token": "wrong", "X-Job-Id": "2600", "X-Job-Queue-Id": "6000"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(store.events, [])
        # And a token without the run it belongs to is a bad request, not a guess.
        r = c.post("/v1/events", json={"events": []}, headers={"X-Worker-Token": "tok-6000"})
        self.assertEqual(r.status_code, 400)

    def test_a_service_names_the_tenant_and_must_have_the_key(self):
        c, store = client()
        r = c.post("/v1/events", json={"events": [
            {"tenantId": 2901, "meter": "ai.tokens.in", "quantity": 1240, "unit": "token", "source": "runner",
             "subjectType": "prompt", "subjectId": "abc", "actorUserId": 7, "dedupeKey": "run#77#in"},
            {"meter": "ai.tokens.out", "quantity": 80, "dedupeKey": "run#77#out"},
            {"tenantId": 2901, "meter": "not.a.meter", "quantity": 1, "dedupeKey": "run#77#x"},
            {"tenantId": 2901, "meter": "pipeline.runs", "quantity": 0, "dedupeKey": "run#77#z"},
        ]}, headers=SVC)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["accepted"], 1)
        self.assertEqual([x["reason"] for x in body["rejected"]], ["tenantId is required", "unknown meter not.a.meter", "quantity is 0"])
        self.assertEqual(store.events[0]["vouched_by"], "service")
        self.assertEqual(c.post("/v1/events", json={"events": []}, headers={"X-Service-Key": "nope"}).status_code, 401)
        self.assertEqual(c.post("/v1/events", json={"events": []}).status_code, 401)

    def test_a_repeated_event_is_a_duplicate_and_the_totals_do_not_move(self):
        c, store = client()
        batch = {"events": [{"tenantId": 2905, "meter": "storage.bytes.written", "quantity": 2.5, "unit": "GB", "dedupeKey": "6000#w#1"}]}
        self.assertEqual(c.post("/v1/events", json=batch, headers=SVC).json()["accepted"], 1)
        again = c.post("/v1/events", json=batch, headers=SVC).json()
        self.assertEqual((again["accepted"], again["duplicates"]), (0, 1))
        self.assertEqual(len(store.events), 1)
        usage = c.get("/v1/usage", params={"tenantId": 2905, "start": "2020-01-01", "end": "2099-12-31"}, headers=SVC).json()
        self.assertEqual(len(usage["rows"]), 1)
        self.assertEqual(Decimal(str(usage["rows"][0]["quantity"])), Decimal("2.5"))

    def test_the_rollup_prices_with_the_card_of_the_period_and_groups_as_asked(self):
        c, store = client()
        day = "2026-09-18T10:00:00Z"
        c.post("/v1/events", json={"events": [
            {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 42100, "occurredAt": day, "dedupeKey": "a"},
            {"tenantId": 2905, "meter": "ai.tokens.out", "quantity": 8200, "occurredAt": day, "dedupeKey": "b"},
            {"tenantId": 2905, "meter": "storage.bytes.deleted", "quantity": 38.2 * 1024 ** 3, "occurredAt": day, "dedupeKey": "c"},
            {"tenantId": 2905, "meter": "storage.ops.delete", "quantity": 1204, "occurredAt": day, "dedupeKey": "d"},
            {"tenantId": 2905, "meter": "seats.user_days", "quantity": 14, "occurredAt": "2026-09-17T02:00:00Z", "dedupeKey": "e"},
        ]}, headers=SVC)
        answer = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()
        by_meter = answer["rows"]
        self.assertEqual(answer["rateCard"], {"version": 1, "name": "Standard", "currency": "USD", "tenantSpecific": False, "effectiveFrom": "2026-01-01"})
        amounts = {r["meter"]: Decimal(str(r["amount"])) for r in by_meter}
        self.assertEqual(amounts["ai.tokens.in"], price(42100, 1000, "0.05"))          # 2.105
        self.assertEqual(amounts["ai.tokens.out"], price(8200, 1000, "0.15"))          # 1.23
        self.assertEqual(amounts["storage.bytes.deleted"], Decimal("0.38200"))
        self.assertEqual(amounts["storage.ops.delete"], Decimal("0.00602"))
        self.assertEqual(amounts["seats.user_days"], Decimal("4.62000"))
        self.assertEqual(by_meter[0]["service"], "Seats")                               # largest first
        by_day = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30", "groupBy": "day"}, headers=SVC).json()["rows"]
        self.assertEqual([r["day"] for r in by_day], ["2026-09-17", "2026-09-18"])
        self.assertEqual(set(by_day[1]["byService"]), {"Model calls", "Storage"})

        # A change to one price is a one-item request; the rest carries over from the card edited.
        r = c.put("/v1/ratecard", json={"name": "Standard, churn free", "effective_from": "2026-09-01", "based_on_version": 1,
                                        "items": [{"meter": "storage.bytes.deleted", "unit": "byte", "per": 1073741824, "unit_price": 0.0}]}, headers=SVC)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["version"], 2)
        self.assertEqual(len(r.json()["items"]), 18)
        answer = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()
        amounts = {r["meter"]: Decimal(str(r["amount"])) for r in answer["rows"]}
        self.assertEqual(answer["rateCard"]["version"], 2)
        self.assertEqual(amounts["storage.bytes.deleted"], Decimal("0"))
        self.assertEqual(amounts["ai.tokens.in"], price(42100, 1000, "0.05"))          # carried over, still priced
        # A card dated next month does not touch this month: a change applies from the next bill.
        c.put("/v1/ratecard", json={"name": "October", "effective_from": "2026-10-01", "based_on_version": 2,
                                    "items": [{"meter": "ai.tokens.in", "unit": "token", "per": 1000, "unit_price": 9.0}]}, headers=SVC)
        answer = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()
        self.assertEqual(answer["rateCard"]["version"], 2)
        self.assertEqual(c.put("/v1/ratecard", json={"name": "x", "effective_from": "2026-10-01", "items": [{"meter": "bogus", "unit": "x", "unit_price": 1}]}, headers=SVC).status_code, 400)
        self.assertEqual(c.put("/v1/ratecard", json={"name": "x", "effective_from": "2026-10-01", "items": [{"meter": "seats.user_days", "unit": "user-day", "unit_price": -1}]}, headers=SVC).status_code, 400)

    def test_a_workspace_can_have_its_own_card_and_the_rest_stay_on_the_default(self):
        c, store = client()
        for t in (2905, 2901):
            c.post("/v1/events", json={"events": [{"tenantId": t, "meter": "seats.user_days", "quantity": 10, "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": f"s{t}"}]}, headers=SVC)
        r = c.put("/v1/ratecard", json={"name": "MedAxis contract", "effective_from": "2026-09-01", "tenant_id": 2905, "based_on_version": 1, "note": "seats at 0.20",
                                        "items": [{"meter": "seats.user_days", "unit": "user-day", "per": 1, "unit_price": 0.20}]}, headers=SVC)
        self.assertEqual(r.status_code, 200, r.text)
        mine = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()
        theirs = c.get("/v1/usage", params={"tenantId": 2901, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()
        self.assertEqual((mine["rateCard"]["name"], mine["rateCard"]["tenantSpecific"]), ("MedAxis contract", True))
        self.assertEqual((theirs["rateCard"]["name"], theirs["rateCard"]["tenantSpecific"]), ("Standard", False))
        self.assertEqual(Decimal(str(mine["rows"][0]["amount"])), Decimal("2.00000"))
        self.assertEqual(Decimal(str(theirs["rows"][0]["amount"])), Decimal("3.30000"))
        # the list names every version, newest first, with who it is for
        cards = c.get("/v1/ratecards", headers=SVC).json()["cards"]
        self.assertEqual([(x["version"], x["name"], x["tenant_id"]) for x in cards], [(2, "MedAxis contract", 2905), (1, "Standard", None)])
        # ?tenantId answers the card in effect for that workspace
        self.assertEqual(c.get("/v1/ratecard", params={"tenantId": 2905}, headers=SVC).json()["version"], 2)
        self.assertEqual(c.get("/v1/ratecard", params={"tenantId": 2901}, headers=SVC).json()["version"], 1)

    def test_an_allowance_and_tiers_price_a_period_not_a_day(self):
        c, store = client()
        # 3,000 model tokens on two days; the card gives 1,000 free, then 0.05/1k up to 1,500 billable, 0.02/1k above.
        c.post("/v1/events", json={"events": [
            {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 1000, "occurredAt": "2026-09-03T10:00:00Z", "dedupeKey": "t1"},
            {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 2000, "occurredAt": "2026-09-04T10:00:00Z", "dedupeKey": "t2"},
        ]}, headers=SVC)
        r = c.put("/v1/ratecard", json={"name": "Tiered", "effective_from": "2026-09-01", "based_on_version": 1, "items": [
            {"meter": "ai.tokens.in", "unit": "token", "per": 1000, "unit_price": 0.05, "included_quantity": 1000,
             "tiers": [{"from": 0, "unit_price": 0.05}, {"from": 1500, "unit_price": 0.02}]}]}, headers=SVC)
        self.assertEqual(r.status_code, 200, r.text)
        row = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC).json()["rows"][0]
        self.assertEqual(Decimal(str(row["quantity"])), Decimal("3000"))
        self.assertEqual(Decimal(str(row["includedQuantity"])), Decimal("1000"))
        self.assertEqual(Decimal(str(row["billableQuantity"])), Decimal("2000"))
        # 1,500 at 0.05/1k = 0.075, then 500 at 0.02/1k = 0.01
        self.assertEqual(Decimal(str(row["amount"])), Decimal("0.08500"))
        self.assertEqual([(Decimal(str(t["units"])), Decimal(str(t["unit_price"]))) for t in row["tiers"]], [(Decimal("1500"), Decimal("0.05")), (Decimal("500"), Decimal("0.02"))])
        # By day the figures are flat, before the allowance -- the chart's shape, not the bill.
        by_day = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30", "groupBy": "day"}, headers=SVC).json()["rows"]
        self.assertEqual([Decimal(str(d["amount"])) for d in by_day], [Decimal("0.05"), Decimal("0.10")])

    def test_subjects_and_events_are_the_drill_down(self):
        c, store = client()
        c.post("/v1/events", json={"events": [
            {"tenantId": 2905, "meter": "storage.bytes.deleted", "quantity": 1.0, "subjectType": "bucket", "subjectId": "medaxis-care-network", "actorUserId": 4385, "dedupeKey": "1"},
            {"tenantId": 2905, "meter": "storage.bytes.deleted", "quantity": 2.0, "subjectType": "bucket", "subjectId": "medaxis-care-network", "actorUserId": 4385, "dedupeKey": "2"},
            {"tenantId": 2905, "meter": "storage.bytes.deleted", "quantity": 0.5, "subjectType": "bucket", "subjectId": "worker-store", "dedupeKey": "3"},
            {"tenantId": 2901, "meter": "storage.bytes.deleted", "quantity": 9.0, "subjectType": "bucket", "subjectId": "carebridge", "dedupeKey": "4"},
        ]}, headers=SVC)
        subjects = c.get("/v1/usage/subjects", params={"tenantId": 2905, "meter": "storage.bytes.deleted", "start": "2020-01-01", "end": "2099-01-01"}, headers=SVC).json()
        self.assertEqual([(r["subject_id"], Decimal(str(r["quantity"])), r["events"]) for r in subjects["rows"]],
                         [("medaxis-care-network", Decimal("3.0"), 2), ("worker-store", Decimal("0.5"), 1)])
        self.assertEqual(subjects["rows"][0]["actor_user_id"], 4385)
        events = c.get("/v1/usage/events", params={"tenantId": 2905, "meter": "storage.bytes.deleted", "limit": 2}, headers=SVC).json()
        self.assertEqual((events["total"], len(events["rows"])), (3, 2))
        # A pipeline cannot read the ledger.
        self.assertEqual(c.get("/v1/usage", params={"tenantId": 2905, "start": "2020-01-01", "end": "2099-01-01"}, headers=RUN).status_code, 401)

    def test_health_says_what_it_holds(self):
        c, _ = client()
        h = c.get("/health").json()
        self.assertEqual((h["status"], h["store"], h["events"]), ("ok", "MemoryStore", 0))


if __name__ == "__main__":
    unittest.main()
