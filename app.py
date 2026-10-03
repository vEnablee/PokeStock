#!/usr/bin/env python3
"""Monitor disponibilita' ETB Pokemon a prezzo di listino.

Due modalita':
  CLI        python app.py --run            (usata da GitHub Actions)
             python app.py --dry-run        (nessuna notifica, stampa a video)
             python app.py --store ID       (un solo store, per debug)
             python app.py --seed           (riallinea lo stato senza notificare)
  Streamlit  streamlit run app.py           (dashboard)
             dashboard?cron=true            (esegue una scansione via query string)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from monitor import config as config_mod  # noqa: E402
from monitor import runner  # noqa: E402


# --------------------------------------------------------------------------- CLI

def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor ETB Pokemon a prezzo di listino")
    parser.add_argument("--run", action="store_true", help="esegue una scansione e invia le notifiche")
    parser.add_argument("--dry-run", action="store_true", help="scansiona ma stampa le notifiche invece di inviarle")
    parser.add_argument("--seed", action="store_true", help="registra lo stato corrente senza notificare nulla")
    parser.add_argument("--store", metavar="ID", help="limita la scansione a un singolo store")
    parser.add_argument("--config", default=None, help="percorso di stores.json")
    parser.add_argument("--list-stores", action="store_true", help="elenca gli store configurati ed esce")
    parser.add_argument("--json", action="store_true", help="stampa il riepilogo in JSON")
    parser.add_argument("--cache", nargs="?", const=3600, type=int, metavar="TTL",
                        help="usa la cache su disco (default 3600s): rilanci senza nuove richieste di rete")
    parser.add_argument("--clear-cache", action="store_true", help="svuota la cache e esce")
    parser.add_argument("--cache-stats", action="store_true", help="mostra lo stato della cache e esce")
    parser.add_argument("--limit", type=int, metavar="N", help="scansiona solo i primi N store (test leggeri)")
    args = parser.parse_args(argv)

    from monitor import cache as cache_mod

    if args.clear_cache:
        print(f"cache svuotata: {cache_mod.clear()} voci rimosse")
        return 0
    if args.cache_stats:
        print(f"cache: {cache_mod.stats()}")
        return 0

    try:
        cfg = config_mod.load(args.config)
    except FileNotFoundError:
        parser.error(f"file di configurazione non trovato: {args.config}")
    except ValueError as exc:
        parser.error(str(exc))

    if args.cache:
        cfg.settings["cache_ttl_seconds"] = args.cache
        print(f"[cache attiva: TTL {args.cache}s - le risposte gia' in cache non generano traffico]")
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit deve essere almeno 1 "
                         "(con 0 l'opzione veniva ignorata e partiva una scansione completa)")
        keep = {s["id"] for s in cfg.stores[: args.limit]}
        for store in cfg.raw["stores"]:
            if "_section" not in store and store["id"] not in keep:
                store["enabled"] = False
        # Il runner non puo' dedurlo da solo: dopo la disattivazione cfg.stores
        # contiene gia' solo gli store tenuti, e il run sembrerebbe completo.
        cfg.settings["_run_parziale"] = True
        print(f"[limite attivo: {len(cfg.stores)} store su {len(cfg.all_stores)}]")

    if args.list_stores:
        for s in cfg.all_stores:
            flag = "ON " if s.get("enabled") else "off"
            extra = "" if s.get("enabled") else f"  <- {s.get('disabled_reason', '')[:70]}"
            print(f"  [{flag}] {s['id']:22s} {s['type']:22s} {s['name']}{extra}")
        print(f"\n{len(cfg.stores)} attivi su {len(cfg.all_stores)} totali")
        return 0

    if not (args.run or args.dry_run or args.seed or args.store):
        parser.print_help()
        return 1

    summary = asyncio.run(runner.run(
        cfg, dry_run=args.dry_run, only_store=args.store, seed=args.seed,
    ))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------- Streamlit

def _credenziali_da_secrets() -> None:
    """Porta i secret di Streamlit nelle variabili d'ambiente.

    Tutto il resto del codice legge os.environ, mentre su Streamlit Cloud le
    credenziali arrivano da st.secrets: questo ponte evita di avere due
    percorsi diversi per la stessa cosa.
    """
    import os

    import streamlit as st
    for chiave in ("GIST_TOKEN", "GIST_ID", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(chiave):
            continue
        try:
            valore = st.secrets.get(chiave)
        except Exception:  # noqa: BLE001 - nessun file di secret: normale in locale
            valore = None
        if valore:
            os.environ[chiave] = str(valore)


def carica_stato(cfg) -> tuple[dict, str]:
    """Stato per la dashboard, con la fonte da cui arriva.

    Sul cloud il file locale non esiste (e' escluso dal repository), quindi la
    fonte e' il Gist scritto dal monitor. In locale si usa il file.
    """
    import json

    import streamlit as st

    from monitor import gist

    @st.cache_data(ttl=60, show_spinner=False)
    def _dal_gist(gist_id: str, _token: str) -> dict:
        return gist.GistStore(_token, gist_id).leggi()

    remoto = gist.da_ambiente()
    if remoto is not None and remoto.gist_id:
        try:
            dati = _dal_gist(remoto.gist_id, remoto.token)
            if dati:
                return dati, "gist"
        except Exception as exc:  # noqa: BLE001 - si ripiega sul file locale
            st.warning(f"Lettura del Gist fallita: {exc}")

    percorso = cfg.path_for("state_file")
    if percorso.exists():
        return json.loads(percorso.read_text(encoding="utf-8")), "file locale"
    return {}, "nessuna"


def main_streamlit() -> None:
    import json

    import streamlit as st

    from dashboard import components as C
    from dashboard import views
    from dashboard.icons import icon
    from dashboard.styles import CSS

    st.set_page_config(page_title="PokeStock", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    _credenziali_da_secrets()

    cfg = config_mod.load()

    # --- esecuzione via query string: dashboard?cron=true ---
    if st.query_params.get("cron") in ("true", "1"):
        with st.spinner("Scansione in corso..."):
            summary = asyncio.run(runner.run(cfg, verbose=False))
        st.success("Scansione completata")
        st.json(summary)
        st.caption("Streamlit Community Cloud va in sleep dopo un periodo di inattività: "
                   "questo endpoint va bene per una scansione su richiesta, non come scheduler.")
        return

    stato, fonte_stato = carica_stato(cfg)
    entries = list(stato.get("entries", {}).values())
    meta = stato.get("meta", {})
    ultimo = meta.get("last_run", {})
    # Per le metriche di copertura serve l'ultima scansione COMPLETA: un run
    # su un singolo negozio direbbe "1/1" e sarebbe fuorviante.
    ultimo_completo = meta.get("last_full_run", ultimo)

    # ---------------------------------------------------------------- sidebar
    etichette_target = {t["id"]: t["name"] for t in cfg.raw["targets"]}
    prezzi = [e["price"] for e in entries if e.get("price")]
    ci_sono_preordini = any(e.get("preorder") for e in entries)
    categorie_presenti = sorted({e.get("categoria") for e in entries if e.get("categoria")})

    with st.sidebar:
        st.markdown("### Controlli")

        # Le scorciatoie scrivono nella key del widget PRIMA che venga creato:
        # cosi' il termine resta nella casella e sopravvive agli altri filtri.
        scorciatoie = {"30° Anniv.": "anniversario", "Megaevol.": "megaevoluzione",
                       "Buio Pesto": "buio pesto", "Azzera": ""}
        if (rapida := st.session_state.pop("_ricerca_rapida", None)) is not None:
            st.session_state["ricerca"] = rapida

        q = st.text_input("Cerca prodotto", key="ricerca",
                          placeholder="30 anniversario, buio pesto, charizard…",
                          help="Cerca nel titolo e nel nome del negozio. "
                               "Ignora accenti e maiuscole: 'pokemon' trova 'Pokémon'. "
                               "Piu' parole = tutte devono comparire.")

        st.caption("Ricerche rapide")
        voci = list(scorciatoie.items())
        for i in range(0, len(voci), 2):
            # due per riga: con quattro colonne la sidebar tronca le etichette
            for col, (etichetta, termine) in zip(st.columns(2), voci[i:i + 2]):
                if col.button(etichetta, key=f"qs_{etichetta}", width="stretch"):
                    st.session_state["_ricerca_rapida"] = termine
                    st.rerun()

        target_sel = st.multiselect(
            "Espansione", sorted({e.get("target_id") for e in entries if e.get("target_id")}),
            default=[], format_func=lambda tid: etichette_target.get(tid, tid))

        # La multiselect categoria ha senso solo con piu' di una categoria:
        # con i soli target ETB attivi ne esiste una, e sarebbe un controllo morto.
        categorie = []
        if len(categorie_presenti) > 1:
            categorie = st.multiselect("Categoria", categorie_presenti, default=[])

        negozi_presenti = sorted({e.get("store_name") for e in entries if e.get("store_name")})
        negozi_sel = st.multiselect("Negozio", negozi_presenti, default=[])

        # BUG corretto: il default era 80 EUR e tagliava in silenzio tutto il resto,
        # anche dopo aver spento "solo entro MSRP". Ora parte dal massimo reale.
        # max(prezzi) potrebbe essere sotto il minimo dello slider (catalogo di soli
        # prodotti economici): Streamlit solleverebbe max_value < min_value.
        tetto = max(int(max(prezzi)) + 1 if prezzi else 200, 10)
        prezzo_max = st.slider("Prezzo massimo (€)", min_value=5, max_value=tetto,
                               value=tetto, step=5)

        opzioni_stato = ["Tutti", "Solo disponibili"]
        if ci_sono_preordini:
            opzioni_stato.append("Solo pre-ordini")
        stato_stock = st.radio("Disponibilità", opzioni_stato, index=1)
        if not ci_sono_preordini:
            st.caption("Nessun pre-ordine fra i prodotti trovati: l'opzione compare "
                       "quando un negozio ne espone uno.")

        solo_msrp = st.toggle("Solo entro soglia MSRP", value=True,
                              help="Nasconde i listini gonfiati, che restano registrati "
                                   "per il calcolo del risparmio.")
        ordine = st.selectbox("Ordina per",
                              ["Più convenienti", "Prezzo crescente", "Prezzo decrescente",
                               "Visti di recente"])
        limite = st.select_slider("Card mostrate", [24, 48, 60, 96, 200], value=60)

        st.divider()
        notifiche = st.toggle("Notifiche Telegram", value=False,
                              help="Se spento la scansione gira in dry-run: nessun messaggio inviato.")
        from monitor.notifier import Telegram
        if notifiche and not Telegram(cfg).configured:
            st.warning("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID non impostati: resta in dry-run.")
            notifiche = False

        scan = st.button("FORZA SCANSIONE ORA", type="primary", width="stretch")

        st.divider()
        st.caption(f"Dati letti da: {fonte_stato}")
        if fonte_stato == "nessuna":
            st.warning("Nessuno stato disponibile. In locale esegui una scansione; "
                       "sul cloud imposta i secret GIST_TOKEN e GIST_ID.")
        if ultimo:
            parziale = " (parziale)" if ultimo.get("partial") else ""
            st.caption(f"Ultimo run{parziale}: {ultimo.get('duration_s', 0)}s · "
                       f"{ultimo.get('stores_ok', 0)}/{ultimo.get('stores_total', 0)} negozi · "
                       f"{ultimo.get('notifications_sent', 0)} notifiche")
            if parziale and ultimo_completo is not ultimo:
                st.caption(f"Ultima completa: {ultimo_completo.get('stores_ok', 0)}/"
                           f"{ultimo_completo.get('stores_total', 0)} negozi")
        falliti = stato.get("store_failures", {})
        if falliti:
            from datetime import datetime as _dt, timezone as _tz

            def _eta(quando: str | None) -> str:
                if not quando:
                    return "data ignota"
                try:
                    minuti = int((_dt.now(_tz.utc) - _dt.fromisoformat(quando)).total_seconds() // 60)
                except (ValueError, TypeError):
                    return "data ignota"
                if minuti < 60:
                    return f"{minuti} min fa"
                return f"{minuti // 60} h fa" if minuti < 1440 else f"{minuti // 1440} g fa"

            righe = []
            for sid, v in falliti.items():
                # le versioni precedenti salvavano un intero nudo, senza data
                dati = v if isinstance(v, dict) else {"count": v}
                righe.append({
                    "nome": (cfg.store(sid) or {}).get("name", sid),
                    "conteggio": dati.get("count", 0),
                    "errore": (dati.get("errore") or "").split(":")[0][:40],
                    "eta": _eta(dati.get("quando")),
                })
            righe.sort(key=lambda r: -r["conteggio"])
            st.markdown(C.error_box(
                righe,
                "Spesso sono protezioni anti-bot o server offline. "
                "L'avviso Telegram parte solo dopo 5 fallimenti di fila."),
                unsafe_allow_html=True)

    # ------------------------------------------------------------------ header
    disponibili_msrp = sum(1 for e in entries if e.get("available") and e.get("within_msrp"))
    # Il timestamp e' in UTC: va convertito, altrimenti l'orario mostrato
    # e' sfasato rispetto all'orologio di chi guarda.
    aggiornato = "—"
    if ultimo.get("ts"):
        try:
            from datetime import datetime as _dt
            aggiornato = _dt.fromisoformat(ultimo["ts"]).astimezone().strftime("%H:%M")
        except (ValueError, TypeError):
            aggiornato = ultimo["ts"][11:16]

    st.markdown(C.topbar(
        "Poke", "Stock",
        f'<span class="meta">aggiornato alle {aggiornato} · '
        f'{ultimo_completo.get("stores_ok", 0)} negozi</span>'
        + C.live_badge(disponibili_msrp > 0,
                       f"{disponibili_msrp} a prezzo di listino"
                       if disponibili_msrp else "nessun drop attivo"),
    ), unsafe_allow_html=True)

    st.markdown(C.lede(
        "Ogni drop.", "Al prezzo giusto.",
        f"Monitoriamo <b>{len(cfg.stores)} negozi italiani</b> e avvisiamo quando un "
        f"<b>Elite Trainer Box</b> torna disponibile entro la soglia di listino."),
        unsafe_allow_html=True)

    # ------------------------------------------------------------------ scan
    # L'esito della scansione passa da session_state: st.success() seguito da
    # st.rerun() veniva cancellato dal rerun prima che l'utente potesse leggerlo.
    if (esito := st.session_state.pop("esito_scansione", None)):
        st.success(esito)

    if scan:
        placeholder = st.empty()
        placeholder.markdown(
            f'<div class="sec"><span class="spin">{icon("refresh")}</span>'
            f' Interrogazione dei negozi…</div>' + C.skeleton_grid(8),
            unsafe_allow_html=True)
        try:
            summary = asyncio.run(runner.run(cfg, dry_run=not notifiche, verbose=False))
            st.session_state["esito_scansione"] = (
                f"{summary['stores_ok']}/{summary['stores_total']} negozi · "
                f"{summary['products_scanned']:,} prodotti letti · "
                f"{summary['within_msrp']} entro MSRP · "
                f"{summary['notifications_sent']} notifiche"
                + ("" if notifiche else "  (dry-run: nessun messaggio inviato)"))
        except Exception as exc:  # noqa: BLE001 - l'errore va mostrato, non nascosto
            st.session_state["esito_scansione"] = None
            placeholder.empty()
            st.error(f"Scansione fallita: {type(exc).__name__}: {exc}")
            st.stop()
        placeholder.empty()
        st.rerun()

    filtri = {"q": q, "categorie": categorie, "negozi": negozi_sel, "target": target_sel,
              "prezzo_max": prezzo_max, "prezzo_tetto": tetto, "stato": stato_stock,
              "solo_msrp": solo_msrp, "limite": limite, "ordine": ordine}

    t1, t2, t3 = st.tabs(["LIVE DROPS", "STORICO & ANALYTICS", "NEGOZI & SOGLIE"])
    with t1:
        if not entries:
            st.markdown(C.empty_state("package", "Nessuna scansione ancora eseguita",
                                      "Premi «FORZA SCANSIONE ORA» oppure lancia: python app.py --dry-run"),
                        unsafe_allow_html=True)
        else:
            views.live_drops(cfg, entries, filtri, scanning=False, ultimo_run=ultimo_completo)
    with t2:
        views.analytics(cfg, entries, cfg.path_for("history_file"))
    with t3:
        views.negozi(cfg)


def _in_streamlit() -> bool:
    """True solo quando il file gira dentro `streamlit run`.

    suppress_warning evita il «missing ScriptRunContext!» che altrimenti
    sporca l'output della CLI a ogni invocazione.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        try:
            return get_script_run_ctx(suppress_warning=True) is not None
        except TypeError:  # versioni che non accettano il parametro
            return get_script_run_ctx() is not None
    except Exception:  # noqa: BLE001
        return False


if _in_streamlit():
    main_streamlit()
elif __name__ == "__main__":
    raise SystemExit(main_cli())
