"""
    Billing reconciliation (MIG-195): what was metered is what was invoiced, for a named period, with every
    gap attributed to a named rule -- or the run fails.

        python -m etl.meter.reconcile --period 2026-09 [--tenant 2901] [--json]

    Exits 0 when every figure reconciles or is explained, 1 when anything is unexplained, 2 on bad input.

    For each workspace and meter it follows the money through four hops, each checked against the next:

      ledger    meter.usage_event, summed over the period (occurred_at's UTC day, as the rollup counts it)
      rolled    meter.usage_daily, summed over the period -- must equal the ledger
      priced    the period's total priced with the card in effect at the period's start, by the meter's own
                app._priced_period / rates.price_item: allowance first, then tiers, else flat. Daily amounts
                are never summed -- a day is priced before its allowance, a period after it (C6).
      invoiced  the month's invoice line for the meter: quantity, included, billable and amount must be
                the priced ones; then the invoice's subtotal, tax and total by the recorded rounding chain
                (lines summed, rounded once to 2 places HALF_UP, tax on the rounded subtotal -- MIG-78).

    A gap is explained only by a named rule: allowance, tiers, the workspace's own card, a zero row the
    draft leaves out, usage received after the invoice was built (late), a manual line, a credit note,
    rounding, an open month. Anything else is UNEXPLAINED.
"""
import argparse
import json
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from etl.meter.rates import price_item

ZERO = Decimal("0")
CENT = Decimal("0.01")

OK, EXPLAINED, UNEXPLAINED = "ok", "explained", "UNEXPLAINED"


def period_of(text):
    """'2026-09' -> (date(2026, 9, 1), date(2026, 9, 30))."""
    year, month = (int(p) for p in text.split("-"))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _d(value):
    return ZERO if value is None else Decimal(str(value))


def _cents(value):
    return _d(value).quantize(CENT, rounding=ROUND_HALF_UP)


class Row:
    """One workspace's one meter over the period: every hop's figure, and what explains the gaps."""

    def __init__(self, tenant_id, meter):
        self.tenant_id, self.meter = tenant_id, meter
        self.metered = self.rolled = self.late = ZERO
        self.included = self.billable = self.priced = ZERO
        self.line_quantity = self.line_amount = None
        self.rules, self.problems = [], []

    @property
    def status(self):
        return UNEXPLAINED if self.problems else (EXPLAINED if self.rules else OK)

    def as_dict(self):
        return {"tenantId": self.tenant_id, "meter": self.meter, "metered": self.metered, "rolled": self.rolled, "late": self.late,
                "included": self.included, "billable": self.billable, "priced": self.priced,
                "lineQuantity": self.line_quantity, "lineAmount": self.line_amount,
                "status": self.status, "rules": self.rules, "problems": self.problems}


class InvoiceCheck:
    def __init__(self, tenant_id, number):
        self.tenant_id, self.number = tenant_id, number
        self.lines_total = self.subtotal = self.tax = self.total = self.credited = ZERO
        self.rules, self.problems = [], []

    @property
    def status(self):
        return UNEXPLAINED if self.problems else (EXPLAINED if self.rules else OK)

    def as_dict(self):
        return {"tenantId": self.tenant_id, "invoice": self.number, "linesTotal": self.lines_total, "subtotal": self.subtotal,
                "tax": self.tax, "total": self.total, "credited": self.credited, "status": self.status,
                "rules": self.rules, "problems": self.problems}


class Report:
    def __init__(self, start, end):
        self.start, self.end = start, end
        self.rows, self.invoices = [], []

    @property
    def unexplained(self):
        return [x for x in self.rows + self.invoices if x.status == UNEXPLAINED]

    @property
    def ok(self):
        return not self.unexplained

    def as_dict(self):
        return {"period": [self.start.isoformat(), self.end.isoformat()], "ok": self.ok,
                "rows": [r.as_dict() for r in self.rows], "invoices": [i.as_dict() for i in self.invoices]}


