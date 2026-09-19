"""
    Where the ledger lives.

    `PostgresStore` keeps it in the `meter` schema of the same Postgres the console uses, so an
    invoice (Phase 2) can join a usage line to the run it came from. `MemoryStore` is the same
    contract in dictionaries, for the unit tests and for a laptop with no database -- the app is
    written against the contract, not against SQL, which is also what will let the Java rewrite
    reuse the tests' expectations.

    Every method takes and returns plain dicts and Decimals; the app does the JSON.
"""
import os
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from etl.meter.rates import SEED_V1, price

EVENT_COLUMNS = ("tenant_id", "meter", "quantity", "unit", "occurred_at", "source", "subject_type",
                 "subject_id", "actor_user_id", "job_queue_id", "dedupe_key", "note", "vouched_by")


def _day_of(occurred_at):
    return occurred_at.astimezone(timezone.utc).date() if occurred_at.tzinfo else occurred_at.date()


class MemoryStore:
    """The contract, in memory. Same behaviour as Postgres for everything the tests assert."""

    def __init__(self):
        self.events = []            # list of dicts, insertion order
        self.dedupe = set()
        self.daily = {}             # (tenant_id, day, meter) -> dict
        self.cards = []             # list of {version, effective_from, currency, items:[...]}
        self.lock = threading.Lock()
        self.seed_rate_card()

    # -- rate card ---------------------------------------------------------
    def seed_rate_card(self):
        if self.cards:
            return
        self.cards.append({
            "version": 1, "effective_from": date(2026, 1, 1), "currency": "USD",
            "items": [{"meter": m, "unit": u, "per": p, "unit_price": Decimal(up)} for m, u, p, up in SEED_V1],
        })

    def rate_card(self, version=None):
        if version is None:
            return self.cards[-1]
        for card in self.cards:
            if card["version"] == version:
                return card
        return None

    def rate_card_for(self, day):
        current = None
        for card in sorted(self.cards, key=lambda c: (c["effective_from"], c["version"])):
            if card["effective_from"] <= day:
                current = card
        return current or self.cards[0]

    def save_rate_card(self, effective_from, currency, items):
        version = max(c["version"] for c in self.cards) + 1
        card = {"version": version, "effective_from": effective_from, "currency": currency,
                "items": [dict(i, unit_price=Decimal(str(i["unit_price"]))) for i in items]}
        self.cards.append(card)
        return card

    # -- events ------------------------------------------------------------
    def insert_events(self, events):
        """Returns (accepted, duplicates). A repeated dedupe_key is a duplicate, never a second row."""
        accepted = duplicates = 0
        with self.lock:
            for event in events:
                key = event["dedupe_key"]
                if key in self.dedupe:
                    duplicates += 1
                    continue
                self.dedupe.add(key)
                row = dict(event)
                row["event_id"] = len(self.events) + 1
                row["quantity"] = Decimal(str(event["quantity"]))
                self.events.append(row)
                accepted += 1
        return accepted, duplicates

    def days_with_events(self, since):
        days = set()
        for e in self.events:
            if e["occurred_at"] >= since:
                days.add((e["tenant_id"], _day_of(e["occurred_at"])))
        return sorted(days)

    def list_events(self, tenant_id, meter=None, start=None, end=None, subject_type=None, limit=100, offset=0):
        rows = [e for e in self.events if e["tenant_id"] == tenant_id
                and (meter is None or e["meter"] == meter)
                and (start is None or _day_of(e["occurred_at"]) >= start)
                and (end is None or _day_of(e["occurred_at"]) <= end)
                and (subject_type is None or e.get("subject_type") == subject_type)]
        rows.sort(key=lambda e: e["occurred_at"], reverse=True)
        return len(rows), rows[offset:offset + limit]

    # -- rollup ------------------------------------------------------------
    def rollup(self, tenant_id, day):
        """Rebuilds one tenant-day from the events, priced with the card current that day."""
        card = self.rate_card_for(day)
        items = {i["meter"]: i for i in card["items"]}
        totals = defaultdict(Decimal)
        for e in self.events:
            if e["tenant_id"] == tenant_id and _day_of(e["occurred_at"]) == day:
                totals[e["meter"]] += e["quantity"]
        with self.lock:
            for key in [k for k in self.daily if k[0] == tenant_id and k[1] == day]:
                del self.daily[key]
            for meter, quantity in totals.items():
                item = items.get(meter)
                amount = price(quantity, item["per"], item["unit_price"]) if item else Decimal("0")
                self.daily[(tenant_id, day, meter)] = {
                    "tenant_id": tenant_id, "day": day, "meter": meter, "quantity": quantity,
                    "unit": item["unit"] if item else "", "per": item["per"] if item else 1,
                    "unit_price": item["unit_price"] if item else Decimal("0"), "amount": amount,
                    "rate_card_version": card["version"],
                }
        return len(totals)

    def usage(self, tenant_id, start, end):
        return [d for (t, day, _), d in sorted(self.daily.items(), key=lambda kv: (kv[0][1], kv[0][2]))
                if t == tenant_id and start <= day <= end]

    def usage_all_tenants(self, start, end):
        return [d for (_, day, _), d in sorted(self.daily.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
                if start <= day <= end]

    def subjects(self, tenant_id, meter, start, end, limit=50):
        """The events behind one meter, summed by subject -- 'which bucket', 'which prompt'."""
        by = defaultdict(lambda: {"quantity": Decimal("0"), "events": 0, "last": None, "actor_user_id": None})
        for e in self.events:
            if e["tenant_id"] == tenant_id and e["meter"] == meter and start <= _day_of(e["occurred_at"]) <= end:
                key = (e.get("subject_type") or "", e.get("subject_id") or "")
                row = by[key]
                row["quantity"] += e["quantity"]; row["events"] += 1
                if row["last"] is None or e["occurred_at"] > row["last"]:
                    row["last"] = e["occurred_at"]; row["actor_user_id"] = e.get("actor_user_id")
        rows = [dict(subject_type=k[0], subject_id=k[1], **v) for k, v in by.items()]
        rows.sort(key=lambda r: r["quantity"], reverse=True)
        return rows[:limit]

    def health(self):
        minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
        return {"events": len(self.events), "events_last_minute": sum(1 for e in self.events if e["occurred_at"] >= minute_ago)}


class PostgresStore:
    """The same contract on Postgres. SQL kept plain so the Java rewrite can read it."""

    DDL = """
    create schema if not exists meter;
    create table if not exists meter.rate_card (
        version int primary key, effective_from date not null, currency varchar(3) not null default 'USD',
        created_at timestamptz not null default now());
    create table if not exists meter.rate_card_item (
        version int not null references meter.rate_card(version), meter varchar(64) not null, unit varchar(24) not null,
        per int not null default 1, unit_price numeric(18,8) not null, primary key (version, meter));
    create table if not exists meter.usage_event (
        event_id bigserial primary key, tenant_id bigint not null, meter varchar(64) not null,
        quantity numeric(18,6) not null, unit varchar(24) not null, occurred_at timestamptz not null,
        source varchar(24) not null, subject_type varchar(32), subject_id varchar(512), actor_user_id bigint,
        job_queue_id bigint, dedupe_key varchar(200) not null unique, note varchar(400), vouched_by varchar(24) not null,
        received_at timestamptz not null default now());
    create index if not exists usage_event_tenant_day on meter.usage_event (tenant_id, occurred_at);
    create index if not exists usage_event_meter on meter.usage_event (tenant_id, meter, occurred_at);
    create table if not exists meter.usage_daily (
        tenant_id bigint not null, day date not null, meter varchar(64) not null, quantity numeric(18,6) not null,
        unit varchar(24) not null, per int not null, unit_price numeric(18,8) not null, amount numeric(18,5) not null,
        rate_card_version int not null, rolled_at timestamptz not null default now(), primary key (tenant_id, day, meter));
    """

    def __init__(self, dsn=None):
        import psycopg2
        import psycopg2.extras
        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras
        self.dsn = dsn or os.environ["METER_DATABASE_URL"]
        self.lock = threading.Lock()
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(self.DDL)
        self.seed_rate_card()

    def _conn(self):
        return self._psycopg2.connect(self.dsn)

    # -- rate card ---------------------------------------------------------
    def seed_rate_card(self):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select count(*) from meter.rate_card")
            if cur.fetchone()[0]:
                return
            cur.execute("insert into meter.rate_card (version, effective_from, currency) values (1, %s, 'USD')", (date(2026, 1, 1),))
            self._extras.execute_values(cur, "insert into meter.rate_card_item (version, meter, unit, per, unit_price) values %s",
                                        [(1, m, u, p, Decimal(up)) for m, u, p, up in SEED_V1])

    def _card(self, cur, version):
        cur.execute("select version, effective_from, currency from meter.rate_card where version = %s", (version,))
        head = cur.fetchone()
        if not head:
            return None
        cur.execute("select meter, unit, per, unit_price from meter.rate_card_item where version = %s order by meter", (version,))
        return {"version": head[0], "effective_from": head[1], "currency": head[2],
                "items": [{"meter": m, "unit": u, "per": p, "unit_price": up} for m, u, p, up in cur.fetchall()]}

    def rate_card(self, version=None):
        with self._conn() as conn, conn.cursor() as cur:
            if version is None:
                cur.execute("select max(version) from meter.rate_card")
                version = cur.fetchone()[0]
            return self._card(cur, version)

    def rate_card_for(self, day):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select version from meter.rate_card where effective_from <= %s order by effective_from desc, version desc limit 1", (day,))
            row = cur.fetchone()
            if not row:
                cur.execute("select min(version) from meter.rate_card")
                row = cur.fetchone()
            return self._card(cur, row[0])

    def save_rate_card(self, effective_from, currency, items):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select coalesce(max(version), 0) + 1 from meter.rate_card")
            version = cur.fetchone()[0]
            cur.execute("insert into meter.rate_card (version, effective_from, currency) values (%s, %s, %s)", (version, effective_from, currency))
            self._extras.execute_values(cur, "insert into meter.rate_card_item (version, meter, unit, per, unit_price) values %s",
                                        [(version, i["meter"], i["unit"], int(i.get("per", 1)), Decimal(str(i["unit_price"]))) for i in items])
            return self._card(cur, version)

    # -- events ------------------------------------------------------------
    def insert_events(self, events):
        if not events:
            return 0, 0
        with self._conn() as conn, conn.cursor() as cur:
            rows = [tuple(e.get(c) for c in EVENT_COLUMNS) for e in events]
            inserted = self._extras.execute_values(
                cur, "insert into meter.usage_event (%s) values %%s on conflict (dedupe_key) do nothing returning event_id"
                     % ", ".join(EVENT_COLUMNS), rows, fetch=True)
            accepted = len(inserted)
            return accepted, len(events) - accepted

    def days_with_events(self, since):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select distinct tenant_id, (occurred_at at time zone 'UTC')::date from meter.usage_event where received_at >= %s order by 1, 2", (since,))
            return [(t, d) for t, d in cur.fetchall()]

    def list_events(self, tenant_id, meter=None, start=None, end=None, subject_type=None, limit=100, offset=0):
        where, args = ["tenant_id = %s"], [tenant_id]
        if meter: where.append("meter = %s"); args.append(meter)
        if start: where.append("(occurred_at at time zone 'UTC')::date >= %s"); args.append(start)
        if end: where.append("(occurred_at at time zone 'UTC')::date <= %s"); args.append(end)
        if subject_type: where.append("subject_type = %s"); args.append(subject_type)
        sql_where = " and ".join(where)
        with self._conn() as conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("select count(*) from meter.usage_event where " + sql_where, args)
            total = cur.fetchone()["count"]
            cur.execute("select * from meter.usage_event where " + sql_where + " order by occurred_at desc, event_id desc limit %s offset %s",
                        args + [limit, offset])
            return total, [dict(r) for r in cur.fetchall()]

    # -- rollup ------------------------------------------------------------
    def rollup(self, tenant_id, day):
        card = self.rate_card_for(day)
        items = {i["meter"]: i for i in card["items"]}
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select meter, sum(quantity) from meter.usage_event where tenant_id = %s and (occurred_at at time zone 'UTC')::date = %s group by meter",
                        (tenant_id, day))
            totals = cur.fetchall()
            cur.execute("delete from meter.usage_daily where tenant_id = %s and day = %s", (tenant_id, day))
            rows = []
            for meter, quantity in totals:
                item = items.get(meter)
                amount = price(quantity, item["per"], item["unit_price"]) if item else Decimal("0")
                rows.append((tenant_id, day, meter, quantity, item["unit"] if item else "", item["per"] if item else 1,
                             item["unit_price"] if item else Decimal("0"), amount, card["version"]))
            if rows:
                self._extras.execute_values(cur, "insert into meter.usage_daily (tenant_id, day, meter, quantity, unit, per, unit_price, amount, rate_card_version) values %s", rows)
            return len(rows)

    def usage(self, tenant_id, start, end):
        with self._conn() as conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("select * from meter.usage_daily where tenant_id = %s and day between %s and %s order by day, meter", (tenant_id, start, end))
            return [dict(r) for r in cur.fetchall()]

    def usage_all_tenants(self, start, end):
        with self._conn() as conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("select * from meter.usage_daily where day between %s and %s order by tenant_id, day, meter", (start, end))
            return [dict(r) for r in cur.fetchall()]

    def subjects(self, tenant_id, meter, start, end, limit=50):
        with self._conn() as conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute("""
                select coalesce(subject_type, '') as subject_type, coalesce(subject_id, '') as subject_id,
                       sum(quantity) as quantity, count(*) as events, max(occurred_at) as last,
                       (array_agg(actor_user_id order by occurred_at desc))[1] as actor_user_id
                from meter.usage_event
                where tenant_id = %s and meter = %s and (occurred_at at time zone 'UTC')::date between %s and %s
                group by 1, 2 order by quantity desc limit %s""", (tenant_id, meter, start, end, limit))
            return [dict(r) for r in cur.fetchall()]

    def health(self):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select count(*), count(*) filter (where received_at >= now() - interval '1 minute') from meter.usage_event")
            total, minute = cur.fetchone()
            return {"events": total, "events_last_minute": minute}
