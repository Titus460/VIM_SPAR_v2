"""Read/write enriched extraction records to output/enriched.json."""

import json
from pathlib import Path

from vim.extraction import config

ENRICHED_PATH = config.OUTPUT_DIR / "enriched.json"


def load_all() -> list[dict]:
    if not ENRICHED_PATH.exists():
        return []
    data = json.loads(ENRICHED_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def save_all(records: list[dict]) -> Path:
    from vim.extraction.vendors import attach_vendor_id

    ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched = [attach_vendor_id(dict(rec)) for rec in records]
    ENRICHED_PATH.write_text(json.dumps(enriched, indent=2, default=str), encoding="utf-8")
    return ENRICHED_PATH


def _record_key(record: dict) -> str | None:
    """Stable key for deduplication — prefer original upload filename."""
    return record.get("file_name") or record.get("stored_file_name") or record.get("file_path")


def _dedupe_records(records: list[dict]) -> list[dict]:
    """Keep the latest record per file_name; preserve first-seen order."""
    ordered_keys: list[str] = []
    by_key: dict[str, dict] = {}
    orphans: list[dict] = []

    for rec in records:
        key = _record_key(rec)
        if not key:
            orphans.append(rec)
            continue
        if key not in by_key:
            ordered_keys.append(key)
        by_key[key] = rec

    return [by_key[k] for k in ordered_keys] + orphans


def upsert_record(record: dict) -> Path:
    """Insert or update one record in enriched.json (matched by file_name)."""
    records = _dedupe_records(load_all())
    key = _record_key(record)
    if not key:
        records.append(record)
        return save_all(records)

    updated = False
    for i, existing in enumerate(records):
        if _record_key(existing) == key:
            records[i] = record
            updated = True
            break
    if not updated:
        records.append(record)
    return save_all(records)
