"""
    MIG-197: what the ledger holds leaves the meter as exactly that number. FastAPI's default encoder
    turns a Decimal into a float, and a float keeps 15 to 17 significant digits, so a month's quantity
    at the ledger's full scale (numeric(24,6)) -- 123456789012.123456 -- arrived as 123456789012.12346:
    a digit lost on its way to the invoice, and at an allowance or tier boundary a digit that moves a
    quantity across the band. Numbers stay JSON numbers (the console and process read them as such),
    written with every digit the Decimal has.
"""
import json
import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

os.environ["METER_ROLLUP_SECONDS"] = "0"     # no background thread in the tests

from fastapi.testclient import TestClient  # noqa: E402

from etl.meter.app import create_app, exact_json  # noqa: E402
from etl.meter.store import MemoryStore  # noqa: E402

KEY = "test-service-key"
SVC = {"X-Service-Key": KEY}
FULL = Decimal("123456789012.123456")


def exact(text):
    return json.loads(text, parse_float=Decimal)


class ExactNumbersTest(unittest.TestCase):

    def test_a_full_scale_quantity_leaves_the_meter_with_every_digit(self):
        store = MemoryStore()
        c = TestClient(create_app(store=store, verify_run=None, service_key=KEY))
        # Straight into the ledger at full scale -- the value a month of sums reaches, not one event.
        store.events.append({"tenant_id": 2905, "meter": "storage.bytes.read", "quantity": FULL, "unit": "byte",
                             "occurred_at": datetime(2026, 9, 18, 10, tzinfo=timezone.utc),
                             "source": "console", "subject_type": None, "subject_id": None, "actor_user_id": None,
                             "job_queue_id": None, "dedupe_key": "full", "note": None, "vouched_by": "service"})
        store.rollup(2905, date(2026, 9, 18))

        r = c.get("/v1/usage", params={"tenantId": 2905, "start": "2026-09-01", "end": "2026-09-30"}, headers=SVC)

        self.assertEqual(r.status_code, 200, r.text)
        row = next(x for x in exact(r.text)["rows"] if x["meter"] == "storage.bytes.read")
        self.assertEqual(row["quantity"], FULL)
        self.assertEqual(row["billableQuantity"], FULL)
        self.assertIn("123456789012.123456", r.text)
        # Still a number, not a string: the console and process read these as numbers.
        self.assertIsInstance(r.json()["rows"][0]["quantity"], (int, float))

    def test_prices_and_amounts_keep_their_digits_too(self):
        body = exact_json({"unit_price": Decimal("0.00003200"), "amount": Decimal("0.00602"), "big": Decimal("1E+3"),
                           "neg": Decimal("-4.5"), "n": 3, "f": 0.5, "s": "0.1", "none": None, "ok": True, "list": [Decimal("7.000001")]})
        parsed = exact(body)
        self.assertEqual(parsed["unit_price"], Decimal("0.00003200"))
        self.assertEqual(parsed["amount"], Decimal("0.00602"))
        self.assertEqual(parsed["big"], Decimal("1000"))
        self.assertEqual(parsed["neg"], Decimal("-4.5"))
        self.assertEqual(parsed["list"], [Decimal("7.000001")])
        self.assertEqual((parsed["n"], parsed["s"], parsed["none"], parsed["ok"]), (3, "0.1", None, True))
        self.assertNotIn("E", body.replace('"', ''))   # plain notation, whatever the Decimal's exponent

    def test_a_string_that_looks_like_a_number_stays_a_string(self):
        # A subject id is user text; it must never turn into a number on the way out.
        self.assertEqual(exact(exact_json({"subject_id": "123.5"}))["subject_id"], "123.5")

    def test_a_decimal_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            exact_json({"x": Decimal("NaN")})

    def test_every_ledger_quantity_is_numeric_24_6(self):
        # The one scale MIG-197 agrees on, here and on invoice_line (process V60): created that way, and
        # an existing ledger widened in place.
        from etl.meter.store import PostgresStore
        ddl = " ".join(PostgresStore.DDL.split())
        for created in ("quantity numeric(24,6) not null, unit varchar(24) not null, occurred_at",
                        "meter varchar(64) not null, quantity numeric(24,6) not null",
                        "included_quantity numeric(24,6) not null default 0"):
            self.assertIn(created, ddl)
        for widened in ("alter table meter.usage_event alter column quantity type numeric(24,6)",
                        "alter table meter.usage_daily alter column quantity type numeric(24,6)",
                        "alter table meter.rate_card_item alter column included_quantity type numeric(24,6)"):
            self.assertIn(widened, ddl)
        self.assertNotIn("numeric(18,6)", ddl)


if __name__ == "__main__":
    unittest.main()
