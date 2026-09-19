"""
    etl-meter: the usage ledger every pipeline and the console report to.

    Contract (v1):
      POST /v1/events           a batch of usage events; idempotent on dedupe_key
      GET  /v1/usage            the priced daily rollup for a tenant and range, grouped
      GET  /v1/usage/subjects   the events behind one meter, summed by subject (bucket, prompt, actor)
      GET  /v1/usage/events     the raw events, paged
      GET  /v1/ratecard         the card (latest, or ?version=)
      PUT  /v1/ratecard         a new version
      POST /v1/rollup           rebuild one tenant-day, or every day touched since a moment
      GET  /health

    Two kinds of caller, and every event records which one vouched for it:
      - a PIPELINE sends the run's own callback token (X-Worker-Token) with jobId and jobQueueId;
        the console verifies it and answers the tenant, so a run can only report as its own
        workspace -- the same proof /changeState and /aiPrompt.json/run already rely on;
      - a SERVICE (the console, the nightly measurer) sends X-Service-Key, and may name any tenant.

    Reporting is never in a job's critical path: the client batches, retries and spools; this
    end answers fast and does the rollup in the background.
"""
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from etl.meter.rates import KNOWN_METERS, label_of, price_item, service_of
from etl.meter.store import MemoryStore, PostgresStore
from etl.util.logging_config import get_logger

logger = get_logger(__name__)

MAX_BATCH = 500
CONSOLE_URL = os.getenv("ETL_EVENT_URL", "http://host.docker.internal:9098/api/v1").rstrip("/")
SERVICE_KEY = (os.getenv("METER_SERVICE_KEY") or "").strip()


def build_store():
    if os.getenv("METER_DATABASE_URL"):
        return PostgresStore()
    logger.warning("METER_DATABASE_URL is not set -- the ledger is in memory and will not survive a restart")
    return MemoryStore()


class EventIn(BaseModel):
    tenantId: Optional[int] = None
    meter: str
    quantity: float
    unit: Optional[str] = None
    occurredAt: Optional[datetime] = None
    source: str = "pipeline"
    subjectType: Optional[str] = None
    subjectId: Optional[str] = None
    actorUserId: Optional[int] = None
    jobQueueId: Optional[int] = None
    dedupeKey: str = Field(min_length=1, max_length=200)
    note: Optional[str] = None


class EventBatch(BaseModel):
    events: List[EventIn] = Field(max_length=MAX_BATCH)


class Tier(BaseModel):
    from_: float = Field(default=0, alias="from")
    unit_price: float

    model_config = {"populate_by_name": True}


class RateItem(BaseModel):
    meter: str
    unit: str
    per: int = 1
    unit_price: float
    included_quantity: float = 0
    tiers: List[Tier] = []


class RateCardIn(BaseModel):
    """A new version. `tenant_id` makes it that workspace's own card; none is the default for everyone.
    Items missing from the list are carried over from `based_on_version` (the card being edited), so a
    change to one price is a one-item request."""
    name: str = Field(min_length=1, max_length=120)
    effective_from: date
    currency: str = "USD"
    tenant_id: Optional[int] = None
    based_on_version: Optional[int] = None
    note: Optional[str] = None
    items: List[RateItem]


class Caller:
    def __init__(self, kind, tenant_id=None, job_queue_id=None):
        self.kind = kind            # "service" | "run"
        self.tenant_id = tenant_id
        self.job_queue_id = job_queue_id


def verify_run_with_console(job_id, job_queue_id, token):
    """Asks the console whether this token is the live token of this run, and whose run it is."""
    try:
        response = requests.post(f"{CONSOLE_URL}/meter.json/verifyRun", json={"jobId": job_id, "jobQueueId": job_queue_id},
                                 headers={"X-Worker-Token": token}, timeout=5)
    except requests.RequestException as ex:
        raise HTTPException(status_code=503, detail=f"The console could not be asked to verify the run: {ex}")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="The console refused this run's token.")
    body = response.json()
    data = body.get("data") or {}
    if body.get("status") != "SUCCESS" or not data.get("tenantId"):
        raise HTTPException(status_code=401, detail=body.get("message") or "The console refused this run's token.")
    return int(data["tenantId"])


