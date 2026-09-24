"""
    MIG-195: the reconciliation harness. A known-good period -- with an allowance boundary, a tier boundary,
    a manual line and a credit note -- reconciles; each class of corruption is caught and named; late usage
    is explained, not flagged; and the verdict does not move when the same usage arrives replayed or out
    of order. The rate card is the golden SEED_V1 fixture, with a workspace card over it.
"""
import io
import json
import os
import random
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from etl.meter.app import _priced_period
from etl.meter.reconcile import MemorySource, UNEXPLAINED, main, period_of, reconcile
from etl.meter.store import MemoryStore

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "rate_card_v1.json")
TENANT = 2905
START, END = period_of("2026-09")
BUILT = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)      # when the close built the invoice
TODAY = date(2026, 10, 3)


def golden_items():
    with open(FIXTURE) as f:
        return json.load(f)["items"]


def workspace_card(store):
    """The golden card with this workspace's own terms over it: an allowance on seats, tiers on model tokens."""
    items = []
    for item in golden_items():
        item = dict(item)
        if item["meter"] == "seats.user_days":
            item["included_quantity"] = "140"
        if item["meter"] == "ai.tokens.in":
            item["included_quantity"] = "1000"
            item["tiers"] = [{"from": 0, "unit_price": "0.05"}, {"from": 1500, "unit_price": "0.02"}]
        items.append(item)
    return store.save_rate_card(date(2026, 9, 1), "USD", items, name="MedAxis pilot", tenant_id=TENANT)


EVENTS = [
    # seats: exactly the allowance -- billable 0, the boundary itself
    ("seats.user_days", "70", 1), ("seats.user_days", "70", 2),
    # model tokens: 1000 included, then 1500 at 0.05, the rest at 0.02 -- crosses the tier boundary
    ("ai.tokens.in", "2000", 3), ("ai.tokens.in", "600.123456", 4),
    # bytes deleted: flat, per GiB
    ("storage.bytes.deleted", str(3 * 1024 ** 3), 5),
    # reads: used, and priced at 0 on this card -- a line that bills nothing
    ("storage.ops.read", "1204", 6),
]


def event(meter, quantity, day, key, received=None):
    at = datetime(2026, 9, day, 10, tzinfo=timezone.utc)
    return {"tenant_id": TENANT, "meter": meter, "quantity": Decimal(quantity), "unit": "x", "occurred_at": at,
            "received_at": received or at + timedelta(minutes=1), "source": "test", "subject_type": None, "subject_id": None,
            "actor_user_id": None, "job_queue_id": None, "dedupe_key": key, "note": None, "vouched_by": "service"}


def ledger(order=None, replay=False):
    store = MemoryStore()
    workspace_card(store)
    events = [event(m, q, d, f"k{i}") for i, (m, q, d) in enumerate(EVENTS)]
    if order is not None:
        events = order(events)
    store.insert_events(events)
    if replay:
        store.insert_events(list(reversed(events)))      # every event again: duplicates, not rows
    for day in range(1, 31):
        store.rollup(TENANT, date(2026, 9, day))
    return store


