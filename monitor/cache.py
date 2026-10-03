"""Cache su disco delle risposte HTTP.

Serve a sviluppare e testare in locale SENZA rifare richieste ai negozi.
Con la cache attiva, rilanciare lo scraper dieci volte di fila costa
zero richieste di rete finche' le voci non scadono.

Non va usata in produzione (il TTL va tenuto a 0): li' serve il dato fresco.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache"


def _key(url: str, params: dict | None) -> str:
    basis = url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def get(url: str, params: dict | None, ttl: float) -> tuple[bytes, dict] | None:
    if ttl <= 0:
        return None
    path = CACHE_DIR / f"{_key(url, params)}.bin"
    meta_path = path.with_suffix(".json")
    if not (path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - meta.get("ts", 0) > ttl:
        return None
    return path.read_bytes(), meta.get("headers", {})


def put(url: str, params: dict | None, content: bytes, headers: dict, ttl: float) -> None:
    if ttl <= 0:
        return
    CACHE_DIR.mkdir(exist_ok=True)
    key = _key(url, params)
    (CACHE_DIR / f"{key}.bin").write_bytes(content)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps({"ts": time.time(), "url": url, "headers": dict(headers)}),
        encoding="utf-8",
    )


def stats() -> dict:
    if not CACHE_DIR.exists():
        return {"entries": 0, "size_kb": 0}
    files = list(CACHE_DIR.glob("*.bin"))
    return {"entries": len(files), "size_kb": round(sum(f.stat().st_size for f in files) / 1024)}


def clear() -> int:
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.iterdir())
    for f in files:
        f.unlink()
    return len(files) // 2
