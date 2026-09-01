"""Read/write enriched extraction records to output/enriched.json."""
 
import json
import os
import threading
from pathlib import Path
 
from vim.extraction import config
 
ENRICHED_PATH = config.OUTPUT_DIR / "enriched.json"
 
# Every update is a read-modify-write of the whole file, and uploads are now
# processed in parallel, so unsynchronised callers would drop each other's
# records. Reentrant because the update helpers call save_all() while holding it.
_file_lock = threading.RLock()
 
 
def load_all() -> list[dict]:
    with _file_lock:
        if not ENRICHED_PATH.exists():
            return []
        data = json.loads(ENRICHED_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []
 
 
def save_all(records: list[dict]) -> Path:
    from vim.extraction.vendors import attach_vendor_id
 
    with _file_lock:
        ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
        enriched = [attach_vendor_id(dict(rec)) for rec in records]
        payload = json.dumps(enriched, indent=2, default=str)
 
        # Write then rename, so an interrupted write cannot leave the file
        # truncated and unreadable for every later upload.
        tmp_path = ENRICHED_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, ENRICHED_PATH)
 
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
 
 
def delete_record(key: str, stored_file_name: str | None = None) -> bool:
    """
    Remove the record for a file.
 
    Records are keyed by original filename, so pass stored_file_name to delete
    only the record for one specific upload. Without it, re-uploading a name
    that already exists would delete the earlier file's record too.
    """
    def is_target(rec: dict) -> bool:
        if stored_file_name is not None:
            return rec.get("stored_file_name") == stored_file_name
        return _record_key(rec) == key
 
    with _file_lock:
        records = _dedupe_records(load_all())
        remaining = [r for r in records if not is_target(r)]
        if len(remaining) == len(records):
            return False
        save_all(remaining)
    return True
 
 
def find_by_stored_name(stored_file_name: str) -> dict | None:
    """Return the enriched.json record for one upload on disk, if any."""
    if not stored_file_name:
        return None
    for rec in load_all():
        if rec.get("stored_file_name") == stored_file_name:
            return rec
    return None
 
 
def upsert_record(record: dict) -> Path:
    """Insert or update one record in enriched.json (matched by file_name)."""
    key = _record_key(record)
 
    with _file_lock:
        records = _dedupe_records(load_all())
 
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
