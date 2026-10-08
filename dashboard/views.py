"""Le tre schede della dashboard."""
from __future__ import annotations

import json
import shutil
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from monitor.matching import normalize

from . import components as C

def layout(**extra) -> dict:
    """PLOT_LAYOUT fuso con sovrascritture per-grafico.

    Serve perche' update_layout(**PLOT_LAYOUT, yaxis=...) passerebbe 'yaxis'
    due volte e solleva TypeError.
    """
    base = {k: (v.copy() if isinstance(v, dict) else v) for k, v in PLOT_LAYOUT.items()}
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


VERDE, AMBRA, CIANO = "#10E07E", "#F5A524", "#38BDF8"

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#A3ABBA", family="Inter", size=12),
    margin=dict(l=10, r=10, t=36, b=10),
    xaxis=dict(gridcolor="rgba(255,255,255,.055)", zerolinecolor="rgba(255,255,255,.09)",
               linecolor="rgba(255,255,255,.09)"),
    yaxis=dict(gridcolor="rgba(255,255,255,.055)", zerolinecolor="rgba(255,255,255,.09)",
               linecolor="rgba(255,255,255,.09)"),
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.12, x=0),
    hoverlabel=dict(bgcolor="#15181F", bordercolor="rgba(255,255,255,.14)",
                    font=dict(color="#F2F4F8", family="Inter")),
)


# --------------------------------------------------------------------- utility

def riferimento_scalper(entries: list[dict], target_id: str) -> float | None:
    """Prezzo di mercato 'da rivendita' per un target.

    E' la MEDIANA dei listini sopra soglia MSRP per quello stesso target.
    Usare il massimo assoluto sarebbe disonesto: un singolo annuncio a 2.300 EUR
    gonfierebbe il risparmio in modo ridicolo. La mediana descrive il prezzo
    che si paga davvero se non si prende il prodotto a listino.
    """
    sopra = [e["price"] for e in entries
             if e.get("target_id") == target_id and not e.get("within_msrp") and e.get("price")]
    return statistics.median(sopra) if len(sopra) >= 3 else None


def calcola_risparmio(entries: list[dict]) -> tuple[float, int]:
    """(risparmio totale stimato, numero di prodotti su cui e' calcolato)."""
    rif: dict[str, float | None] = {}
    totale, n = 0.0, 0
    for e in entries:
        if not (e.get("available") and e.get("within_msrp") and e.get("price")):
            continue
        tid = e.get("target_id")
        if tid not in rif:
            rif[tid] = riferimento_scalper(entries, tid)
        if rif[tid]:
            diff = rif[tid] - e["price"]
            if diff > 0:
                totale += diff
                n += 1
    return totale, n


# ------------------------------------------------------------------ LIVE DROPS

