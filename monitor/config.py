"""Caricamento e validazione di stores.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "stores.json"


@dataclass
class Config:
    raw: dict[str, Any]
    path: Path

    @property
    def settings(self) -> dict:
        return self.raw["settings"]

    @property
    def filters(self) -> dict:
        return self.raw["filters"]

    @property
    def telegram(self) -> dict:
        return self.raw.get("telegram", {})

    @property
    def endpoints(self) -> dict:
        return self.raw.get("platform_endpoints", {})

    @property
    def targets(self) -> list[dict]:
        """Target attivi, ordinati per priorita' crescente (1 = piu' importante)."""
        return sorted(
            (t for t in self.raw["targets"] if t.get("enabled")),
            key=lambda t: t.get("priority", 99),
        )

    @property
    def stores(self) -> list[dict]:
        """Store abilitati. Le voci '_section' sono separatori leggibili, non store."""
        return [
            s for s in self.raw["stores"]
            if "_section" not in s and s.get("enabled")
        ]

    @property
    def all_stores(self) -> list[dict]:
        return [s for s in self.raw["stores"] if "_section" not in s]

    def store(self, store_id: str) -> dict | None:
        return next((s for s in self.all_stores if s["id"] == store_id), None)

    def setting(self, key: str, store: dict | None = None, default=None):
        """Valore di impostazione, con override per-store."""
        if store is not None and key in store:
            return store[key]
        return self.settings.get(key, default)

    def target(self, target_id: str) -> dict | None:
        return next((t for t in self.raw["targets"] if t["id"] == target_id), None)

    def path_for(self, key: str) -> Path:
        """Risolve un percorso di file dalla config, relativo alla radice del progetto."""
        return ROOT / self.settings[key]


def load(path: str | Path | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as fh:
        raw = json.load(fh)
    _validate(raw, p)
    return Config(raw=raw, path=p)


def _validate(raw: dict, p: Path) -> None:
    for key in ("settings", "filters", "targets", "stores"):
        if key not in raw:
            raise ValueError(f"{p}: manca la sezione obbligatoria '{key}'")

    if raw["settings"].get("match_mode") != "word_boundary":
        raise ValueError(
            f"{p}: settings.match_mode deve essere 'word_boundary'. Il match a sottostringa "
            "produce falsi positivi verificati ('tin' dentro 'bustine', '30' dentro '3039')."
        )

    for t in raw["targets"]:
        for key in ("id", "name", "max_price_eur", "must_contain_any_groups"):
            if key not in t:
                raise ValueError(f"{p}: target '{t.get('id', '?')}' senza '{key}'")

    seen: set[str] = set()
    for s in raw["stores"]:
        if "_section" in s:
            continue
        if s["id"] in seen:
            raise ValueError(f"{p}: id store duplicato '{s['id']}'")
        seen.add(s["id"])
        if s.get("enabled") and "type" not in s:
            raise ValueError(f"{p}: store '{s['id']}' abilitato ma senza 'type'")
