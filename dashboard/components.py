"""HTML di KPI, card prodotto, skeleton e avvisi.

Streamlit non offre una griglia di card: queste funzioni producono HTML che viene
iniettato con st.markdown(unsafe_allow_html=True) e stilizzato da styles.CSS.
Tutto il testo che proviene dai negozi passa da esc().
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .icons import icon

PLATFORM_LABEL = {
    "shopify": "Shopify",
    "woocommerce_store_api": "WooCommerce",
    "vtex": "VTEX",
    "html_schema_org": "HTML",
    "html_generic": "HTML",
    "html_prestashop": "PrestaShop",
    "html_sitemap": "Sitemap",
}


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def eur(value) -> str:
    if value is None:
        return "n/d"
    return f"{value:,.2f}".replace(",", "~").replace(".", ",").replace("~", ".") + " €"


def live_badge(active: bool, text: str) -> str:
    cls = "live" if active else "live off"
    return f'<span class="{cls}"><span class="dot{"" if active else " idle"}"></span>{esc(text)}</span>'


def topbar(titolo: str, marchio: str, destra: str) -> str:
    return (f'<div class="bar"><div class="brand"><span class="mk">{icon("activity")}</span>'
            f'{esc(titolo)}<b>{esc(marchio)}</b></div>{destra}</div>')


def lede(riga1: str, riga2: str, sottotitolo: str) -> str:
    return (f'<div class="lede"><h1>{esc(riga1)}<em>{esc(riga2)}</em></h1>'
            f'<p>{sottotitolo}</p></div>')


def kpi_row(items: list[dict]) -> str:
    cards = "".join(
        f'<div class="kpi {esc(i.get("tone", "k1"))}">'
        f'<div class="label">{esc(i["label"])}</div>'
        f'<div class="value">{esc(i["value"])}</div>'
        f'<div class="sub">{esc(i.get("sub", ""))}</div></div>'
        for i in items
    )
    return f'<div class="kpi-grid">{cards}</div>'


def _age(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "ora"
    if mins < 60:
        return f"{mins} min fa"
    if mins < 1440:
        return f"{mins // 60} h fa"
    return f"{mins // 1440} g fa"


def product_card(entry: dict, *, msrp: float | None, mercato: float | None = None,
                 platform: str = "", delay: float = 0.0) -> str:
    """Una card. `mercato` e' il prezzo mediano dei listini sopra soglia per quel
    target: serve a calcolare la percentuale di risparmio mostrata nel badge.
    """
    # Lo stesso filtro di schema applicato all'immagine vale per il link: l'URL
    # arriva da un negozio esterno e un "javascript:" eseguirebbe codice al clic.
    def _link(u: str) -> str:
        return u if str(u or "").startswith(("http://", "https://")) else "#"

    available = bool(entry.get("available"))
    within = bool(entry.get("within_msrp"))
    preorder = bool(entry.get("preorder"))
    price = entry.get("price")
    url = _link(entry.get("url"))
    image = entry.get("image") or ""

    # badge a sinistra: stato di vendita
    if preorder:
        sinistra = '<span class="tag pre">pre-order</span>'
    elif available:
        sinistra = '<span class="tag stock">in stock</span>'
    else:
        sinistra = '<span class="tag out">esaurito</span>'

    # badge a destra: entro soglia, oppure quanto si sta pagando in piu'
    destra = ""
    if within:
        destra = '<span class="tag msrp">msrp ok</span>'
        if mercato and price and mercato > price:
            risparmio = round((mercato - price) / mercato * 100)
            if risparmio >= 5:
                destra = f'<span class="tag save">−{risparmio}% mercato</span>'
    elif price and msrp:
        ricarico = round((price - msrp) / msrp * 100)
        destra = f'<span class="tag over">+{ricarico}%</span>'

    # Il riquadro resta chiaro e isolato: cosi' il multiply dell'immagine agisce
    # su di esso e i fondi bianchi delle foto spariscono senza annerire il prodotto.
    # Streamlit rimuove gli attributi on*, quindi niente onerror: se l'URL e' rotto
    # il livello non dipinge nulla e il segnaposto sotto resta visibile.
    sicura = image if image.startswith(("http://", "https://")) else ""
    livello = (f'<div class="shot" style="background-image:url(&quot;{esc(sicura)}&quot;)"></div>'
               if sicura else "")

    delta = ""
    if msrp and price:
        diff = price - msrp
        if abs(diff) >= 0.01:
            segno = "+" if diff > 0 else "−"
            classe = "loss" if diff > 0 else "gain"
            delta = (f'<div class="delta {classe}">{segno}{eur(abs(diff))} '
                     f'<span style="color:var(--muted);font-weight:400">vs MSRP {eur(msrp)}</span></div>')
        else:
            delta = f'<div class="delta">in linea con l\'MSRP ({eur(msrp)})</div>'

    cta = (f'<a class="cta" href="{esc(url)}" target="_blank" rel="noopener">'
           f'{icon("cart")}ACQUISTA ORA</a>' if available else
           f'<a class="cta muted" href="{esc(url)}" target="_blank" rel="noopener">'
           f'{icon("external")}Vedi scheda</a>')

    return (
        f'<div class="card" style="animation-delay:{delay:.2f}s">'
        f'<div class="frame">'
        f'<div class="tags">{sinistra}{destra}</div>'
        f'<div class="noimg">{icon("image")}</div>{livello}</div>'
        f'<div class="body">'
        f'<div class="title" title="{esc(entry.get("title"))}">{esc(entry.get("title"))}</div>'
        f'<div class="meta"><span class="price {"" if within else "over"}">{eur(price)}</span>'
        f'<span class="seen">{esc(_age(entry.get("last_seen")))}</span></div>'
        f'{delta}'
        f'<div class="store">{icon("store")}'
        f'<span>{esc(entry.get("store_name") or entry.get("store_id"))}</span>'
        f'<span class="plat">· {esc(PLATFORM_LABEL.get(platform, platform))}</span></div>'
        f'{cta}</div></div>'
    )


def grid(cards: list[str]) -> str:
    return f'<div class="grid">{"".join(cards)}</div>'


def skeleton_grid(n: int = 8) -> str:
    one = ('<div class="sk"><div class="sk-img shimmer"></div>'
           '<div class="sk-line shimmer"></div>'
           '<div class="sk-line short shimmer"></div>'
           '<div class="sk-line shimmer"></div></div>')
    return f'<div class="grid">{one * n}</div>'


def empty_state(nome_icona: str, title: str, hint: str = "") -> str:
    return (f'<div class="empty">{icon(nome_icona)}'
            f'<div style="margin-top:.7rem;font-weight:700;color:var(--ink)">{esc(title)}</div>'
            f'<div style="margin-top:.35rem;font-size:.83rem">{esc(hint)}</div></div>')


def section(title: str, count: str | int | None = None, nome_icona: str = "") -> str:
    badge = f'<span class="n">{esc(count)}</span>' if count is not None else ""
    testa = icon(nome_icona) if nome_icona else ""
    return f'<div class="sec">{testa}{esc(title)}{badge}</div>'


def notice(testo: str) -> str:
    """Banner d'avviso: usato quando un filtro sta nascondendo dei risultati."""
    return f'<div class="notice">{icon("alert")}<span>{esc(testo)}</span></div>'


def error_box(righe: list[dict], nota: str) -> str:
    """Riquadro degli store in errore.

    Ogni riga porta nome, numero di fallimenti consecutivi, quando e con quale
    errore: un contatore nudo faceva sembrare "rotti" store che si erano gia'
    ripresi ma non erano stati riscansionati.
    """
    corpo = ""
    for r in righe:
        corpo += (f'<div class="rw"><span>{esc(r["nome"])}</span>'
                  f'<b>{esc(r["conteggio"])}&times;</b></div>')
        dettaglio = " · ".join(x for x in (r.get("errore"), r.get("eta")) if x)
        if dettaglio:
            corpo += (f'<div style="font-size:.67rem;color:var(--muted);'
                      f'margin:-.1rem 0 .35rem;padding-left:.1rem">{esc(dettaglio)}</div>')
    return (f'<div class="errbox"><div class="hd">{icon("alert")}'
            f'{len(righe)} negozi in errore</div>{corpo}'
            f'<div class="ft">{esc(nota)}</div></div>')