def live_drops(cfg, entries: list[dict], filtri: dict, scanning: bool,
               ultimo_run: dict | None = None) -> None:
    store_type = {s["id"]: s.get("type", "") for s in cfg.all_stores}
    msrp = {t["id"]: t.get("msrp_eur") for t in cfg.raw["targets"]}

    ultimo_run = ultimo_run or {}
    ok_scan = ultimo_run.get("stores_ok", 0)
    tot_scan = ultimo_run.get("stores_total", 0)
    con_prodotti = len({e.get("store_id") for e in entries if e.get("store_id")})

    disponibili = [e for e in entries if e.get("available")]
    in_msrp = [e for e in disponibili if e.get("within_msrp")]
    risparmio, su_quanti = calcola_risparmio(entries)

    st.markdown(C.kpi_row([
        {"label": "Prodotti monitorati", "value": f"{len(entries)}",
         "sub": f"su {len(cfg.stores)} negozi attivi", "tone": "k1"},
        {"label": "Disponibili a MSRP", "value": f"{len(in_msrp)}",
         "sub": f"{len(disponibili)} disponibili in totale", "tone": "k2"},
        {"label": "Negozi raggiunti", "value": f"{ok_scan}/{tot_scan}" if tot_scan else "—",
         "sub": (f"{con_prodotti} hanno ETB in catalogo"
                 if con_prodotti else "nessuna scansione registrata"), "tone": "k3"},
        {"label": "Risparmio stimato", "value": C.eur(risparmio) if risparmio else "—",
         "sub": (f"su {su_quanti} prodotti, vs mediana dei listini sopra MSRP"
                 if su_quanti else "servono piu' dati di mercato"), "tone": "k4"},
    ]), unsafe_allow_html=True)

    if scanning:
        st.markdown(C.section("Scansione in corso", nome_icona="refresh"), unsafe_allow_html=True)
        st.markdown(C.skeleton_grid(8), unsafe_allow_html=True)
        return

    visibili = applica_filtri(entries, filtri)

    # Avvisa quando un filtro sta nascondendo risultati: prima lo slider prezzo
    # tagliava in silenzio e sembrava che i prodotti non esistessero.
    if filtri.get("solo_msrp"):
        nascosti = sum(1 for e in entries if not e.get("within_msrp"))
        if nascosti:
            st.markdown(C.notice(
                f"{nascosti} prodotti sopra la soglia MSRP sono nascosti dal filtro "
                f"«Solo entro soglia MSRP». Restano registrati per il calcolo del risparmio."),
                unsafe_allow_html=True)
    tetto = filtri.get("prezzo_tetto")
    if tetto and filtri.get("prezzo_max", tetto) < tetto:
        fuori = sum(1 for e in entries
                    if e.get("price") and e["price"] > filtri["prezzo_max"])
        if fuori:
            st.markdown(C.notice(
                f"Lo slider prezzo (max {filtri['prezzo_max']} €) nasconde altri {fuori} prodotti."),
                unsafe_allow_html=True)

    st.markdown(C.section("Live drops", f"{len(visibili)} risultati", "activity"),
                unsafe_allow_html=True)

    if not visibili:
        st.markdown(C.empty_state("search", "Nessun prodotto con questi filtri",
                                  "Qui sotto quale filtro sta escludendo cosa."),
                    unsafe_allow_html=True)
        for riga in diagnosi_filtri(entries, filtri):
            st.markdown(C.notice(riga), unsafe_allow_html=True)
        return

    ordine = filtri.get("ordine", "Più convenienti")
    visibili.sort(key=ORDINAMENTI.get(ordine, ORDINAMENTI["Più convenienti"]),
                  reverse=(ordine == "Visti di recente"))
    limite = filtri.get("limite", 60)
    # Il riferimento di mercato (mediana dei listini sopra soglia) si calcola una
    # volta per target, non per card: con 60 card sarebbe tempo sprecato.
    mercato = {tid: riferimento_scalper(entries, tid)
               for tid in {e.get("target_id") for e in visibili[:limite]}}
    cards = [
        C.product_card(e, msrp=msrp.get(e.get("target_id")),
                       mercato=mercato.get(e.get("target_id")),
                       platform=store_type.get(e.get("store_id"), ""),
                       delay=min(i, 12) * 0.03)
        for i, e in enumerate(visibili[:limite])
    ]
    st.markdown(C.grid(cards), unsafe_allow_html=True)
    if len(visibili) > limite:
        st.caption(f"Mostrati {limite} di {len(visibili)}. Alza il limite nella barra laterale.")


def applica_filtri(entries: list[dict], f: dict) -> list[dict]:
    out = []
    # normalize() toglie accenti e maiuscole: cercando "pokemon" si trova "Pokémon",
    # cercando "30" si trova "30°".
    q = normalize(f.get("q") or "").strip()
    for e in entries:
        if q:
            testo = normalize(f"{e.get('title', '')} {e.get('store_name', '')}")
            if not all(parola in testo for parola in q.split()):
                continue
        if f.get("target") and e.get("target_id") not in f["target"]:
            continue
        if f.get("categorie") and e.get("categoria") not in f["categorie"]:
            continue
        if f.get("negozi") and e.get("store_name") not in f["negozi"]:
            continue
        prezzo = e.get("price")
        if prezzo is not None and prezzo > f.get("prezzo_max", 1e9):
            continue
        stato = f.get("stato", "Tutti")
        if stato == "Solo disponibili" and not e.get("available"):
            continue
        if stato == "Solo pre-ordini" and not e.get("preorder"):
            continue
        if f.get("solo_msrp") and not e.get("within_msrp"):
            continue
        out.append(e)
    return out


