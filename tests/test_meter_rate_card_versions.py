"""
    MIG-88: meter.rate_card versions come from a sequence. PostgresStore took max(version) + 1 with no lock,
    so two cards saved at once collided on the primary key -- a person's save answered with a 500. Against
    a real PostgreSQL, in a throwaway database: eight saves at once make eight distinct versions.

    And P6: where billing-service's Liquibase owns the meter schema (billing_db), the meter runs no DDL of
    its own (METER_APPLY_DDL=false) -- its role has no right to, and should not need one.
"""
import os
import threading
import time
import unittest
from datetime import date

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None

from etl.meter.store import PostgresStore

ADMIN = os.getenv("METER_IT_ADMIN_DSN", "postgresql://nabeel.amd93:admin@localhost:5433/postgres")


def reachable():
    if psycopg2 is None:
        return False
    try:
        psycopg2.connect(ADMIN, connect_timeout=2).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(reachable(), "no PostgreSQL for the meter's integration tests")
class RateCardVersionsTest(unittest.TestCase):

    def setUp(self):
        self.name = f"meter_it_{time.time_ns()}"
        admin = psycopg2.connect(ADMIN)
        admin.autocommit = True
        admin.cursor().execute(f"create database {self.name}")
        admin.close()
        self.dsn = ADMIN.rsplit("/", 1)[0] + "/" + self.name

    def tearDown(self):
        admin = psycopg2.connect(ADMIN)
        admin.autocommit = True
        admin.cursor().execute(f"drop database if exists {self.name} with (force)")
        admin.close()

    def test_the_seed_card_takes_its_version_from_the_sequence(self):
        store = PostgresStore(self.dsn)
        self.assertEqual([c["version"] for c in store.rate_cards()], [1])
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute("select nextval('meter.rate_card_version_seq')")
            self.assertEqual(cur.fetchone()[0], 2)

    def test_eight_cards_saved_at_once_are_eight_versions(self):
        store = PostgresStore(self.dsn)
        items = [{"meter": "pipeline.runs", "unit": "run", "per": 1, "unit_price": "0.002"}]
        versions, errors = [], []
        start = threading.Barrier(8)

        def save(i):
            try:
                start.wait()
                versions.append(store.save_rate_card(date(2026, 10, 1), "USD", items, name=f"card {i}")["version"])
            except Exception as ex:  # noqa: BLE001
                errors.append(ex)

        threads = [threading.Thread(target=save, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(versions), list(range(2, 10)))

    def test_a_store_on_a_managed_schema_runs_no_ddl(self):
        PostgresStore(self.dsn)                      # the schema, as Liquibase would have left it
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute("alter table meter.rate_card add column sentinel int")   # DDL would not remove it...
            cur.execute("drop sequence meter.rate_card_version_seq cascade")     # ...but would recreate this
        PostgresStore(self.dsn, apply_ddl=False)
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute("select count(*) from pg_class where relname = 'rate_card_version_seq'")
            self.assertEqual(cur.fetchone()[0], 0, "a store told not to manage the schema ran its DDL")

    def test_the_environment_decides_by_default(self):
        PostgresStore(self.dsn)
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute("drop sequence meter.rate_card_version_seq cascade")
        os.environ["METER_APPLY_DDL"] = "false"
        try:
            PostgresStore(self.dsn)
        finally:
            del os.environ["METER_APPLY_DDL"]
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute("select count(*) from pg_class where relname = 'rate_card_version_seq'")
            self.assertEqual(cur.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
