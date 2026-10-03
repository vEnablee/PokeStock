"""Tipi condivisi fra adapter, runner e dashboard."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Categorie derivate dal titolo, usate dai filtri della dashboard.
# L'ordine conta: la prima che matcha vince.
CATEGORIE = [
    ("Set Allenatore / ETB", ("fuoriclasse", "elite trainer", "etb")),
    ("Box Sigillati",        ("display", "booster box", "play booster", "36 buste", "18 buste")),
    ("Tin Box",              ("tin", "tins", "latta", "latte")),
    ("Collezioni",           ("collezione", "premium", "raccoglitore", "poster", "mazzo")),
    ("Bustine",              ("bustina", "bustine", "busta", "buste", "blister", "bundle")),
]

_PREORDER = re.compile(r"\b(pre[ -]?order|pre[ -]?ordine|preordine|prenota)\b", re.I)


def categoria(title: str) -> str:
    low = title.lower()
    for nome, parole in CATEGORIE:
        if any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", low) for p in parole):
            return nome
    return "Altro"


@dataclass(frozen=True)
class Product:
    store_id: str
    store_name: str
    title: str
    price: float | None
    available: bool
    url: str
    image: str = ""
    preorder: bool = False

    @property
    def key(self) -> str:
        """Identita' stabile di un prodotto presso uno store.

        Usa l'URL quando c'e' (resta valido anche se il negozio ritocca il titolo),
        altrimenti ricade sul titolo.
        """
        basis = self.url or self.title
        return f"{self.store_id}|{hashlib.sha1(basis.encode('utf-8')).hexdigest()[:16]}"

    @property
    def categoria(self) -> str:
        return categoria(self.title)

    @property
    def is_preorder(self) -> bool:
        return self.preorder or bool(_PREORDER.search(self.title))


@dataclass
class StoreResult:
    store_id: str
    products: list[Product] = field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None
