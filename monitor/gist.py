"""Persistenza dello stato su un GitHub Gist.

Su GitHub Actions il filesystem e' effimero: senza una memoria esterna, ogni
run ripartirebbe da zero e rispedirebbe notifiche per prodotti gia' visti.
Il Gist e' quella memoria: letto a inizio run, riscritto alla fine.

Il contenuto viene compresso: lo stato in chiaro e' circa 390 KB e cresce con
i prodotti tracciati, mentre compresso sta sui 37 KB, ben dentro il limite
pratico di un file di Gist.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
from typing import Any

import httpx

API = "https://api.github.com"
NOME_FILE = "stato.json.gz.b64"
TIMEOUT = 30


class GistError(RuntimeError):
    pass


def comprimi(dati: dict[str, Any]) -> str:
    crudo = json.dumps(dati, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(crudo, 9)).decode("ascii")


def decomprimi(contenuto: str) -> dict[str, Any]:
    testo = contenuto.strip()
    if not testo:
        return {}
    try:
        return json.loads(gzip.decompress(base64.b64decode(testo)).decode("utf-8"))
    except Exception:
        # tolleranza: un Gist scritto in chiaro da una versione precedente
        try:
            return json.loads(testo)
        except json.JSONDecodeError as exc:
            raise GistError(f"contenuto del Gist illeggibile: {exc}") from exc


class GistStore:
    """Lettura e scrittura dello stato su un Gist privato."""

    def __init__(self, token: str, gist_id: str = "") -> None:
        if not token:
            raise GistError("GIST_TOKEN assente")
        self.token = token
        self.gist_id = gist_id

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pokestock",
        }

    def _chiama(self, metodo: str, url: str, **kw) -> httpx.Response:
        try:
            r = httpx.request(metodo, url, headers=self._headers, timeout=TIMEOUT, **kw)
        except httpx.HTTPError as exc:
            raise GistError(f"GitHub non raggiungibile: {exc}") from exc
        if r.status_code == 401:
            raise GistError("GIST_TOKEN rifiutato (401): serve un token con permesso 'gist'.")
        if r.status_code == 404:
            raise GistError(f"Gist {self.gist_id} non trovato (404): controlla GIST_ID.")
        if r.status_code >= 400:
            raise GistError(f"GitHub ha risposto {r.status_code}: {r.text[:160]}")
        return r

    def leggi(self) -> dict[str, Any]:
        """Stato salvato, o {} se il Gist e' nuovo o vuoto."""
        if not self.gist_id:
            return {}
        dati = self._chiama("GET", f"{API}/gists/{self.gist_id}").json()
        file = (dati.get("files") or {}).get(NOME_FILE)
        if not file:
            return {}
        contenuto = file.get("content") or ""
        # oltre ~1 MB GitHub tronca il contenuto inline e offre raw_url
        if file.get("truncated") and file.get("raw_url"):
            contenuto = self._chiama("GET", file["raw_url"]).text
        return decomprimi(contenuto)

    def scrivi(self, stato: dict[str, Any], descrizione: str = "") -> None:
        if not self.gist_id:
            raise GistError("GIST_ID assente: usa crea() per generarne uno.")
        corpo = {"files": {NOME_FILE: {"content": comprimi(stato)}}}
        if descrizione:
            corpo["description"] = descrizione[:200]
        self._chiama("PATCH", f"{API}/gists/{self.gist_id}", json=corpo)

    def crea(self, stato: dict[str, Any]) -> str:
        """Crea un Gist privato e ne restituisce l'id, da salvare come secret."""
        r = self._chiama("POST", f"{API}/gists", json={
            "description": "Stato di PokeStock",
            "public": False,
            "files": {NOME_FILE: {"content": comprimi(stato)}},
        })
        self.gist_id = r.json()["id"]
        return self.gist_id


def da_ambiente() -> GistStore | None:
    """GistStore configurato dalle variabili d'ambiente, o None se assenti.

    None non e' un errore: in locale lo stato resta su disco.
    """
    token = os.environ.get("GIST_TOKEN", "").strip()
    if not token:
        return None
    return GistStore(token, os.environ.get("GIST_ID", "").strip())
