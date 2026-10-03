"""Test offline: nessuna richiesta di rete.

Ogni caso qui sotto e' un falso positivo REALE osservato interrogando i negozi
il 2026-10-02, prima di introdurre il match a confine di parola.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor import config  # noqa: E402
from monitor.adapters import _price  # noqa: E402
from monitor.matching import classify, matches_target, normalize  # noqa: E402

cfg = config.load()
TARGETS = cfg.targets
F = cfg.filters


def check(label, cond):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
    return cond


def main() -> int:
    ok = True

    print("Falsi positivi da match a sottostringa (devono essere RESPINTI):")
    for title in [
        "TOPOLINO libretto n. 3039 (Copertina Speciale)",
        "MARTINELIA Yummy Nail Art Set Sweet Shop - POS230138",
        "Bacchetta Magica di Harry Potter - 30cm De Agostini",
        "Case in Plexiglas con chiusura magnetica per ETB",
        "Bustina ST30 - Starter Deck EX Luffy & Ace Bonus Pack",
        "Album e/o Bustine di Figurine Dylan Dog 40 Anniversario",
        "Tin 25th Anniversario: Eroi Duellanti TN23 Edizione",
        "Pokemon Elite Trainer Box Journey Together English",
        "ACRYLIC BOX PROTEZIONE POKEMON SET ALLENATORE FUORICLASSE",
        "Acrylic Box Protezione Pokemon ETB",
    ]:
        ok &= check(title[:58], classify(title, 59.90, TARGETS, F) is None)

    print("\nProdotti veri (devono essere ACCETTATI, con il target giusto):")
    expected = {
        "30esimo Anniversario Set Allenatore Fuoriclasse (IT)": "etb_30th",
        "Pokemon - 30th Anniversario - Set Allenatore Fuoriclasse ITA": "etb_30th",
        "Set Allenatore Fuoriclasse Megaevoluzione Buio Pesto (IT)": "etb_megaevoluzione",
        "Pokemon Scintille Folgoranti Set Allenatore Fuoriclasse": "etb_qualsiasi",
    }
    for title, want in expected.items():
        got = classify(title, 59.90, TARGETS, F)
        ok &= check(f"{title[:50]:52s} -> {got['id'] if got else None}", got is not None and got["id"] == want)

    print("\nFiltro prezzo (soglia MSRP):")
    etb = "30esimo Anniversario Set Allenatore Fuoriclasse (IT)"
    ok &= check("59,90 accettato", classify(etb, 59.90, TARGETS, F) is not None)
    ok &= check("64,90 accettato (limite)", classify(etb, 64.90, TARGETS, F) is not None)
    ok &= check("65,00 respinto", classify(etb, 65.00, TARGETS, F) is None)
    ok &= check("144,90 da scalper respinto", classify(etb, 144.90, TARGETS, F) is None)
    ok &= check("0,01 civetta respinto", classify(etb, 0.01, TARGETS, F) is None)

    print("\nParsing prezzi europei:")
    for raw, want in [("59,90", 59.9), ("1.234,50", 1234.5), ("1,234.50", 1234.5), ("EUR 64,90", 64.9)]:
        ok &= check(f"{raw!r} -> {_price(raw)}", _price(raw) == want)

    print("\nNormalizzazione accenti:")
    ok &= check("Pokémon == pokemon", normalize("Pokémon") == "pokemon")
    ok &= check("30° riconosciuto", matches_target("Pokémon 30° Anniversario Set Allenatore Fuoriclasse",
                                                    cfg.target("etb_30th"), F))

    print("\nRISULTATO:", "tutti i test passano" if ok else "CI SONO FALLIMENTI")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
