"""
    The rate card: what a unit of each meter costs, versioned by effective date.

    A meter is a stable key (`storage.bytes.deleted`), a unit, and a price per `per` units --
    tokens are priced per 1,000, storage per GB-hour, seats per user-day. Events carry quantity
    only; pricing happens at rollup with the card that was current for that day, so a rate change
    never rewrites history.

    The seed card below is the one the design proposal drew. Placeholder prices in USD; the
    console's rate-card screen (Phase 3) edits later versions.
"""
from decimal import Decimal

# A byte meter is priced per this many bytes: the ``per`` its card items carry.
BYTES_PER_GB = 1024 ** 3

# meter, unit, per, unit_price
SEED_V1 = [
    ("storage.gb_hours", "GB-hour", 1, "0.000032"),
    # Bytes are carried as bytes and priced per GB: a 40-byte archive stored as 0.000000 GB is
    # a write that never happened, and numeric(18,6) can hold a terabyte in bytes.
    ("storage.bytes.written", "byte", BYTES_PER_GB, "0.01"),
    ("storage.bytes.deleted", "byte", BYTES_PER_GB, "0.01"),
    ("storage.bytes.read", "byte", BYTES_PER_GB, "0.0"),
    ("storage.ops.read", "op", 1000, "0.004"),
    ("storage.ops.write", "op", 1000, "0.005"),
    ("storage.ops.delete", "op", 1000, "0.005"),
    ("pipeline.runs", "run", 1, "0.002"),
    ("pipeline.worker_minutes", "minute", 1, "0.02"),
    ("ai.tokens.in", "token", 1000, "0.05"),
    ("ai.tokens.out", "token", 1000, "0.15"),
    ("ai.vision.images", "image", 1, "0.01"),
    ("ai.transcript.minutes", "minute", 1, "0.006"),
    ("analytics.queries", "query", 1, "0.001"),
    ("analytics.gb_scanned", "GB", 1, "0.005"),
    ("convert.documents", "document", 1, "0.02"),
    ("kafka.topic_hours", "topic-hour", 1, "0.001"),
    ("seats.user_days", "user-day", 1, "0.33"),
]

# What the screens call a meter, and which service it belongs to.
LABELS = {
    "storage.gb_hours": ("Storage kept", "Storage"),
    "storage.bytes.written": ("Bytes written", "Storage"),
    "storage.bytes.deleted": ("Bytes deleted (data churn)", "Storage"),
    "storage.bytes.read": ("Bytes read", "Storage"),
    "storage.ops.read": ("Storage reads", "Storage"),
    "storage.ops.write": ("Storage writes", "Storage"),
    "storage.ops.delete": ("Storage deletes", "Storage"),
    "pipeline.runs": ("Pipeline runs", "Pipelines"),
    "pipeline.worker_minutes": ("Worker minutes", "Pipelines"),
    "ai.tokens.in": ("Model tokens in", "Model calls"),
    "ai.tokens.out": ("Model tokens out", "Model calls"),
    "ai.vision.images": ("Images described", "Model calls"),
    "ai.transcript.minutes": ("Transcript minutes", "Model calls"),
    "analytics.queries": ("Analytics queries", "Analytics & tools"),
    "analytics.gb_scanned": ("Analytics data scanned", "Analytics & tools"),
    "convert.documents": ("Documents converted", "Analytics & tools"),
    "kafka.topic_hours": ("Kafka topics", "Pipelines"),
    "seats.user_days": ("Seats", "Seats"),
}

KNOWN_METERS = frozenset(m for m, _, _, _ in SEED_V1)


def price(quantity, per, unit_price):
    """quantity x unit_price / per, as a Decimal rounded to the cent-thousandth (5 places)."""
    q = Decimal(str(quantity))
    return (q * Decimal(str(unit_price)) / Decimal(per)).quantize(Decimal("0.00001"))


def price_item(quantity, item):
    """
    The calculation an item carries, applied to a period's quantity:

      included_quantity -- the first N units of the period are free (a monthly allowance);
      tiers             -- graduated: [{"from": 0, "unit_price": p0}, {"from": q1, "unit_price": p1}, ...],
                           each band priced at its own rate for the units that fall in it;
                           absent or empty means one flat unit_price.

    Returns (amount, detail) where detail says what was applied, so an invoice line can carry it.
    """
    q = Decimal(str(quantity))
    per = Decimal(item.get("per") or 1)
    included = Decimal(str(item.get("included_quantity") or 0))
    billable = max(q - included, Decimal("0"))
    tiers = item.get("tiers") or []
    detail = {"included": included, "billable": billable}
    if not tiers:
        return (billable * Decimal(str(item["unit_price"])) / per).quantize(Decimal("0.00001")), detail
    bands = sorted(({"from": Decimal(str(t.get("from") or 0)), "unit_price": Decimal(str(t["unit_price"]))} for t in tiers), key=lambda b: b["from"])
    if bands[0]["from"] > 0:
        bands.insert(0, {"from": Decimal("0"), "unit_price": Decimal(str(item["unit_price"]))})
    amount = Decimal("0")
    applied = []
    for i, band in enumerate(bands):
        upper = bands[i + 1]["from"] if i + 1 < len(bands) else None
        in_band = max(min(billable, upper) - band["from"], Decimal("0")) if upper is not None else max(billable - band["from"], Decimal("0"))
        if in_band > 0:
            amount += in_band * band["unit_price"] / per
            applied.append({"from": band["from"], "to": upper, "units": in_band, "unit_price": band["unit_price"]})
    detail["tiers"] = applied
    return amount.quantize(Decimal("0.00001")), detail


def label_of(meter):
    return LABELS.get(meter, (meter, "Other"))[0]


def service_of(meter):
    return LABELS.get(meter, (meter, "Other"))[1]