def create_app(store=None, verify_run=verify_run_with_console, service_key=None):
    store = store or build_store()
    service_key = SERVICE_KEY if service_key is None else service_key
    app = FastAPI(title="etl-meter", version="1")
    app.state.store = store
    rollup_lock = threading.Lock()
    dirty = set()               # (tenant_id, day) touched since the last rollup

    def caller(x_service_key: Optional[str] = Header(default=None), x_worker_token: Optional[str] = Header(default=None),
               x_job_id: Optional[int] = Header(default=None), x_job_queue_id: Optional[int] = Header(default=None)) -> Caller:
        if x_service_key:
            if not service_key or x_service_key != service_key:
                raise HTTPException(status_code=401, detail="Unknown service key.")
            return Caller("service")
        if x_worker_token:
            if not x_job_id or not x_job_queue_id:
                raise HTTPException(status_code=400, detail="A run reports with X-Job-Id and X-Job-Queue-Id beside its token.")
            tenant_id = verify_run(x_job_id, x_job_queue_id, x_worker_token)
            return Caller("run", tenant_id=tenant_id, job_queue_id=x_job_queue_id)
        raise HTTPException(status_code=401, detail="Send X-Service-Key, or a run's X-Worker-Token with X-Job-Id and X-Job-Queue-Id.")

    def reader(x_service_key: Optional[str] = Header(default=None)) -> Caller:
        # Reads are the console's; a pipeline has no business reading the ledger.
        if not x_service_key or not service_key or x_service_key != service_key:
            raise HTTPException(status_code=401, detail="Reads need the service key.")
        return Caller("service")

    def do_rollup(pairs):
        with rollup_lock:
            done = 0
            for tenant_id, day in sorted(pairs):
                try:
                    store.rollup(tenant_id, day)
                    done += 1
                except Exception as ex:      # noqa: BLE001 -- a rollup that fails is retried next round
                    logger.error("rollup failed for tenant %s day %s: %s", tenant_id, day, ex)
                    dirty.add((tenant_id, day))
            return done

    def background_rollup():
        while True:
            time.sleep(float(os.getenv("METER_ROLLUP_SECONDS", "15")))
            if dirty:
                pairs, dirty_copy = set(dirty), None
                dirty.clear()
                do_rollup(pairs)

    if os.getenv("METER_ROLLUP_SECONDS", "15") != "0":
        threading.Thread(target=background_rollup, daemon=True, name="meter-rollup").start()

    @app.get("/health")
    def health():
        info = store.health()
        info.update({"status": "ok", "store": type(store).__name__, "dirty_days": len(dirty)})
        return info

    @app.post("/v1/events")
    def post_events(batch: EventBatch, who: Caller = Depends(caller)):
        now = datetime.now(timezone.utc)
        rows, rejected = [], []
        for i, e in enumerate(batch.events):
            if e.meter not in KNOWN_METERS:
                rejected.append({"index": i, "reason": f"unknown meter {e.meter}"}); continue
            if e.quantity == 0:
                rejected.append({"index": i, "reason": "quantity is 0"}); continue
            if who.kind == "run":
                tenant_id, job_queue_id = who.tenant_id, who.job_queue_id
            else:
                tenant_id, job_queue_id = e.tenantId, e.jobQueueId
                if not tenant_id:
                    rejected.append({"index": i, "reason": "tenantId is required"}); continue
            occurred = e.occurredAt or now
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone.utc)
            rows.append({
                "tenant_id": tenant_id, "meter": e.meter, "quantity": Decimal(str(e.quantity)), "unit": e.unit or "",
                "occurred_at": occurred, "source": e.source[:24], "subject_type": (e.subjectType or None),
                "subject_id": (e.subjectId or None) and e.subjectId[:512], "actor_user_id": e.actorUserId,
                "job_queue_id": job_queue_id, "dedupe_key": e.dedupeKey, "note": (e.note or None) and e.note[:400],
                "vouched_by": who.kind,
            })
        accepted, duplicates = store.insert_events(rows)
        for r in rows:
            dirty.add((r["tenant_id"], r["occurred_at"].astimezone(timezone.utc).date()))
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    @app.get("/v1/usage")
    def get_usage(tenantId: Optional[int] = None, start: date = Query(...), end: date = Query(...),
                  groupBy: str = "meter", who: Caller = Depends(reader)):
        if dirty:
            do_rollup(set(dirty)); dirty.clear()
        rows = store.usage(tenantId, start, end) if tenantId else store.usage_all_tenants(start, end)
        out = {"tenantId": tenantId, "start": start, "end": end, "groupBy": groupBy}
        if groupBy == "meter" and tenantId:
            # A period's card is the one in effect at its start for this workspace; allowances and
            # tiers apply to the period's totals, so the amount here is what the bill will say.
            card = store.rate_card_for(start.replace(day=1), tenantId)
            out["rateCard"] = {"version": card["version"], "name": card["name"], "currency": card["currency"],
                               "tenantSpecific": card.get("tenant_id") is not None, "effectiveFrom": card["effective_from"]}
            out["rows"] = _priced_period(rows, card)
        else:
            out["rows"] = _group(rows, groupBy)
        return out

    @app.get("/v1/usage/subjects")
    def get_subjects(tenantId: int, meter: str, start: date, end: date, limit: int = 50, who: Caller = Depends(reader)):
        rows = store.subjects(tenantId, meter, start, end, limit=min(limit, 500))
        return {"meter": meter, "label": label_of(meter), "rows": rows}

    @app.get("/v1/usage/events")
    def get_events(tenantId: int, meter: Optional[str] = None, start: Optional[date] = None, end: Optional[date] = None,
                   subjectType: Optional[str] = None, page: int = 1, limit: int = 100, who: Caller = Depends(reader)):
        limit = min(max(limit, 1), 500)
        total, rows = store.list_events(tenantId, meter, start, end, subjectType, limit=limit, offset=(max(page, 1) - 1) * limit)
        return {"total": total, "page": page, "limit": limit, "rows": rows}

    @app.get("/v1/ratecards")
    def list_ratecards(who: Caller = Depends(reader)):
        cards = store.rate_cards()
        for card in cards:
            _label_items(card)
        return {"cards": cards}

    @app.get("/v1/ratecard")
    def get_ratecard(version: Optional[int] = None, tenantId: Optional[int] = None, day: Optional[date] = None, who: Caller = Depends(reader)):
        """One version by number, or the card in effect for a workspace on a day (today by default)."""
        card = store.rate_card(version) if version else store.rate_card_for(day or date.today(), tenantId)
        if not card:
            raise HTTPException(status_code=404, detail="No such rate card version.")
        return _label_items(card)

    @app.put("/v1/ratecard")
    def put_ratecard(card: RateCardIn, who: Caller = Depends(reader)):
        unknown = [i.meter for i in card.items if i.meter not in KNOWN_METERS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown meter(s): {', '.join(unknown)}")
        for i in card.items:
            if i.unit_price < 0 or i.included_quantity < 0 or i.per < 1 or any(t.unit_price < 0 or t.from_ < 0 for t in i.tiers):
                raise HTTPException(status_code=400, detail=f"{i.meter}: prices, allowances and tier starts cannot be negative.")
        # Start from the card being edited, so one changed price is a one-item request.
        items = {}
        base = store.rate_card(card.based_on_version) if card.based_on_version else None
        if base:
            for i in base["items"]:
                items[i["meter"]] = dict(i)
        for i in card.items:
            items[i.meter] = {"meter": i.meter, "unit": i.unit, "per": i.per, "unit_price": i.unit_price,
                              "included_quantity": i.included_quantity, "tiers": [{"from": t.from_, "unit_price": t.unit_price} for t in i.tiers]}
        saved = store.save_rate_card(card.effective_from, card.currency, list(items.values()), name=card.name,
                                     tenant_id=card.tenant_id, based_on_version=card.based_on_version, note=card.note)
        # Prices changed from that date for whoever this card covers: their days from it are stale
        # until rolled again. Issued invoices are frozen on the console side and do not move.
        since = datetime.combine(card.effective_from, datetime.min.time(), tzinfo=timezone.utc)
        for tenant_id, day in store.days_with_events(since):
            if card.tenant_id is None or tenant_id == card.tenant_id:
                dirty.add((tenant_id, day))
        return _label_items(saved)

    @app.post("/v1/rollup")
    def post_rollup(tenantId: Optional[int] = None, day: Optional[date] = None, sinceHours: int = 48, who: Caller = Depends(reader)):
        if tenantId and day:
            pairs = {(tenantId, day)}
        else:
            since = datetime.now(timezone.utc) - timedelta(hours=sinceHours)
            pairs = set(store.days_with_events(since)) | set(dirty)
        dirty.difference_update(pairs)
        return {"rolled": do_rollup(pairs)}

    return app


def _label_items(card):
    for item in card["items"]:
        item["label"] = label_of(item["meter"]); item["service"] = service_of(item["meter"])
    return card


def _priced_period(rows, card):
    """usage_daily rows of one workspace over one period, summed per meter and priced with the card's
    per-item calculation: allowance first, then tiers, else the flat price."""
    items = {i["meter"]: i for i in card["items"]}
    by = {}
    for r in rows:
        entry = by.setdefault(r["meter"], {"meter": r["meter"], "label": label_of(r["meter"]), "service": service_of(r["meter"]),
                                            "unit": r["unit"], "quantity": Decimal("0"), "days": 0})
        entry["quantity"] += r["quantity"]; entry["days"] += 1
    out = []
    for meter, entry in by.items():
        item = items.get(meter)
        if item:
            amount, detail = price_item(entry["quantity"], item)
            entry.update({"unit": item["unit"], "per": item["per"], "unitPrice": item["unit_price"], "amount": amount,
                          "includedQuantity": detail["included"], "billableQuantity": detail["billable"],
                          "tiers": detail.get("tiers", []), "hasTiers": bool(item.get("tiers"))})
        else:
            entry.update({"per": 1, "unitPrice": Decimal("0"), "amount": Decimal("0"), "includedQuantity": Decimal("0"),
                          "billableQuantity": entry["quantity"], "tiers": [], "hasTiers": False, "unpriced": True})
        out.append(entry)
    return sorted(out, key=lambda e: e["amount"], reverse=True)


def _group(rows, group_by):
    """usage_daily rows, folded the way a screen asks for them."""
    if group_by == "day":
        out = {}
        for r in rows:
            key = (r.get("tenant_id"), r["day"])
            entry = out.setdefault(key, {"tenantId": r.get("tenant_id"), "day": r["day"], "amount": Decimal("0"), "byService": {}})
            entry["amount"] += r["amount"]
            svc = service_of(r["meter"])
            entry["byService"][svc] = entry["byService"].get(svc, Decimal("0")) + r["amount"]
        return list(out.values())
    if group_by == "tenant":
        out = {}
        for r in rows:
            entry = out.setdefault(r.get("tenant_id"), {"tenantId": r.get("tenant_id"), "amount": Decimal("0"), "quantityByMeter": {}})
            entry["amount"] += r["amount"]
            entry["quantityByMeter"][r["meter"]] = entry["quantityByMeter"].get(r["meter"], Decimal("0")) + r["quantity"]
        return list(out.values())
    out = {}
    for r in rows:
        entry = out.setdefault(r["meter"], {"meter": r["meter"], "label": label_of(r["meter"]), "service": service_of(r["meter"]),
                                            "unit": r["unit"], "per": r["per"], "unitPrice": r["unit_price"],
                                            "quantity": Decimal("0"), "amount": Decimal("0"), "days": 0})
        entry["quantity"] += r["quantity"]; entry["amount"] += r["amount"]; entry["days"] += 1
    return sorted(out.values(), key=lambda e: e["amount"], reverse=True)


# Started with `uvicorn etl.meter.app:create_app --factory`, so importing this module (the tests
# do) builds nothing and starts no thread.