def diagnosi_filtri(entries: list[dict], f: dict) -> list[str]:
    """Spiega perche' la griglia e' vuota, togliendo un filtro alla volta.

    Senza questo, «0 risultati» sembra un bug: in realta' puo' voler dire che
    quel prodotto esiste ma e' esaurito, oppure che e' in vendita solo sopra MSRP.
    """
    if not entries:
        return ["Nessun prodotto in archivio: esegui una scansione."]

    etichette = {
        "q": "la ricerca testuale",
        "target": "il filtro Espansione",
        "categorie": "il filtro Categoria",
        "negozi": "il filtro Negozio",
        "prezzo_max": "lo slider del prezzo",
        "stato": "il filtro Disponibilità",
        "solo_msrp": "il toggle «Solo entro soglia MSRP»",
    }
    neutro = {"q": "", "target": [], "categorie": [], "negozi": [],
              "prezzo_max": f.get("prezzo_tetto") or 10**9,
              "stato": "Tutti", "solo_msrp": False}

    righe = []
    for chiave, valore_neutro in neutro.items():
        attivo = f.get(chiave) not in (None, "", [], valore_neutro)
        if not attivo:
            continue
        rilassato = dict(f)
        rilassato[chiave] = valore_neutro
        quanti = len(applica_filtri(entries, rilassato))
        if quanti:
            righe.append(f"Togliendo {etichette[chiave]} comparirebbero {quanti} prodotti.")
    if not righe:
        righe.append("Nessun singolo filtro basta: provane a togliere due insieme, "
                     "oppure il prodotto non e' presente in archivio.")
    return righe


ORDINAMENTI = {
    "Più convenienti":   lambda e: (not e.get("available"), not e.get("within_msrp"),
                                    e.get("price") or 1e9),
    "Prezzo crescente":  lambda e: e.get("price") or 1e9,
    "Prezzo decrescente": lambda e: -(e.get("price") or 0),
    "Visti di recente":  lambda e: e.get("last_seen") or "",
}


# -------------------------------------------------------------------- ANALYTICS

