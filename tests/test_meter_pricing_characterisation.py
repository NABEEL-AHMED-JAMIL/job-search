"""
    Characterisation tests for metering prices (MIG-142, MIG-143, MIG-144), written before the
    Java migration. They pin what the Python service does TODAY, so the rewrite can be held to
    the same answers. They change no behaviour.

    Fixtures shared with the Java side live in tests/fixtures/:
      rate_card_v1.json -- SEED_V1 as data (meter, unit, per, unit_price)
      meter_keys.json   -- the 18 meter keys, sorted
"""
import json
import os
import unittest
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

os.environ["METER_ROLLUP_SECONDS"] = "0"     # no background thread in the tests

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from etl.meter.app import create_app  # noqa: E402
from etl.meter.rates import BYTES_PER_GB, KNOWN_METERS, LABELS, SEED_V1, price, price_item  # noqa: E402
from etl.meter.store import MemoryStore  # noqa: E402

KEY = "test-service-key"
SVC = {"X-Service-Key": KEY}
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SEPT = {"start": "2026-09-01", "end": "2026-09-30"}


def refuse(job_id, job_queue_id, token):
    raise HTTPException(status_code=401, detail="no runs in these tests")


def client():
    store = MemoryStore()
    return TestClient(create_app(store=store, verify_run=refuse, service_key=KEY)), store


def D(value):
    """A JSON number back to a Decimal, through its shortest repr (FastAPI encodes Decimals as floats)."""
    return Decimal(str(value))


def post(c, *events):
    r = c.post("/v1/events", json={"events": list(events)}, headers=SVC)
    assert r.status_code == 200, r.text
    assert r.json()["rejected"] == [], r.json()
    return r.json()


def usage(c, tenant_id=None, group_by=None, **period):
    params = dict(SEPT, **period)
    if tenant_id is not None:
        params["tenantId"] = tenant_id
    if group_by is not None:
        params["groupBy"] = group_by
    r = c.get("/v1/usage", params=params, headers=SVC)
    assert r.status_code == 200, r.text
    return r.json()


def daily(c, store, tenant_id):
    """The usage_daily rows of September. The rollup of touched days runs on the next GET /v1/usage,
    so one is made first -- the store is read directly so no grouping is in the way."""
    usage(c, tenant_id, "day")
    return store.usage(tenant_id, date(2026, 9, 1), date(2026, 9, 30))


