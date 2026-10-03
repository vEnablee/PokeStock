"""Matching titoli prodotto contro i target di stores.json.

Regola non negoziabile: match a CONFINE DI PAROLA. Il match a sottostringa
produce falsi positivi verificati sul campo il 2026-10-02:
  'tin' dentro 'busTINe' / 'MarTINelia' / 'VicTINi'
  '30'  dentro '3039' (Topolino) / '30cm' / 'POS230138'
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_WS = re.compile(r"\s+")


@lru_cache(maxsize=8192)
def normalize(text: str) -> str:
    """Minuscole, diacritici rimossi, spazi collassati. Applicata a titoli e keyword."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WS.sub(" ", stripped).strip()


@lru_cache(maxsize=8192)
def _pattern(keyword: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(normalize(keyword)) + r"(?!\w)")


def contains(normalized_title: str, keyword: str) -> bool:
    """True se la keyword compare come parola intera nel titolo gia' normalizzato.

    Nota: con questa regola '30' NON matcha '30th' ne' '30esimo' (cifra seguita da
    lettera = nessun confine di parola). Per questo stores.json elenca le varianti
    separatamente dentro ogni gruppo.
    """
    return _pattern(keyword).search(normalized_title) is not None


def matches_target(title: str, target: dict, global_filters: dict) -> bool:
    """Valuta un titolo contro un target.

    must_contain_all        -> tutte presenti          (AND)
    must_contain_any_groups -> almeno una per gruppo   (gruppi in AND, keyword in OR)
    must_not_contain        -> una sola presenza scarta
    filters.exclude_keywords-> esclusioni globali, applicate per prime
    """
    n = normalize(title)

    for kw in global_filters.get("exclude_keywords", ()):
        if contains(n, kw):
            return False

    for kw in target.get("must_not_contain", ()):
        if contains(n, kw):
            return False

    for kw in target.get("must_contain_all", ()):
        if not contains(n, kw):
            return False

    for group in target.get("must_contain_any_groups", ()):
        if not any(contains(n, kw) for kw in group):
            return False

    return True


def price_in_range(price: float | None, target: dict, global_filters: dict) -> bool:
    if price is None:
        return False
    floor = global_filters.get("min_price_eur", 0.0)
    return floor <= price <= target["max_price_eur"]


def classify_keywords(title: str, targets: list[dict], global_filters: dict) -> dict | None:
    """Primo target che accetta il TITOLO, ignorando il prezzo.

    Separare le due fasi serve a registrare anche i prodotti sopra soglia MSRP:
    senza di loro non si puo' calcolare quanto si risparmia rispetto a chi
    specula, ne' disegnare la dispersione dei prezzi fra negozi.
    """
    for t in targets:
        if matches_target(title, t, global_filters):
            return t
    return None


def classify(title: str, price: float | None, targets: list[dict], global_filters: dict) -> dict | None:
    """Primo target (gia' ordinato per priorita') che accetta titolo e prezzo.

    Restituendo solo il primo match implementa di fatto 'dedupe_across_targets':
    un ETB 30deg soddisfa sia etb_30th sia etb_qualsiasi, ma viene attribuito
    al target a priority piu' bassa e notificato una volta sola.
    """
    for t in targets:
        if matches_target(title, t, global_filters) and price_in_range(price, t, global_filters):
            return t
    return None