def reconcile(source, start, end, tenant_ids=None, today=None):
    """Reconciles every workspace with usage or an invoice in the period (or only those named)."""
    today = today or datetime.now(timezone.utc).date()
    report = Report(start, end)
    for tenant_id in sorted(tenant_ids or source.tenants(start, end)):
        _reconcile_tenant(source, report, tenant_id, start, end, today)
    return report


def _reconcile_tenant(source, report, tenant_id, start, end, today):
    card = source.rate_card_for(start, tenant_id)
    items = {i["meter"]: i for i in card["items"]}
    invoice = source.invoice(tenant_id, start)
    snapshot = invoice.get("snapshot_at") if invoice else None
    ledger = source.ledger_totals(tenant_id, start, end, snapshot)
    rolled = {}
    for daily in source.daily(tenant_id, start, end):
        rolled[daily["meter"]] = rolled.get(daily["meter"], ZERO) + _d(daily["quantity"])
    lines = {}
    manual = []
    for line in (invoice or {}).get("lines", []):
        if line.get("manual"):
            manual.append(line)
        else:
            lines[line["meter"]] = line

    for meter in sorted(set(ledger) | set(rolled) | set(lines)):
        row = Row(tenant_id, meter)
        report.rows.append(row)
        row.metered = ledger.get(meter, {}).get("total", ZERO)
        row.late = ledger.get(meter, {}).get("late", ZERO)
        row.rolled = rolled.get(meter, ZERO)
        if row.rolled != row.metered:
            row.problems.append(f"rollup: usage_daily holds {row.rolled}, the ledger {row.metered}")
        item = items.get(meter)
        if item is None:
            row.rules.append("not on the card: priced 0")
            item = {"meter": meter, "per": 1, "unit_price": 0, "included_quantity": 0, "tiers": []}
        amount, detail = price_item(row.rolled, item)
        row.included, row.billable, row.priced = detail["included"], detail["billable"], amount
        _explain_pricing(row, item, card)
        line = lines.get(meter)
        if invoice is None:
            continue
        if line is None:
            if row.rolled == 0 and amount == 0:
                row.rules.append("nothing used and nothing owed: no line (the draft leaves it out)")
            elif row.late and row.late == row.rolled:
                row.rules.append(f"late: all {row.late} arrived after the invoice was built")
            else:
                row.problems.append(f"no invoice line for {row.rolled} priced at {amount}")
            continue
        _check_line(row, line, item)

    _check_invoice(report, tenant_id, invoice, rolled, start, today, manual)


def _explain_pricing(row, item, card):
    if card.get("tenant_id") is not None:
        row.rules.append(f"the workspace's own card v{card['version']}")
    if row.included > 0 and row.billable < row.rolled:
        row.rules.append(f"allowance: the first {row.included} are included")
    if item.get("tiers"):
        row.rules.append(f"tiers: {len(item['tiers'])} bands")


def _check_line(row, line, item):
    q = _d(line.get("quantity"))
    row.line_quantity, row.line_amount = q, _d(line.get("amount"))
    if q != row.rolled:
        if row.late and q == row.rolled - row.late:
            row.rules.append(f"late: {row.late} arrived after the invoice was built; it bills when the month is redrafted")
        else:
            row.problems.append(f"line quantity {q}, metered {row.rolled}")
            return
    # The line must carry the pricing of its own quantity -- the meter's calculation, applied once.
    amount, detail = price_item(q, item)
    for name, seen, expected in (("included", line.get("included_quantity"), detail["included"]),
                                 ("billable", line.get("billable_quantity"), detail["billable"]),
                                 ("amount", line.get("amount"), amount)):
        if seen is not None and _d(seen) != expected:
            row.problems.append(f"line {name} {_d(seen)}, priced {expected}")