def invoice_as_drafted(store, tax_rate=Decimal("10")):
    """The month's invoice as process's BillingService.draft builds it from the meter's /v1/usage answer."""
    card = store.rate_card_for(START, TENANT)
    lines = []
    for row in _priced_period(store.usage(TENANT, START, END), card):
        if row["amount"] == 0 and row["quantity"] == 0:
            continue
        lines.append({"meter": row["meter"], "description": row["label"], "quantity": row["quantity"],
                      "included_quantity": row["includedQuantity"], "billable_quantity": row["billableQuantity"],
                      "amount": row["amount"], "manual": False})
    lines.append({"meter": None, "description": "Onboarding support", "quantity": Decimal("1"), "amount": Decimal("50.00000"), "manual": True})
    subtotal = sum((l["amount"] for l in lines), Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = (subtotal * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    credit = {"number": "CN-2026-09-0001", "total": Decimal("-5.00"),
              "lines": [{"meter": None, "description": "Credit against INV-2026-09-0001", "quantity": 1, "amount": Decimal("-5.00000"), "manual": True}]}
    return {"number": "INV-2026-09-0001", "status": "issued", "subtotal": subtotal, "tax_rate_percent": tax_rate, "tax": tax,
            "total": subtotal + tax, "snapshot_at": BUILT, "lines": lines, "credit_notes": [credit]}


def run(store, invoice):
    return reconcile(MemorySource(store, {(TENANT, START): invoice}), START, END, today=TODAY)


def row(report, meter):
    return next(r for r in report.rows if r.meter == meter)


def line(invoice, meter):
    return next(l for l in invoice["lines"] if l["meter"] == meter)


class KnownGoodTest(unittest.TestCase):

    def setUp(self):
        self.store = ledger()
        self.invoice = invoice_as_drafted(self.store)
        self.report = run(self.store, self.invoice)

    def test_a_clean_period_reconciles(self):
        self.assertTrue(self.report.ok, [x.as_dict() for x in self.report.unexplained])

    def test_the_allowance_boundary_bills_nothing_and_says_why(self):
        seats = row(self.report, "seats.user_days")
        self.assertEqual((seats.metered, seats.included, seats.billable, seats.priced), (Decimal("140"), Decimal("140"), Decimal("0"), Decimal("0.00000")))
        self.assertIn("the workspace's own card v2", seats.rules)

    def test_the_tier_boundary_is_banded_and_says_so(self):
        tokens = row(self.report, "ai.tokens.in")
        self.assertEqual(tokens.billable, Decimal("1600.123456"))
        # 1500 at 0.05 per 1000, then 100.123456 at 0.02 per 1000
        self.assertEqual(tokens.priced, (Decimal("1500") * Decimal("0.05") / 1000 + Decimal("100.123456") * Decimal("0.02") / 1000).quantize(Decimal("0.00001")))
        self.assertTrue(any(r.startswith("tiers:") for r in tokens.rules))
        self.assertTrue(any(r.startswith("allowance:") for r in tokens.rules))

    def test_the_invoice_explains_its_manual_line_rounding_and_credit_note(self):
        check = self.report.invoices[0]
        self.assertEqual(check.status, "explained")
        self.assertTrue(any(r.startswith("manual line: Onboarding support") for r in check.rules))
        self.assertIn("credit note CN-2026-09-0001: -5.00", check.rules)
        self.assertEqual(check.credited, Decimal("5.00"))

    def test_the_report_has_every_figure_per_meter(self):
        d = row(self.report, "storage.bytes.deleted").as_dict()
        for key in ("metered", "included", "billable", "priced", "lineQuantity", "lineAmount", "status", "rules"):
            self.assertIn(key, d)


class CorruptionTest(unittest.TestCase):
    """One class of corruption each; every one is UNEXPLAINED and says what it saw."""

    def setUp(self):
        self.store = ledger()
        self.invoice = invoice_as_drafted(self.store)

    def assertUnexplained(self, report, meter_or_invoice, words):
        self.assertFalse(report.ok)
        found = [p for x in report.unexplained for p in x.problems
                 if getattr(x, "meter", None) == meter_or_invoice or getattr(x, "number", None) == meter_or_invoice]
        self.assertTrue(any(words in p for p in found), found)

    def test_a_dropped_event(self):
        # In the ledger before the invoice was built, and not on it: lost, not late.
        self.store.insert_events([event("storage.bytes.deleted", str(1024 ** 3), 20, "dropped", received=BUILT - timedelta(days=5))])
        self.store.rollup(TENANT, date(2026, 9, 20))
        self.assertUnexplained(run(self.store, self.invoice), "storage.bytes.deleted", "line quantity")

    def test_a_duplicated_event(self):
        l = line(self.invoice, "storage.ops.read")
        l["quantity"] = l["quantity"] * 2
        self.assertUnexplained(run(self.store, self.invoice), "storage.ops.read", "line quantity")

    def test_a_wrong_meter_key(self):
        line(self.invoice, "ai.tokens.in")["meter"] = "ai.token.in"
        report = run(self.store, self.invoice)
        self.assertUnexplained(report, "ai.tokens.in", "no invoice line")
        self.assertUnexplained(report, "ai.token.in", "line quantity")

    def test_a_wrong_precision(self):
        l = line(self.invoice, "ai.tokens.in")
        l["quantity"] = l["quantity"].quantize(Decimal("0.00001"))            # 2600.123456 -> 2600.12346
        self.assertUnexplained(run(self.store, self.invoice), "ai.tokens.in", "line quantity")

    def test_a_line_priced_other_than_the_card_says(self):
        line(self.invoice, "storage.bytes.deleted")["amount"] += Decimal("0.00001")
        self.assertUnexplained(run(self.store, self.invoice), "storage.bytes.deleted", "line amount")

    def test_a_billable_quantity_that_ignores_the_allowance(self):
        seats = line(self.invoice, "seats.user_days")
        seats["billable_quantity"] = seats["quantity"]
        self.assertUnexplained(run(self.store, self.invoice), "seats.user_days", "line billable")

    def test_a_rollup_that_disagrees_with_the_ledger(self):
        key = next(k for k in self.store.daily if k[2] == "storage.ops.read")
        self.store.daily[key]["quantity"] += 1
        self.assertUnexplained(run(self.store, self.invoice), "storage.ops.read", "rollup")

    def test_a_subtotal_tax_or_total_that_does_not_follow_the_rounding_chain(self):
        # Each corrupted so the others still agree with it -- only its own check can catch it.
        for fields, words in ((("subtotal", "total"), "lines round to"), (("tax", "total"), "% of"), (("total",), "subtotal and tax make")):
            invoice = invoice_as_drafted(self.store)
            for field in fields:
                invoice[field] += Decimal("0.01")
            report = run(self.store, invoice)
            self.assertUnexplained(report, "INV-2026-09-0001", words)
            self.assertEqual(len(report.invoices[0].problems), 1, report.invoices[0].problems)

    def test_a_credit_note_whose_total_is_not_its_lines(self):
        self.invoice["credit_notes"][0]["total"] = Decimal("-6.00")
        self.assertUnexplained(run(self.store, self.invoice), "INV-2026-09-0001", "credit note")

    def test_usage_in_a_closed_month_with_no_invoice(self):
        report = reconcile(MemorySource(self.store, {}), START, END, today=TODAY)
        self.assertFalse(report.ok)
        self.assertIn("usage in a closed period and no invoice", report.invoices[0].problems)


class ExplainedTest(unittest.TestCase):

    def test_usage_received_after_the_invoice_was_built_is_late_not_lost(self):
        store = ledger()
        invoice = invoice_as_drafted(store)
        store.insert_events([event("storage.bytes.deleted", str(1024 ** 3), 30, "late", received=BUILT + timedelta(hours=3))])
        store.rollup(TENANT, date(2026, 9, 30))
        report = run(store, invoice)
        self.assertTrue(report.ok, [x.as_dict() for x in report.unexplained])
        deleted = row(report, "storage.bytes.deleted")
        self.assertEqual(deleted.late, Decimal(1024 ** 3))
        self.assertTrue(any(r.startswith("late:") for r in deleted.rules))

    def test_an_open_month_with_no_invoice_yet_is_explained(self):
        store = ledger()
        report = reconcile(MemorySource(store, {}), START, END, today=date(2026, 9, 20))
        self.assertTrue(report.ok)
        self.assertIn("the period is still open: no invoice yet", report.invoices[0].rules)


class StabilityTest(unittest.TestCase):

    def test_the_verdict_does_not_move_with_replayed_or_out_of_order_usage(self):
        baseline = run(ledger(), invoice_as_drafted(ledger()))
        expected = [(r.meter, r.metered, r.billable, r.priced, r.status) for r in baseline.rows]
        rng = random.Random(195)
        for attempt in range(25):
            store = ledger(order=lambda es: rng.sample(es, len(es)), replay=attempt % 2 == 0)
            report = run(store, invoice_as_drafted(store))
            self.assertTrue(report.ok, attempt)
            self.assertEqual([(r.meter, r.metered, r.billable, r.priced, r.status) for r in report.rows], expected, attempt)


class CommandTest(unittest.TestCase):

    def call(self, argv, invoices):
        out = io.StringIO()
        store = ledger()
        invoices = invoices(store)
        with redirect_stdout(out):
            code = main(argv, source_factory=lambda: MemorySource(store, invoices), today=TODAY)
        return code, out.getvalue()

    def test_zero_when_everything_reconciles(self):
        code, text = self.call(["--period", "2026-09"], lambda s: {(TENANT, START): invoice_as_drafted(s)})
        self.assertEqual(code, 0)
        self.assertIn("OK", text.splitlines()[0])
        self.assertIn("ai.tokens.in", text)

    def test_non_zero_on_anything_unexplained(self):
        def corrupt(store):
            invoice = invoice_as_drafted(store)
            invoice["total"] += 1
            return {(TENANT, START): invoice}
        code, text = self.call(["--period", "2026-09", "--json"], corrupt)
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(text)["ok"])
        self.assertIn(UNEXPLAINED, text)

    def test_a_bad_period_is_a_usage_error(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--period", "September"], source_factory=lambda: None), 2)


if __name__ == "__main__":
    unittest.main()
