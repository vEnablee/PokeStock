"""Rete di sicurezza per GitHub Actions.

    python -m monitor --upload

Carica sul Gist lo stato locale. Il workflow lo esegue con `if: always()`:
se il run principale e' morto a meta', lo stato su disco esiste comunque
(state.save() avviene in coda al run) ma potrebbe non essere arrivato sul
Gist. Se e' gia' stato caricato, questo passaggio e' innocuo.
"""
from __future__ import annotations

import sys

from . import gist
from .config import load


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--upload" not in argv:
        print("uso: python -m monitor --upload")
        return 2

    remoto = gist.da_ambiente()
    if remoto is None:
        print("[stato] GIST_TOKEN assente: niente da caricare")
        return 0

    cfg = load()
    percorso = cfg.path_for("state_file")
    if not percorso.exists():
        print("[stato] nessuno stato locale da caricare")
        return 0

    import json
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    try:
        if not remoto.gist_id:
            nuovo = remoto.crea(dati)
            print(f"[stato] creato un Gist nuovo: {nuovo}")
            print(f"::notice::Salva questo id come secret GIST_ID: {nuovo}")
        else:
            remoto.scrivi(dati, descrizione="salvataggio di sicurezza")
            print("[stato] caricato sul Gist")
    except gist.GistError as exc:
        print(f"[stato] caricamento fallito: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