def _check_invoice(report, tenant_id, invoice, rolled, start, today, manual):
    if invoice is None:
        owed = any(v > 0 for v in rolled.values())
        if owed:
            check = InvoiceCheck(tenant_id, None)
            report.invoices.append(check)
            if start.replace(day=1) >= today.replace(day=1):
                check.rules.append("the period is still open: no invoice yet")
            else:
                check.problems.append("usage in a closed period and no invoice")
        return
    check = InvoiceCheck(tenant_id, invoice["number"])
    report.invoices.append(check)
    check.lines_total = sum((_d(l.get("amount")) for l in invoice.get("lines", [])), ZERO)
    check.subtotal, check.tax, check.total = _d(invoice.get("subtotal")), _d(invoice.get("tax")), _d(invoice.get("total"))
    for line in manual:
        check.rules.append(f"manual line: {line.get('description')} {_d(line.get('amount'))}")
    # The recorded rounding chain: summed, rounded once to 2 places HALF_UP, tax on the rounded subtotal.
    expected_subtotal = _cents(check.lines_total)
    if check.subtotal != expected_subtotal:
        check.problems.append(f"subtotal {check.subtotal}, lines round to {expected_subtotal}")
    elif expected_subtotal != check.lines_total:
        check.rules.append(f"rounding: lines {check.lines_total} to {expected_subtotal} (2 places, HALF_UP)")
    rate = _d(invoice.get("tax_rate_percent"))
    expected_tax = (check.subtotal * rate / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    if check.tax != expected_tax:
        check.problems.append(f"tax {check.tax}, {rate}% of {check.subtotal} is {expected_tax}")
    if check.total != check.subtotal + check.tax:
        check.problems.append(f"total {check.total}, subtotal and tax make {check.subtotal + check.tax}")
    for note in invoice.get("credit_notes", []):
        note_lines = sum((_d(l.get("amount")) for l in note.get("lines", [])), ZERO)
        check.credited += -_d(note.get("total"))
        if _cents(note_lines) != _d(note.get("total")):
            check.problems.append(f"credit note {note['number']}: total {_d(note.get('total'))}, its lines {note_lines}")
        else:
            check.rules.append(f"credit note {note['number']}: {_d(note.get('total'))}")


# ---- where the figures come from ---------------------------------------------------------------

class MemorySource:
    """A MemoryStore's ledger and cards, and invoices as dicts: the tests' source, and a shape reference."""

    def __init__(self, store, invoices=None):
        self.store, self.invoices = store, invoices or {}

    def tenants(self, start, end):
        from etl.meter.store import _day_of
        found = {e["tenant_id"] for e in self.store.events if start <= _day_of(e["occurred_at"]) <= end}
        return found | {t for (t, p) in self.invoices if p == start}

    def ledger_totals(self, tenant_id, start, end, cutoff):
        from etl.meter.store import _day_of
        out = {}
        for e in self.store.events:
            if e["tenant_id"] == tenant_id and start <= _day_of(e["occurred_at"]) <= end:
                entry = out.setdefault(e["meter"], {"total": ZERO, "late": ZERO})
                entry["total"] += e["quantity"]
                received = e.get("received_at") or e["occurred_at"]
                if cutoff is not None and received > cutoff:
                    entry["late"] += e["quantity"]
        return out

    def daily(self, tenant_id, start, end):
        return self.store.usage(tenant_id, start, end)

    def rate_card_for(self, day, tenant_id):
        return self.store.rate_card_for(day, tenant_id)

    def invoice(self, tenant_id, period_start):
        return self.invoices.get((tenant_id, period_start))


class PostgresSource:
    """The live figures, read only: the meter schema and billing's invoice tables, in one database."""

    def __init__(self, dsn):
        import psycopg2
        import psycopg2.extras
        from etl.meter.store import PostgresStore
        self._psycopg2, self._extras, self.dsn = psycopg2, psycopg2.extras, dsn
        # PostgresStore's own card and usage reads, without its constructor's DDL and seeding: read only.
        self.store = PostgresStore.__new__(PostgresStore)
        self.store.dsn, self.store._psycopg2, self.store._extras = dsn, psycopg2, psycopg2.extras

    def _rows(self, sql, args):
        with self._psycopg2.connect(self.dsn) as conn, conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

    def tenants(self, start, end):
        rows = self._rows("select distinct tenant_id from meter.usage_event where (occurred_at at time zone 'UTC')::date between %s and %s "
                          "union select tenant_id from public.invoice where kind = 'invoice' and status <> 'void' and period_start = %s",
                          (start, end, start))
        return {r["tenant_id"] for r in rows}

    def ledger_totals(self, tenant_id, start, end, cutoff):
        rows = self._rows("select meter, sum(quantity) as total, coalesce(sum(quantity) filter (where %s::timestamptz is not null "
                          "and received_at > %s::timestamptz), 0) as late from meter.usage_event where tenant_id = %s "
                          "and (occurred_at at time zone 'UTC')::date between %s and %s group by meter",
                          (cutoff, cutoff, tenant_id, start, end))
        return {r["meter"]: {"total": r["total"], "late": r["late"]} for r in rows}

    def daily(self, tenant_id, start, end):
        return self.store.usage(tenant_id, start, end)

    def rate_card_for(self, day, tenant_id):
        return self.store.rate_card_for(day, tenant_id)

    def invoice(self, tenant_id, period_start):
        heads = self._rows("select invoice_id, number, status, subtotal, tax_rate_percent, tax, total, "
                           "coalesce(issued_at, date_updated, date_created) at time zone 'UTC' as snapshot_at "
                           "from public.invoice where tenant_id = %s and period_start = %s and kind = 'invoice' and status <> 'void'",
                           (tenant_id, period_start))
        if not heads:
            return None
        head = heads[0]
        line_sql = ("select meter, description, quantity, included_quantity, billable_quantity, amount, manual from public.invoice_line "
                    "where invoice_id = %s and tenant_id = %s order by sort")
        head["lines"] = self._rows(line_sql, (head["invoice_id"], tenant_id))
        head["credit_notes"] = self._rows("select invoice_id, number, total from public.invoice where references_invoice_id = %s "
                                          "and kind = 'credit_note' and tenant_id = %s", (head["invoice_id"], tenant_id))
        for note in head["credit_notes"]:
            note["lines"] = self._rows(line_sql, (note["invoice_id"], tenant_id))
        return head


# ---- the command ---------------------------------------------------------------------------------

def render(report):
    out = [f"Reconciliation {report.start} .. {report.end}: {'OK' if report.ok else 'UNEXPLAINED DIFFERENCES'}", ""]
    out.append(f"{'tenant':>7} {'meter':<24} {'metered':>22} {'included':>14} {'billable':>22} {'priced':>12} {'invoiced':>12}  status")
    for r in report.rows:
        invoiced = "" if r.line_amount is None else str(r.line_amount)
        out.append(f"{r.tenant_id:>7} {r.meter:<24} {str(r.metered):>22} {str(r.included):>14} {str(r.billable):>22} "
                   f"{str(r.priced):>12} {invoiced:>12}  {r.status}")
        for why in r.rules:
            out.append(f"{'':>33}- {why}")
        for what in r.problems:
            out.append(f"{'':>33}! {what}")
    out.append("")
    for i in report.invoices:
        out.append(f"{i.tenant_id:>7} invoice {i.number or '-'}: lines {i.lines_total}, subtotal {i.subtotal}, tax {i.tax}, "
                   f"total {i.total}, credited {i.credited}  {i.status}")
        for why in i.rules:
            out.append(f"{'':>9}- {why}")
        for what in i.problems:
            out.append(f"{'':>9}! {what}")
    return "\n".join(out)


def main(argv=None, source_factory=None, today=None):
    parser = argparse.ArgumentParser(prog="python -m etl.meter.reconcile", description="Metered usage against invoices, for one period.")
    parser.add_argument("--period", required=True, help="the month, YYYY-MM")
    parser.add_argument("--tenant", type=int, action="append", help="only this workspace (repeatable)")
    parser.add_argument("--json", action="store_true", help="the report as JSON")
    args = parser.parse_args(argv)
    try:
        start, end = period_of(args.period)
    except ValueError:
        print(f"Not a month: {args.period} (YYYY-MM).", file=sys.stderr)
        return 2
    if source_factory is None:
        dsn = os.getenv("METER_DATABASE_URL")
        if not dsn:
            print("METER_DATABASE_URL is not set.", file=sys.stderr)
            return 2
        source = PostgresSource(dsn)
    else:
        source = source_factory()
    report = reconcile(source, start, end, args.tenant, today=today)
    print(json.dumps(report.as_dict(), default=str, indent=2) if args.json else render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