def put_card(c, **card):
    r = c.put("/v1/ratecard", json=card, headers=SVC)
    assert r.status_code == 200, r.text
    return r.json()


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------------------------
# MIG-142 (C6)
# ---------------------------------------------------------------------------------------------
class DailyAmountsAreNotPeriodAmountsTest(unittest.TestCase):
    """
    MIG-142 (C6) -- doc 06 section 13 rule 2: usage_daily.amount is a flat, before-allowance,
    before-tier daily price and is never the number billed for a period.

    The one place a period is priced is app._priced_period, reached ONLY by
    GET /v1/usage?groupBy=meter&tenantId=... It sums the daily QUANTITIES per meter and prices the
    sum with the card's item (allowance first, then graduated tiers). Every other reading --
    groupBy=day, groupBy=tenant, groupBy=meter without a tenantId, an unrecognised groupBy, and the
    usage_daily rows themselves -- folds the flat daily AMOUNTS, which are quantity x unit_price / per
    with the item's own unit_price, ignoring included_quantity and tiers.

    Scenario: seats.user_days, 10 per day on 3 days of September 2026. A card effective 2026-09-01
    gives 12 seats free and a tier from 10 billable at 0.10 (so an implicit first band 0..10 at the
    item's 0.33).
      daily:  10 x 0.33 = 3.30000 each, sum 9.90000
      period: 30 raw, 12 included, 18 billable -> 10 x 0.33 + 8 x 0.10 = 4.10000
    """

    TENANT = 2905

    def setUp(self):
        self.c, self.store = client()
        put_card(self.c, name="Seats with allowance", effective_from="2026-09-01", based_on_version=1, items=[
            {"meter": "seats.user_days", "unit": "user-day", "per": 1, "unit_price": 0.33, "included_quantity": 12,
             "tiers": [{"from": 10, "unit_price": 0.10}]}])
        post(self.c, *[{"tenantId": self.TENANT, "meter": "seats.user_days", "quantity": 10,
                        "occurredAt": f"2026-09-0{d}T02:00:00Z", "dedupeKey": f"seat-{d}"} for d in (3, 4, 5)])

    def test_period_by_meter_for_a_tenant_is_repriced_from_summed_quantity(self):
        row = usage(self.c, self.TENANT, "meter")["rows"][0]
        self.assertEqual(row["meter"], "seats.user_days")
        self.assertEqual(D(row["quantity"]), Decimal("30"))
        self.assertEqual(row["days"], 3)
        self.assertEqual(D(row["includedQuantity"]), Decimal("12"))
        self.assertEqual(D(row["billableQuantity"]), Decimal("18"))
        self.assertTrue(row["hasTiers"])
        self.assertEqual(D(row["amount"]), Decimal("4.10000"))

    def test_daily_rows_carry_the_flat_before_allowance_before_tier_price(self):
        rows = daily(self.c, self.store, self.TENANT)
        self.assertEqual([r["day"] for r in rows], [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 5)])
        for r in rows:
            self.assertEqual(r["amount"], Decimal("3.30000"))          # 10 x 0.33, no allowance, no tier
            self.assertEqual(r["unit_price"], Decimal("0.33"))
            self.assertEqual(r["rate_card_version"], 2)
            self.assertNotIn("included_quantity", r)

    def test_the_sum_of_daily_amounts_is_NOT_the_period_amount(self):
        daily_sum = sum(r["amount"] for r in daily(self.c, self.store, self.TENANT))
        period = D(usage(self.c, self.TENANT, "meter")["rows"][0]["amount"])
        self.assertEqual(daily_sum, Decimal("9.90000"))
        self.assertEqual(period, Decimal("4.10000"))
        self.assertNotEqual(daily_sum, period)     # summing daily amounts would over-bill by 5.80

    def test_group_by_day_folds_the_flat_daily_amounts(self):
        rows = usage(self.c, self.TENANT, "day")["rows"]
        self.assertEqual([D(r["amount"]) for r in rows], [Decimal("3.3")] * 3)
        self.assertEqual(sum(D(r["amount"]) for r in rows), Decimal("9.9"))
        self.assertEqual([D(r["byService"]["Seats"]) for r in rows], [Decimal("3.3")] * 3)

    def test_group_by_tenant_is_flat_even_with_a_tenant_id(self):
        # Pinned: the tenant total disagrees with the same tenant's by-meter total (9.90 vs 4.10).
        rows = usage(self.c, self.TENANT, "tenant")["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(D(rows[0]["amount"]), Decimal("9.9"))
        self.assertEqual(D(rows[0]["quantityByMeter"]["seats.user_days"]), Decimal("30"))
        self.assertNotEqual(D(rows[0]["amount"]), D(usage(self.c, self.TENANT, "meter")["rows"][0]["amount"]))

    def test_group_by_meter_without_a_tenant_is_flat_and_has_no_rate_card(self):
        answer = usage(self.c, None, "meter")
        self.assertNotIn("rateCard", answer)
        row = answer["rows"][0]
        self.assertEqual(D(row["amount"]), Decimal("9.9"))
        self.assertNotIn("includedQuantity", row)
        self.assertNotIn("billableQuantity", row)

    def test_an_unrecognised_group_by_falls_back_to_the_flat_meter_fold(self):
        # Pinned: a typo in groupBy is not an error; it answers the flat figure, not the bill.
        answer = usage(self.c, self.TENANT, "meters")
        self.assertEqual(answer["groupBy"], "meters")
        self.assertNotIn("rateCard", answer)
        self.assertEqual(D(answer["rows"][0]["amount"]), Decimal("9.9"))

    def test_the_daily_price_uses_the_items_unit_price_even_when_a_from_zero_tier_says_otherwise(self):
        # A first tier from 0 replaces the item's unit_price for the PERIOD, but the daily row still
        # uses the item's unit_price: the two can disagree even with no allowance at all.
        c, store = client()
        put_card(c, name="t", effective_from="2026-09-01", based_on_version=1, items=[
            {"meter": "pipeline.runs", "unit": "run", "per": 1, "unit_price": 0.002,
             "tiers": [{"from": 0, "unit_price": 0.001}]}])
        post(c, {"tenantId": 7, "meter": "pipeline.runs", "quantity": 100, "occurredAt": "2026-09-10T00:00:00Z", "dedupeKey": "r"})
        self.assertEqual(daily(c, store, 7)[0]["amount"], Decimal("0.20000"))
        self.assertEqual(D(usage(c, 7, "meter")["rows"][0]["amount"]), Decimal("0.1"))

    def test_the_allowance_is_applied_once_per_requested_range_not_per_calendar_month(self):
        # Pinned, and worth a decision before the rewrite: included_quantity is documented as
        # monthly, but _priced_period applies it once to whatever range was asked for, using the
        # card in effect on the first of the START month. A two-month range gets one allowance.
        post(self.c, {"tenantId": self.TENANT, "meter": "seats.user_days", "quantity": 10,
                      "occurredAt": "2026-10-02T02:00:00Z", "dedupeKey": "seat-oct"})
        row = usage(self.c, self.TENANT, "meter", start="2026-09-01", end="2026-10-31")["rows"][0]
        self.assertEqual(D(row["quantity"]), Decimal("40"))
        self.assertEqual(D(row["includedQuantity"]), Decimal("12"))     # not 24
        self.assertEqual(D(row["billableQuantity"]), Decimal("28"))
        self.assertEqual(D(row["amount"]), Decimal("5.1"))               # 10 x 0.33 + 18 x 0.10


# ---------------------------------------------------------------------------------------------
# MIG-143 (C6b)
# ---------------------------------------------------------------------------------------------
class AllowanceAndGraduatedTiersTest(unittest.TestCase):
    """
    MIG-143 (C6b) -- allowance, then graduated tiers, to five decimal places.

    Rules pinned:
      - included_quantity comes off first; tier boundaries are measured on the BILLABLE
        (post-allowance) quantity, never on the raw quantity;
      - graduated banding: each band's units at that band's own rate, never the whole quantity
        at the top band's rate;
      - when the first tier starts above 0 there is an implicit first band from 0 at the item's
        own unit_price;
      - the period total is rounded ONCE, to 5 places, after the bands are summed;
      - a tenant card WINS OUTRIGHT: it does not merge with the default card at pricing time, so a
        meter the default card prices and the tenant card omits prices as unknown (0, flagged
        unpriced) for that tenant -- it does not fall back to the default price;
      - an unknown meter's row is returned, never dropped and never guessed.

    Worked example (ai.tokens.in, per 1,000):
      item unit_price 0.0512, included 1,000, tiers [{from 2000: 0.0437}, {from 5000: 0.0291}]
      raw 8,123 -> billable 7,123
        band 0..2000     (implicit, item price)  2,000 x 0.0512 / 1000 = 0.1024
        band 2000..5000                          3,000 x 0.0437 / 1000 = 0.1311
        band 5000..                              2,123 x 0.0291 / 1000 = 0.0617793
        total 0.2952793 -> 0.29528
      Wrong answers it must NOT give:
        whole billable at top rate      7,123 x 0.0291 / 1000         = 0.20728
        boundaries on raw quantity      1,000 x 0.0512 + 3,000 x 0.0437 + 3,123 x 0.0291 (/1000) = 0.27318
    """

    ITEM = {"meter": "ai.tokens.in", "unit": "token", "per": 1000, "unit_price": "0.0512", "included_quantity": "1000",
            "tiers": [{"from": 2000, "unit_price": "0.0437"}, {"from": 5000, "unit_price": "0.0291"}]}

    def test_worked_example_to_five_places(self):
        amount, detail = price_item(8123, self.ITEM)
        self.assertEqual(amount, Decimal("0.29528"))
        self.assertEqual(amount.as_tuple().exponent, -5)
        self.assertEqual(detail["included"], Decimal("1000"))
        self.assertEqual(detail["billable"], Decimal("7123"))
        self.assertEqual([(b["from"], b["to"], b["units"], b["unit_price"]) for b in detail["tiers"]], [
            (Decimal("0"), Decimal("2000"), Decimal("2000"), Decimal("0.0512")),
            (Decimal("2000"), Decimal("5000"), Decimal("3000"), Decimal("0.0437")),
            (Decimal("5000"), None, Decimal("2123"), Decimal("0.0291")),
        ])

    def test_each_band_at_its_own_rate_never_the_whole_quantity_at_the_top_rate(self):
        amount, _ = price_item(8123, self.ITEM)
        whole_at_top = (Decimal("7123") * Decimal("0.0291") / 1000).quantize(Decimal("0.00001"))
        self.assertEqual(whole_at_top, Decimal("0.20728"))
        self.assertNotEqual(amount, whole_at_top)

    def test_tier_boundaries_are_measured_on_billable_not_raw_quantity(self):
        amount, detail = price_item(8123, self.ITEM)
        raw_boundaries = ((Decimal("1000") * Decimal("0.0512") + Decimal("3000") * Decimal("0.0437")
                           + Decimal("3123") * Decimal("0.0291")) / 1000).quantize(Decimal("0.00001"))
        self.assertEqual(raw_boundaries, Decimal("0.27318"))
        self.assertNotEqual(amount, raw_boundaries)
        # And the sharp case: raw crosses the 2,000 boundary, billable (1,500) does not -> one band only.
        amount, detail = price_item(2500, self.ITEM)
        self.assertEqual(detail["billable"], Decimal("1500"))
        self.assertEqual([(b["from"], b["units"]) for b in detail["tiers"]], [(Decimal("0"), Decimal("1500"))])
        self.assertEqual(amount, Decimal("0.07680"))                         # 1,500 x 0.0512 / 1000

    def test_implicit_first_band_at_the_items_own_price_only_when_the_first_tier_starts_above_zero(self):
        _, detail = price_item(3000, dict(self.ITEM, included_quantity="0"))
        self.assertEqual(detail["tiers"][0]["from"], Decimal("0"))
        self.assertEqual(detail["tiers"][0]["unit_price"], Decimal("0.0512"))   # the item's own price
        # With a tier from 0 there is no implicit band, and the item's unit_price plays no part.
        item = dict(self.ITEM, included_quantity="0", unit_price="99", tiers=[{"from": 0, "unit_price": "0.01"}, {"from": 100, "unit_price": "0.005"}])
        amount, detail = price_item(300, item)
        self.assertEqual([(b["from"], b["unit_price"]) for b in detail["tiers"]], [(Decimal("0"), Decimal("0.01")), (Decimal("100"), Decimal("0.005"))])
        self.assertEqual(amount, Decimal("0.00200"))                          # (100 x 0.01 + 200 x 0.005) / 1000

    def test_an_allowance_larger_than_the_usage_bills_nothing_and_no_band_is_listed(self):
        amount, detail = price_item(700, self.ITEM)
        self.assertEqual((amount, detail["billable"], detail["tiers"]), (Decimal("0.00000"), Decimal("0"), []))

    def test_the_period_is_rounded_once_after_summing_the_bands_not_per_band(self):
        # Each band alone is 0.000004 (rounds to 0.00000); together 0.000008 -> 0.00001.
        item = {"meter": "x", "unit": "u", "per": 1, "unit_price": "0.000002", "tiers": [{"from": 2, "unit_price": "0.000002"}]}
        amount, detail = price_item(4, item)
        self.assertEqual(len(detail["tiers"]), 2)
        self.assertEqual(amount, Decimal("0.00001"))

    def test_worked_example_through_the_service_across_days(self):
        c, store = client()
        put_card(c, name="Tiered tokens", effective_from="2026-09-01", based_on_version=1, items=[
            {"meter": "ai.tokens.in", "unit": "token", "per": 1000, "unit_price": 0.0512, "included_quantity": 1000,
             "tiers": [{"from": 2000, "unit_price": 0.0437}, {"from": 5000, "unit_price": 0.0291}]}])
        post(c, {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 3000, "occurredAt": "2026-09-02T10:00:00Z", "dedupeKey": "a"},
                {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 5123, "occurredAt": "2026-09-20T10:00:00Z", "dedupeKey": "b"})
        row = usage(c, 2905, "meter")["rows"][0]
        self.assertEqual(D(row["amount"]), Decimal("0.29528"))
        self.assertEqual(D(row["billableQuantity"]), Decimal("7123"))
        self.assertEqual([(D(t["units"]), D(t["unit_price"])) for t in row["tiers"]],
                         [(Decimal("2000"), Decimal("0.0512")), (Decimal("3000"), Decimal("0.0437")), (Decimal("2123"), Decimal("0.0291"))])
        self.assertIsNone(row["tiers"][-1]["to"])

    def test_a_tenant_card_wins_outright_and_an_omitted_meter_is_unpriced_not_the_default_price(self):
        c, store = client()
        for t in (2905, 2901):
            post(c, {"tenantId": t, "meter": "seats.user_days", "quantity": 10, "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": f"s{t}"},
                    {"tenantId": t, "meter": "pipeline.runs", "quantity": 5, "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": f"r{t}"})
        # The tenant's own card names ONLY pipeline.runs -- no based_on_version, so nothing is copied.
        card = put_card(c, name="Runs-only contract", effective_from="2026-09-01", tenant_id=2905,
                        items=[{"meter": "pipeline.runs", "unit": "run", "per": 1, "unit_price": 1.0}])
        self.assertEqual([i["meter"] for i in card["items"]], ["pipeline.runs"])

        mine = usage(c, 2905, "meter")
        self.assertTrue(mine["rateCard"]["tenantSpecific"])
        rows = {r["meter"]: r for r in mine["rows"]}
        self.assertEqual(set(rows), {"seats.user_days", "pipeline.runs"})          # the unknown row is not dropped
        self.assertEqual(D(rows["pipeline.runs"]["amount"]), Decimal("5"))
        seats = rows["seats.user_days"]
        self.assertEqual(D(seats["quantity"]), Decimal("10"))                      # quantity kept
        self.assertEqual(D(seats["amount"]), Decimal("0"))                         # not 3.30 from the default card
        self.assertEqual(D(seats["unitPrice"]), Decimal("0"))
        self.assertTrue(seats["unpriced"])
        self.assertEqual(D(seats["billableQuantity"]), Decimal("10"))
        # The daily row for it is kept too, at 0, with no unit guessed.
        rolled = {r["meter"]: r for r in daily(c, store, 2905)}
        self.assertEqual((rolled["seats.user_days"]["amount"], rolled["seats.user_days"]["unit"], rolled["seats.user_days"]["per"]),
                         (Decimal("0"), "", 1))
        # Another tenant stays on the default and is priced as before.
        theirs = {r["meter"]: r for r in usage(c, 2901, "meter")["rows"]}
        self.assertEqual(D(theirs["seats.user_days"]["amount"]), Decimal("3.3"))
        self.assertNotIn("unpriced", theirs["seats.user_days"])

    def test_a_tenant_card_based_on_the_default_is_a_snapshot_not_a_live_merge(self):
        c, store = client()
        post(c, {"tenantId": 2905, "meter": "ai.tokens.in", "quantity": 10000, "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": "t"})
        put_card(c, name="MedAxis", effective_from="2026-09-01", tenant_id=2905, based_on_version=1,
                 items=[{"meter": "seats.user_days", "unit": "user-day", "per": 1, "unit_price": 0.20}])
        # A later default card changes tokens; the tenant's card keeps the price it copied.
        put_card(c, name="Default v3", effective_from="2026-09-01", based_on_version=1,
                 items=[{"meter": "ai.tokens.in", "unit": "token", "per": 1000, "unit_price": 9.0}])
        row = usage(c, 2905, "meter")["rows"][0]
        self.assertEqual(D(row["amount"]), Decimal("0.5"))                          # 10,000 x 0.05 / 1000, not x 9.0
        self.assertEqual(usage(c, 2901, "meter")["rateCard"]["name"], "Default v3")


# ---------------------------------------------------------------------------------------------
# MIG-144 (C6c)
# ---------------------------------------------------------------------------------------------
class GoldenRateCardAndRoundingTest(unittest.TestCase):
    """
    MIG-144 (C6c) -- the golden rate card, rounding, and the byte meters.

    tests/fixtures/rate_card_v1.json is SEED_V1 as data; any change to the card is a fixture diff.

    Rounding: the Python side rounds ROUND_HALF_EVEN at 5 places (Decimal.quantize with the
    default decimal context -- the mode is implicit, not passed as rounding=). The Java side
    (invoice subtotal / tax) rounds HALF_UP at 2 places, deliberately: doc 06 section 11.4 rule 7.
    The two are different on purpose and must not be "harmonised" in the rewrite.

    Bytes are carried as raw bytes and priced per GB (per = 1073741824); storage.gb_hours is per 1.
    There is no minimum charge: a 40-byte write prices to 0.00000. storage.bytes.read is free
    (0.0) but its row is still kept in the usage answer.
    """

    def test_seed_v1_equals_the_golden_fixture(self):
        fixture = load_fixture("rate_card_v1.json")
        self.assertEqual(fixture["version"], 1)
        as_data = [{"meter": m, "unit": u, "per": p, "unit_price": up} for m, u, p, up in SEED_V1]
        self.assertEqual(as_data, fixture["items"])          # order included
        self.assertEqual(len(fixture["items"]), 18)

    def test_the_seeded_store_card_equals_the_golden_fixture(self):
        card = MemoryStore().rate_card(1)
        fixture = load_fixture("rate_card_v1.json")["items"]
        self.assertEqual([(i["meter"], i["unit"], i["per"], i["unit_price"]) for i in card["items"]],
                         [(i["meter"], i["unit"], i["per"], Decimal(i["unit_price"])) for i in fixture])
        self.assertTrue(all(i["included_quantity"] == 0 and i["tiers"] == [] for i in card["items"]))
        self.assertEqual((card["effective_from"], card["currency"], card["name"], card["tenant_id"]),
                         (date(2026, 1, 1), "USD", "Standard", None))

    def test_python_rounds_half_even_at_five_places(self):
        # Exact ties at the 6th place: HALF_EVEN goes to the even 5th digit, HALF_UP would go up.
        self.assertEqual(price(1, 1, "0.000005"), Decimal("0.00000"))      # HALF_UP: 0.00001
        self.assertEqual(price(1, 1, "0.000025"), Decimal("0.00002"))      # HALF_UP: 0.00003
        self.assertEqual(price(1, 1, "0.000015"), Decimal("0.00002"))      # same either way
        self.assertEqual(price(5, 1000, "0.001"), Decimal("0.00000"))      # 0.000005 via per
        item = {"meter": "x", "unit": "u", "per": 1, "unit_price": "0.000005"}
        self.assertEqual(price_item(1, item)[0], Decimal("0.00000"))
        self.assertEqual(price_item(5, dict(item, unit_price="0.000001", tiers=[{"from": 0, "unit_price": "0.000001"}]))[0],
                         Decimal("0.00000"))
        self.assertEqual(price(1, 1, "0.000005").as_tuple().exponent, -5)

    def test_the_half_even_mode_comes_from_the_ambient_decimal_context(self):
        # Pinned for the rewrite: nothing in rates.py names the rounding mode.
        with localcontext() as ctx:
            ctx.rounding = ROUND_HALF_UP
            self.assertEqual(price(1, 1, "0.000005"), Decimal("0.00001"))

    def test_a_40_byte_write_prices_to_zero_with_no_minimum_charge(self):
        self.assertEqual(price(40, BYTES_PER_GB, "0.01"), Decimal("0.00000"))
        c, store = client()
        post(c, {"tenantId": 2905, "meter": "storage.bytes.written", "quantity": 40, "unit": "byte",
                 "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": "w40"})
        day_row = daily(c, store, 2905)[0]
        self.assertEqual((day_row["quantity"], day_row["amount"]), (Decimal("40"), Decimal("0.00000")))
        row = usage(c, 2905, "meter")["rows"][0]
        self.assertEqual((row["meter"], D(row["quantity"]), D(row["amount"])), ("storage.bytes.written", Decimal("40"), Decimal("0")))

    def test_bytes_read_is_free_and_its_row_is_kept(self):
        self.assertEqual(price(5 * BYTES_PER_GB, BYTES_PER_GB, "0.0"), Decimal("0.00000"))
        c, store = client()
        post(c, {"tenantId": 2905, "meter": "storage.bytes.read", "quantity": 5 * BYTES_PER_GB, "unit": "byte",
                 "occurredAt": "2026-09-05T02:00:00Z", "dedupeKey": "r5"})
        for group_by in ("meter", "bogus"):
            rows = usage(c, 2905, group_by)["rows"]
            self.assertEqual(len(rows), 1, group_by)
            self.assertEqual(rows[0]["meter"], "storage.bytes.read")
            self.assertGreater(D(rows[0]["quantity"]), 0)
            self.assertEqual(D(rows[0]["amount"]), Decimal("0"))
        self.assertNotIn("unpriced", usage(c, 2905, "meter")["rows"][0])      # priced at 0, not unknown

    def test_byte_meters_are_raw_bytes_priced_per_gb_and_gb_hours_is_per_one(self):
        per = {m: (u, p) for m, u, p, _ in SEED_V1}
        self.assertEqual(BYTES_PER_GB, 1073741824)
        for meter in ("storage.bytes.written", "storage.bytes.deleted", "storage.bytes.read"):
            self.assertEqual(per[meter], ("byte", 1073741824), meter)
        self.assertEqual(per["storage.gb_hours"], ("GB-hour", 1))
        self.assertEqual(price(BYTES_PER_GB, BYTES_PER_GB, "0.01"), Decimal("0.01000"))   # one GB written = one cent


class MeterVocabularyTest(unittest.TestCase):
    """
    MIG-144 (C6c) -- the meter vocabulary: tests/fixtures/meter_keys.json lists the 18 meter keys
    (sorted). KNOWN_METERS is exactly that set and LABELS names every one. The Java side reads the
    same file.
    """

    def test_known_meters_equal_the_fixture(self):
        keys = load_fixture("meter_keys.json")
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), 18)
        self.assertEqual(len(set(keys)), 18)
        self.assertEqual(KNOWN_METERS, frozenset(keys))
        self.assertEqual(sorted(m for m, *_ in SEED_V1), keys)

    def test_labels_cover_every_key(self):
        keys = load_fixture("meter_keys.json")
        for key in keys:
            self.assertIn(key, LABELS, key)
            label, service = LABELS[key]
            self.assertTrue(label and service, key)
        self.assertEqual(set(LABELS), set(keys))            # and nothing extra


if __name__ == "__main__":
    unittest.main()
