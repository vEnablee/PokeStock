"""Stato persistente: decide COSA notificare.

Senza questo modulo, girando ogni 5 minuti riceveresti ~288 messaggi al giorno
per ogni prodotto disponibile. La regola e': si notifica solo la TRANSIZIONE
non-disponibile -> disponibile.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import Product


def now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class State:
    """Mappa prodotto -> ultimo stato osservato.

    Persistita su disco e, quando configurato, su un Gist: su GitHub Actions il
    filesystem e' effimero, quindi senza una memoria esterna ogni esecuzione
    ripartirebbe da zero e rispedirebbe notifiche per prodotti gia' visti.
    """

    def __init__(self, path: Path, remote=None):
        self.path = path
        self.remote = remote
        self.entries: dict[str, dict] = {}
        self.store_failures: dict[str, dict] = {}
        self.meta: dict = {}
        self.existed = path.exists()
        self.origine = "nuovo"

        # Il Gist ha la precedenza: e' la fonte condivisa fra le esecuzioni.
        if remote is not None:
            try:
                raw = remote.leggi()
                if raw:
                    self._carica(raw)
                    self.existed = True
                    self.origine = "gist"
                    return
            except Exception as exc:  # noqa: BLE001 - si ripiega sul file locale
                print(f"[stato] lettura del Gist fallita ({exc}); uso il file locale")

        if self.existed:
            try:
                self._carica(json.loads(path.read_text(encoding="utf-8")))
                self.origine = "locale"
            except (json.JSONDecodeError, OSError):
                # stato corrotto: si riparte da zero, ma NON si considera
                # un primo avvio, per non perdere la protezione anti-seed
                self.entries = {}
                self.origine = "corrotto"

    def _carica(self, raw: dict) -> None:
        self.entries = raw.get("entries", {})
        self.store_failures = raw.get("store_failures", {})
        self.meta = raw.get("meta", {})

    # ------------------------------------------------------------------ seed

    @property
    def is_first_run(self) -> bool:
        return not self.existed

    # ------------------------------------------------------------ decisione

    def should_notify(self, product: Product, renotify_after_hours: float) -> tuple[bool, str]:
        """(notificare?, motivo). Il motivo finisce nei log e nello storico."""
        prev = self.entries.get(product.key)

        if not product.available:
            return False, "non disponibile"

        if prev is None:
            return True, "nuovo prodotto disponibile"

        if not prev.get("available"):
            return True, "tornato disponibile"

        # era gia' disponibile: eventuale promemoria dopo N ore
        last = prev.get("last_notified")
        if not last:
            return False, "gia' disponibile, mai notificato (seed)"
        try:
            when = datetime.fromisoformat(last)
        except ValueError:
            return False, "timestamp illeggibile"
        if renotify_after_hours and now() - when >= timedelta(hours=renotify_after_hours):
            return True, f"ancora disponibile da oltre {renotify_after_hours:g}h"
        return False, "gia' notificato"

    # -------------------------------------------------------------- scrittura

    def record(self, product: Product, *, notified: bool, target_id: str | None = None,
               within_msrp: bool = True) -> None:
        prev = self.entries.get(product.key, {})
        price = product.price
        # min/max storici: alimentano il grafico e il calcolo del risparmio
        lo = prev.get("price_min")
        hi = prev.get("price_max")
        if price is not None:
            lo = price if lo is None else min(lo, price)
            hi = price if hi is None else max(hi, price)
        self.entries[product.key] = {
            "store_id": product.store_id,
            "store_name": product.store_name,
            "title": product.title,
            "url": product.url,
            "image": product.image or prev.get("image", ""),
            "price": price,
            "price_min": lo,
            "price_max": hi,
            "available": product.available,
            "preorder": product.is_preorder,
            "categoria": product.categoria,
            "within_msrp": within_msrp,
            "target_id": target_id or prev.get("target_id"),
            "first_seen": prev.get("first_seen") or _iso(now()),
            "last_seen": _iso(now()),
            "last_available": _iso(now()) if product.available else prev.get("last_available"),
            "last_notified": _iso(now()) if notified else prev.get("last_notified"),
        }

    def mark_store(self, store_id: str, ok: bool, errore: str | None = None,
                   soglia_quarantena: int = 4, giri_quarantena: int = 6) -> int:
        """Aggiorna i fallimenti consecutivi dello store e li restituisce.

        Registra anche QUANDO e PERCHE': senza data, un contatore rimasto appeso
        faceva comparire in dashboard store che nel frattempo si erano ripresi.
        """
        if ok:
            self.store_failures.pop(store_id, None)
            return 0
        prec = self.store_failures.get(store_id)
        count = (prec.get("count", 0) if isinstance(prec, dict) else (prec or 0)) + 1
        voce = {"count": count, "errore": (errore or "")[:160], "quando": _iso(now())}
        if isinstance(prec, dict) and prec.get("salta_restanti"):
            voce["salta_restanti"] = prec["salta_restanti"]
        if count >= soglia_quarantena > 0:
            # messo in quarantena: saltato per i prossimi giri, poi ritentato
            voce["salta_restanti"] = giri_quarantena
            voce["in_quarantena_dal"] = _iso(now())
        self.store_failures[store_id] = voce
        return count

    # ------------------------------------------------------------ quarantena

    def in_quarantena(self, store_id: str) -> bool:
        """True se lo store va saltato in questo giro.

        Dopo N fallimenti consecutivi non ha senso continuare a bussare: se e'
        un ban lo si peggiora, se e' offline si sprecano richieste e tempo.
        """
        v = self.store_failures.get(store_id)
        return isinstance(v, dict) and v.get("salta_restanti", 0) > 0

    def consuma_quarantena(self, store_id: str) -> int:
        """Scala di uno i giri di quarantena rimasti e restituisce quanti ne restano."""
        v = self.store_failures.get(store_id)
        if isinstance(v, dict) and v.get("salta_restanti", 0) > 0:
            v["salta_restanti"] -= 1
            return v["salta_restanti"]
        return 0

    def dimentica_store(self, store_ids) -> int:
        """Elimina i fallimenti di store che non vengono piu' scansionati
        (disattivati o rimossi dalla configurazione)."""
        via = [k for k in self.store_failures if k not in set(store_ids)]
        for k in via:
            del self.store_failures[k]
        return len(via)

    def drop_unmatched(self, scanned_store_ids: set[str], matched_keys: set[str]) -> int:
        """Rimuove i prodotti di store scansionati con successo che NON matchano piu'.

        Serve quando cambiano i filtri: senza, un falso positivo gia' registrato
        resterebbe a vita nello stato e nella dashboard.
        """
        stale = [
            key for key, entry in self.entries.items()
            if entry.get("store_id") in scanned_store_ids and key not in matched_keys
        ]
        for key in stale:
            del self.entries[key]
        return len(stale)

    def prune(self, seen_keys: Iterable[str], keep_days: int = 30) -> int:
        """Rimuove i prodotti spariti dai cataloghi da oltre keep_days."""
        seen = set(seen_keys)
        cutoff = now() - timedelta(days=keep_days)
        dropped = []
        for key, entry in self.entries.items():
            if key in seen:
                continue
            try:
                if datetime.fromisoformat(entry.get("last_seen", "")) < cutoff:
                    dropped.append(key)
            except ValueError:
                dropped.append(key)
        for key in dropped:
            del self.entries[key]
        return len(dropped)

    # ------------------------------------------------------------- allarmi

    def allarme_globale(self, scattato: bool, giri_richiesti: int,
                        ore_silenzio: float) -> bool:
        """True se va inviato l'allarme di blocco diffuso.

        Un solo giro storto non significa nulla: una disconnessione di pochi
        secondi sul runner fa fallire meta' dei negozi e poi tutto torna
        normale. Si avvisa solo se la condizione resiste per piu' giri di
        fila, e non si ripete finche' non rientra.
        """
        voce = self.meta.setdefault("allarme_globale", {})
        if not scattato:
            voce["giri_consecutivi"] = 0
            return False

        voce["giri_consecutivi"] = voce.get("giri_consecutivi", 0) + 1
        if voce["giri_consecutivi"] < giri_richiesti:
            return False

        ultimo = voce.get("ultimo_invio")
        if ultimo:
            try:
                if now() - datetime.fromisoformat(ultimo) < timedelta(hours=ore_silenzio):
                    return False
            except ValueError:
                pass
        voce["ultimo_invio"] = _iso(now())
        return True

    def avviso_store_dovuto(self, store_id: str, ore_silenzio: float) -> bool:
        """True se si puo' avvisare per questo store senza ripetersi troppo."""
        voce = self.store_failures.get(store_id)
        if not isinstance(voce, dict):
            return True
        ultimo = voce.get("ultimo_avviso")
        if ultimo:
            try:
                if now() - datetime.fromisoformat(ultimo) < timedelta(hours=ore_silenzio):
                    return False
            except ValueError:
                pass
        voce["ultimo_avviso"] = _iso(now())
        return True

    # ----------------------------------------------------------- preferenze

    def preferenze(self, predefinite: dict | None = None) -> dict:
        """Preferenze di notifica, con i valori di partenza come riserva.

        Vivono nello stato, quindi sul Gist: e' l'unico punto che la dashboard
        e il monitor su Actions condividono davvero.
        """
        base = dict(predefinite or {})
        base.update(self.meta.get("preferenze") or {})
        base.setdefault("notifiche_attive", True)
        base.setdefault("target_notificati", None)
        return base

    def imposta_preferenze(self, valori: dict) -> None:
        pref = self.meta.setdefault("preferenze", {})
        pref.update(valori)
        pref["aggiornate_il"] = _iso(now())

    def payload(self) -> dict:
        """Lo stato serializzabile, identico a cio' che finisce su disco."""
        return {"meta": self.meta, "store_failures": self.store_failures,
                "entries": self.entries}

    def save(self, run_summary: dict | None = None) -> None:
        if run_summary:
            self.meta["last_run"] = run_summary
            # I run parziali (--store, --limit) non devono sovrascrivere le
            # statistiche della copertura completa: falserebbero la dashboard.
            if not run_summary.get("partial"):
                self.meta["last_full_run"] = run_summary
        payload = self.payload()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)  # scrittura atomica: niente stato mezzo scritto


def append_history(path: Path, record: dict, max_righe: int = 20000) -> None:
    """Aggiunge una riga allo storico, tenendolo sotto una soglia.

    Lo storico cresce di una riga per prodotto per scansione: a 10 minuti di
    cadenza sono centinaia di migliaia di righe al mese. Oltre `max_righe`
    il file viene potato tenendo le piu' recenti.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # il controllo costa una stat: si pota solo quando il file e' davvero grande
    if path.stat().st_size < 4_000_000:
        return
    righe = path.read_text(encoding="utf-8").splitlines()
    if len(righe) > max_righe:
        path.write_text("\n".join(righe[-max_righe:]) + "\n", encoding="utf-8")
