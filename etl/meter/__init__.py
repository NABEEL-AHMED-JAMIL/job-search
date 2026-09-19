"""
    The metering service: the one place every pipeline, and the console, reports usage to.

    A ledger of usage events (append-only, deduplicated), a daily rollup priced from a versioned
    rate card, and the reads the console's Cost & usage screen makes. See .ai/grooming for the
    design; the contract is `etl.meter.app`.
"""