def analytics(cfg, entries: list[dict], history_path: Path) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    if not entries:
        st.markdown(C.empty_state("chart", "Nessun dato", "Esegui una scansione."), unsafe_allow_html=True)
        return

    df = pd.DataFrame(entries)
    # Voci salvate da versioni precedenti possono non avere tutte le colonne:
    # senza questo, groupby("store_name") solleverebbe KeyError.
    for colonna, default in (("price", None), ("store_name", "—"), ("available", False),
                             ("within_msrp", False), ("target_id", "—"), ("title", "")):
        if colonna not in df:
            df[colonna] = default
    df = df[df["price"].notna()]
    if df.empty:
        st.markdown(C.empty_state("chart", "Nessun prezzo rilevato",
                                  "I prodotti trovati non espongono un prezzo leggibile."),
                    unsafe_allow_html=True)
        return

    st.markdown(C.section("Dispersione dei prezzi per target", nome_icona="chart"),
                unsafe_allow_html=True)
    st.caption("Ogni punto e' un negozio. La linea tratteggiata e' la soglia MSRP: "
               "tutto cio' che sta sopra e' ricarico.")

    df = df.assign(fascia=df["within_msrp"].fillna(False)
                   .map({True: "Entro MSRP", False: "Sopra MSRP"}))
    fig = px.strip(df, x="target_id", y="price", color="fascia",
                   hover_data=["store_name", "title"],
                   color_discrete_map={"Entro MSRP": VERDE, "Sopra MSRP": AMBRA},
                   labels={"target_id": "", "price": "Prezzo (€)", "fascia": ""})
    fig.update_traces(marker=dict(size=9, opacity=.85,
                                  line=dict(width=1, color="rgba(11,13,18,.85)")),
                      jitter=.45)
    soglie = {t["max_price_eur"] for t in cfg.raw["targets"] if t.get("enabled")}
    for soglia in soglie:
        fig.add_hline(y=soglia, line_dash="dash", line_color=CIANO, line_width=1.4,
                      annotation_text=f"soglia MSRP {soglia:.2f} €",
                      annotation_position="top left",
                      annotation_font=dict(color=CIANO, size=11))
    fig.update_layout(**layout(height=420))
    tetto = df["price"].quantile(0.97) * 1.15
    if pd.notna(tetto) and tetto > 0:
        fig.update_yaxes(range=[0, min(tetto, df["price"].max())])
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(C.section("Disponibilita' per negozio", nome_icona="store"),
                    unsafe_allow_html=True)
        per_store = (df.groupby("store_name")
                       .agg(disponibili=("available", "sum"), totale=("available", "size"))
                       .sort_values("disponibili", ascending=False).head(15).reset_index())
        f2 = go.Figure()
        f2.add_bar(y=per_store["store_name"], x=per_store["disponibili"], orientation="h",
                   name="disponibili", marker_color=VERDE,
                   marker_line=dict(width=0), hovertemplate="%{y}: %{x} disponibili<extra></extra>")
        f2.add_bar(y=per_store["store_name"], x=per_store["totale"] - per_store["disponibili"],
                   orientation="h", name="esauriti", marker_color="rgba(255,255,255,.10)",
                   marker_line=dict(width=0), hovertemplate="%{y}: %{x} esauriti<extra></extra>")
        f2.update_layout(**layout(barmode="stack", height=430, bargap=.34,
                                  yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)")))
        st.plotly_chart(f2, width="stretch")
    with c2:
        st.markdown(C.section("Prezzo minimo per target", nome_icona="tag"),
                    unsafe_allow_html=True)
        best = (df[df["available"]].groupby("target_id")["price"]
                  .agg(["min", "median", "max", "count"]).reset_index())
        best = best.rename(columns={"target_id": "Target", "min": "Minimo",
                                    "median": "Mediana", "max": "Massimo", "count": "Offerte"})
        st.dataframe(
            best, width="stretch", hide_index=True, height=190,
            column_config={
                "Target": st.column_config.TextColumn(width="medium"),
                "Minimo": st.column_config.NumberColumn(format="%.2f €"),
                "Mediana": st.column_config.NumberColumn(format="%.2f €"),
                "Massimo": st.column_config.NumberColumn(format="%.2f €"),
                "Offerte": st.column_config.NumberColumn(width="small"),
            })
        st.caption("Solo prodotti disponibili adesso. La distanza fra minimo e massimo "
                   "e' lo spazio in cui si muove chi rivende.")

    st.markdown(C.section("Log delle scansioni", nome_icona="list"), unsafe_allow_html=True)
    if history_path.exists():
        st.caption(f"Ultime 200 righe di {history_path.name}.")
        hist, csv = _carica_storico(str(history_path), history_path.stat().st_mtime,
                                    history_path.stat().st_size)
        st.dataframe(hist.tail(200).iloc[::-1], width="stretch", hide_index=True, height=320)
        st.download_button("Scarica il log completo in CSV", csv,
                           file_name=f"scansioni_{datetime.now():%Y%m%d_%H%M}.csv",
                           mime="text/csv")
    else:
        st.markdown(C.empty_state("list", "Nessun log ancora"), unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _carica_storico(percorso: str, _mtime: float, _dimensione: int):
    """Legge history.jsonl e prepara il CSV una sola volta.

    Streamlit esegue TUTTE le schede a ogni interazione, quindi senza cache
    questo lavoro si ripeteva anche solo muovendo uno slider. La chiave della
    cache include mtime e dimensione: il file viene riletto solo se cambia.
    """
    righe = [json.loads(l) for l in Path(percorso).read_text(encoding="utf-8").splitlines() if l.strip()]
    hist = pd.DataFrame(righe)
    return hist, hist.to_csv(index=False).encode("utf-8")


# ------------------------------------------------------------------ NOTIFICHE

def salva_preferenze(cfg, valori: dict) -> str:
    """Scrive le preferenze dove il monitor andra' a leggerle.

    Sul Gist se configurato (e' l'unico punto che dashboard e GitHub Actions
    condividono), altrimenti nel file locale. Rilegge lo stato prima di
    scrivere, per non sovrascrivere una scansione avvenuta nel frattempo.
    """
    from monitor import gist
    from monitor.state import State

    remoto = gist.da_ambiente()
    percorso = cfg.path_for("state_file")
    stato = State(percorso, remote=remoto)
    stato.imposta_preferenze(valori)

    if remoto is not None and remoto.gist_id:
        remoto.scrivi(stato.payload(), descrizione="preferenze aggiornate dalla dashboard")
        return "Gist"
    stato.save()
    return "file locale"


def riattivazione(cfg, stato: dict) -> None:
    """Elenco degli store spenti o in pausa dal monitor, con la riattivazione.

    Lo spegnimento automatico vive nello stato, non in stores.json: il
    workflow non puo' scrivere sul repository, e questo e' l'unico punto che
    dashboard e monitor condividono.
    """
    falliti = stato.get("store_failures") or {}
    spenti = {k: v for k, v in falliti.items() if isinstance(v, dict) and v.get("spento")}
    pausa = {k: v for k, v in falliti.items()
             if isinstance(v, dict) and v.get("riposo_fino_a") and not v.get("spento")}
    if not spenti and not pausa:
        return

    st.markdown(C.section("Negozi sospesi dal monitor",
                          f"{len(spenti)} spenti · {len(pausa)} in pausa", "alert"),
                unsafe_allow_html=True)
    st.caption("Dopo 4 fallimenti un negozio va in pausa per 24 ore; se al rientro ne "
               "colleziona altri 4 viene spento. Un successo azzera tutto da solo.")

    righe = []
    for sid, v in {**spenti, **pausa}.items():
        righe.append({
            "negozio": (cfg.store(sid) or {}).get("name", sid),
            "id": sid,
            "stato": "spento" if v.get("spento") else "in pausa",
            "errore": (v.get("errore") or "")[:60],
            "dal": (v.get("spento_il") or v.get("quando") or "")[:16].replace("T", " "),
        })
    st.dataframe(pd.DataFrame(righe).drop(columns=["id"]),
                 width="stretch", hide_index=True)

    scelta = st.multiselect("Riattiva", [r["id"] for r in righe],
                            format_func=lambda i: next(r["negozio"] for r in righe if r["id"] == i))
    if scelta and st.button("Riattiva i negozi selezionati"):
        from monitor import gist
        from monitor.state import State
        remoto = gist.da_ambiente()
        s_stato = State(cfg.path_for("state_file"), remote=remoto)
        n = sum(1 for sid in scelta if s_stato.riattiva_store(sid))
        try:
            if remoto is not None and remoto.gist_id:
                remoto.scrivi(s_stato.payload(), descrizione="negozi riattivati dalla dashboard")
            else:
                s_stato.save()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Salvataggio fallito: {exc}")
        else:
            st.session_state["esito_config"] = f"{n} negozi riattivati: verranno ritentati al prossimo giro."
            st.rerun()


def notifiche(cfg, stato: dict) -> None:
    st.markdown(C.section("Notifiche Telegram", nome_icona="alert"), unsafe_allow_html=True)
    st.caption("Le preferenze vivono nello stato condiviso: il monitor le legge "
               "al giro successivo al salvataggio.")

    pref = (stato.get("meta") or {}).get("preferenze") or {}
    attivi = [t for t in cfg.raw["targets"] if t.get("enabled")]
    etichette = {t["id"]: t["name"] for t in attivi}
    scelti = pref.get("target_notificati")

    attive = st.toggle("Invia notifiche su Telegram",
                       value=bool(pref.get("notifiche_attive", True)),
                       help="Spento, lo scraper continua a scansionare e ad aggiornare "
                            "la dashboard, ma non manda nulla.")
    selezione = st.multiselect(
        "Avvisami solo per questi prodotti",
        [t["id"] for t in attivi],
        default=list(scelti) if scelti is not None else [t["id"] for t in attivi],
        format_func=lambda tid: etichette.get(tid, tid),
        help="Lasciali tutti selezionati per ricevere avvisi su qualsiasi prodotto "
             "monitorato.")

    if not attive:
        st.warning("Le notifiche sono disattivate: non riceverai alcun avviso.")
    elif not selezione:
        st.warning("Nessun prodotto selezionato: equivale a non ricevere avvisi.")

    if pref.get("aggiornate_il"):
        st.caption(f"Ultima modifica: {pref['aggiornate_il'][:19].replace('T', ' ')}")

    if st.button("Salva le preferenze di notifica", type="primary"):
        tutti = [t["id"] for t in attivi]
        try:
            dove = salva_preferenze(cfg, {
                "notifiche_attive": bool(attive),
                # tutti selezionati equivale a nessun filtro: si salva null
                "target_notificati": None if set(selezione) == set(tutti) else list(selezione),
            })
        except Exception as exc:  # noqa: BLE001 - l'errore va mostrato
            st.error(f"Salvataggio fallito: {exc}")
        else:
            st.session_state["esito_config"] = f"Preferenze di notifica salvate su: {dove}"
            st.rerun()


# ---------------------------------------------------------------------- NEGOZI

def negozi(cfg) -> None:
    # st.success() seguito da st.rerun() viene cancellato prima di essere letto:
    # l'esito sopravvive al rerun passando da session_state.
    if (esito := st.session_state.pop("esito_config", None)):
        st.success(esito)

    st.markdown(C.section("Soglie MSRP per target", nome_icona="tag"), unsafe_allow_html=True)
    st.caption("Modifica le soglie e salva: il file stores.json viene riscritto, "
               "con backup automatico in stores.json.bak.")

    tdf = pd.DataFrame([{
        "attivo": t.get("enabled", False), "id": t["id"], "nome": t["name"],
        "MSRP €": t.get("msrp_eur"), "soglia max €": t["max_price_eur"],
        "MSRP verificato": t.get("msrp_verified", False),
    } for t in cfg.raw["targets"]])
    tedit = st.data_editor(
        tdf, width="stretch", hide_index=True, key="targets_editor",
        disabled=["id", "nome", "MSRP verificato"],
        column_config={"attivo": st.column_config.CheckboxColumn("Attivo"),
                       "MSRP €": st.column_config.NumberColumn(format="%.2f"),
                       "soglia max €": st.column_config.NumberColumn(format="%.2f")},
    )

    st.markdown(C.section("Parole chiave del target", nome_icona="filter"), unsafe_allow_html=True)
    attivi = [t for t in cfg.raw["targets"] if t.get("enabled")]
    if attivi:
        scelto = st.selectbox("Target", [t["id"] for t in attivi], key="kw_target")
        tg = cfg.target(scelto)
        st.caption("Gruppi in AND fra loro, parole in OR dentro il gruppo. "
                   "Il match e' a confine di parola: 'tin' non matcha 'bustine'.")
        gruppi_txt = st.text_area(
            "Gruppi (una riga per gruppo, parole separate da virgola)",
            "\n".join(", ".join(g) for g in tg.get("must_contain_any_groups", [])),
            height=110, key="kw_groups")
        esclusioni_txt = st.text_area(
            "Parole che scartano il prodotto (separate da virgola)",
            ", ".join(tg.get("must_not_contain", [])), height=80, key="kw_excl")
    else:
        scelto = gruppi_txt = esclusioni_txt = None
        st.info("Nessun target attivo.")

    st.markdown(C.section("Negozi", f"{len(cfg.stores)} attivi su {len(cfg.all_stores)}", "store"),
                unsafe_allow_html=True)
    sdf = pd.DataFrame([{
        "attivo": s.get("enabled", False), "id": s["id"], "nome": s["name"],
        "tipo": s.get("type", ""), "url": s.get("base_url", ""),
        "ufficiale": s.get("official_retailer", False),
        "motivo disattivazione": (s.get("disabled_reason") or "")[:90],
    } for s in cfg.all_stores])
    sedit = st.data_editor(
        sdf, width="stretch", hide_index=True, height=420, key="stores_editor",
        disabled=["id", "tipo", "url", "ufficiale", "motivo disattivazione"],
        column_config={"attivo": st.column_config.CheckboxColumn("Attivo")},
    )

    with st.expander("Aggiungi un negozio"):
        st.caption("Identifica prima la piattaforma: "
                   "`/products.json?limit=3` risponde JSON → Shopify; "
                   "`/wp-json/wc/store/v1/products?search=pokemon` risponde JSON → WooCommerce.")
        c1, c2 = st.columns(2)
        nuovo_id = c1.text_input("ID univoco", placeholder="nuovonegozio")
        nuovo_nome = c2.text_input("Nome visualizzato", placeholder="Nuovo Negozio")
        nuovo_url = c1.text_input("URL base", placeholder="https://nuovonegozio.it")
        nuovo_tipo = c2.selectbox("Adapter", ["shopify", "woocommerce_store_api", "vtex",
                                              "html_schema_org", "html_generic",
                                              "html_prestashop", "html_sitemap"])
        if st.button("Aggiungi al file"):
            if not (nuovo_id and nuovo_url):
                st.error("ID e URL sono obbligatori.")
            elif cfg.store(nuovo_id):
                st.error(f"Esiste gia' uno store con id '{nuovo_id}'.")
            else:
                cfg.raw["stores"].append({
                    "id": nuovo_id, "name": nuovo_nome or nuovo_id,
                    "base_url": nuovo_url.rstrip("/"), "type": nuovo_tipo,
                    "enabled": True, "priority": 3,
                    "search_terms": ["pokemon", "fuoriclasse"],
                    "verified_at": datetime.now().strftime("%Y-%m-%d"),
                    "notes": "Aggiunto dalla dashboard: non ancora verificato sul campo.",
                })
                try:
                    salva(cfg)
                except OSError as exc:
                    st.error(f"Scrittura fallita: {exc}")
                else:
                    st.session_state["esito_config"] = (
                        f"Negozio '{nuovo_id}' aggiunto. "
                        f"Provalo con: python app.py --store {nuovo_id}")
                    st.rerun()

    if st.button("Salva le modifiche su stores.json", type="primary"):
        for _, r in tedit.iterrows():
            t = cfg.target(r["id"])
            if t:
                t["enabled"] = bool(r["attivo"])
                t["max_price_eur"] = float(r["soglia max €"])
                if r["MSRP €"] is not None:
                    t["msrp_eur"] = float(r["MSRP €"])
        for _, r in sedit.iterrows():
            s = cfg.store(r["id"])
            if s:
                s["enabled"] = bool(r["attivo"])
        if scelto:
            tg = cfg.target(scelto)
            gruppi = [[w.strip() for w in riga.split(",") if w.strip()]
                      for riga in (gruppi_txt or "").splitlines() if riga.strip()]
            if gruppi:
                tg["must_contain_any_groups"] = gruppi
            tg["must_not_contain"] = [w.strip() for w in (esclusioni_txt or "").split(",") if w.strip()]
        try:
            salva(cfg)
        except OSError as exc:
            st.error(f"Salvataggio fallito: {exc}")
        else:
            st.session_state["esito_config"] = (
                "stores.json salvato. La versione precedente e' in stores.json.bak.")
            st.rerun()


def salva(cfg) -> None:
    """Scrive stores.json tenendo un backup della versione precedente."""
    if cfg.path.exists():
        shutil.copy2(cfg.path, cfg.path.with_suffix(".json.bak"))
    cfg.path.write_text(json.dumps(cfg.raw, ensure_ascii=False, indent=2), encoding="utf-8")
