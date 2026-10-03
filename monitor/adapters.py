"""Adapter per piattaforma e-commerce.

Ogni adapter riceve uno store di stores.json e restituisce una lista di Product.
Non deve mai sollevare: il runner cattura, ma e' bene fallire piano e restituire
quello che si e' riusciti a leggere.
"""
from __future__ import annotations

import asyncio
import html as html_mod
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import cache
from .models import Product

# Spaziatura minima fra due richieste allo STESSO store. Evita di sembrare un bot
# aggressivo: i negozi piccoli stanno su hosting condiviso e si spaventano in fretta.
_LAST_REQUEST: dict[str, float] = {}
_STORE_LOCKS: dict[str, asyncio.Lock] = {}


async def _respect_rate_limit(store_id: str, min_interval: float) -> None:
    if min_interval <= 0:
        return
    lock = _STORE_LOCKS.setdefault(store_id, asyncio.Lock())
    async with lock:
        elapsed = time.monotonic() - _LAST_REQUEST.get(store_id, 0.0)
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _LAST_REQUEST[store_id] = time.monotonic()

# Marcatori testuali usati quando non c'e' JSON-LD. L'ordine conta:
# "non disponibile" contiene "disponibile" come sottostringa, quindi i negativi
# vanno sempre controllati per primi.
NEG_DEFAULT = ["non disponibile", "esaurito", "out of stock", "sold out", "terminato", "non acquistabile"]
POS_DEFAULT = ["aggiungi al carrello", "acquista ora", "disponibile", "add to cart"]

PRICE_RE = re.compile(r"(\d{1,4})[.,](\d{2})")
SCHEMA_IN = re.compile(r"schema\.org/(InStock|LimitedAvailability|PreOrder|InStoreOnly)", re.I)
SCHEMA_OUT = re.compile(r"schema\.org/(OutOfStock|SoldOut|Discontinued|BackOrder)", re.I)


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------- http

async def _get(client: httpx.AsyncClient, url: str, cfg, store: dict, *, params=None, expect_json=False):
    """GET con cache, rate limit per store, retry, backoff e jitter.

    Valida il Content-Type prima di parsare JSON: packmonstore.it risponde 200
    con una pagina HTML al posto del JSON quando lo si interroga troppo in fretta.
    """
    retries = cfg.setting("retries", store, 2)
    backoff = cfg.setting("retry_backoff_seconds", store, 3)
    timeout = cfg.setting("timeout_seconds", store, 25)
    jitter = cfg.settings.get("jitter_seconds", [0, 0])
    ttl = float(cfg.settings.get("cache_ttl_seconds", 0) or 0)
    min_interval = float(cfg.setting("min_seconds_between_requests_per_store", store, 0) or 0)
    # cfg.setting() applica l'override per-store: alcuni WAF rifiutano proprio
    # lo User-Agent da browser sulle chiamate alle API REST.
    headers = {
        "User-Agent": cfg.setting("user_agent", store, cfg.settings["user_agent"]),
        "Accept-Language": cfg.setting("accept_language", store, cfg.settings["accept_language"]),
        "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    }

    cached = cache.get(url, params, ttl)
    if cached is not None:
        content, cached_headers = cached
        if expect_json:
            return json.loads(content.decode("utf-8", errors="replace"))
        return httpx.Response(200, content=content, headers=cached_headers,
                              request=httpx.Request("GET", url))

    last: Exception | None = None
    for attempt in range(retries + 1):
        await _respect_rate_limit(store["id"], min_interval)
        if jitter and jitter[1] > 0:
            await asyncio.sleep(random.uniform(jitter[0], jitter[1]))
        try:
            r = await client.get(url, params=params, headers=headers, timeout=timeout,
                                 follow_redirects=cfg.settings.get("follow_redirects", True))
            if r.status_code == 429:
                # il server ci sta dicendo esplicitamente di rallentare: si rispetta
                wait = float(r.headers.get("retry-after", backoff * 4))
                raise FetchError(f"HTTP 429 (rate limit), attesa suggerita {wait:g}s")
            if r.status_code >= 400:
                raise FetchError(f"HTTP {r.status_code}")
            ctype = r.headers.get("content-type", "")
            if expect_json and "json" not in ctype.lower():
                raise FetchError(f"atteso JSON, ricevuto '{ctype.split(';')[0] or 'ignoto'}'")
            cache.put(url, params, r.content, dict(r.headers), ttl)
            return r.json() if expect_json else r
        except Exception as exc:  # noqa: BLE001 - si ritenta su qualunque errore di rete
            last = exc
            if attempt < retries:
                await asyncio.sleep(backoff * (attempt + 1))
    raise FetchError(str(last))


def _price(value) -> float | None:
    """Converte un prezzo in float gestendo i formati europei.

    '59,90' -> 59.9   '1.234,50' -> 1234.5   '1,234.50' -> 1234.5
    L'ultimo separatore incontrato e' quello decimale; gli altri sono migliaia.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = re.sub(r"[^\d.,-]", "", str(value))
    if not text:
        return None

    last_dot, last_comma = text.rfind("."), text.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec, thou = (",", ".") if last_comma > last_dot else (".", ",")
        text = text.replace(thou, "").replace(dec, ".")
    elif last_comma >= 0:
        # virgola singola: decimale se seguita da 1-2 cifre, altrimenti migliaia
        text = text.replace(",", "." if len(text) - last_comma - 1 <= 2 else "")
    elif last_dot >= 0 and len(text) - last_dot - 1 == 3 and text.count(".") == 1:
        # '1.234' senza decimali: punto di migliaia
        text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


# ------------------------------------------------------------------------ shopify

async def shopify(client, cfg, store) -> list[Product]:
    """/products.json?limit=250 -> catalogo paginato, 'available' autoritativo.

    Se lo store dichiara `collections`, si interrogano solo quelle:
    /collections/<handle>/products.json. Serve per i cataloghi enormi (una
    libreria ha migliaia di titoli e i Pokemon stanno in fondo), dove scorrere
    tutto il catalogo costerebbe decine di richieste per nulla.
    """
    base = store["base_url"].rstrip("/")
    tpl = cfg.endpoints.get("shopify", {})
    max_pages = tpl.get("max_pages", 6)
    collezioni = store.get("collections") or []
    percorsi = ([f"{base}/collections/{h}/products.json" for h in collezioni]
                or [f"{base}/products.json"])

    out: list[Product] = []
    visti: set[str] = set()
    for percorso in percorsi:
        for page in range(1, max_pages + 1):
            data = await _get(client, percorso, cfg, store,
                              params={"limit": 250, "page": page}, expect_json=True)
            products = data.get("products", []) if isinstance(data, dict) else []
            if not products:
                break
            for p in products:
                handle = p.get("handle", "")
                if handle in visti:      # lo stesso prodotto puo' stare in piu' collection
                    continue
                visti.add(handle)
                variants = p.get("variants") or []
                if not variants:
                    continue
                # la variante "migliore" e' una disponibile, al prezzo piu' basso
                v = max(variants, key=lambda v: (bool(v.get("available")),
                                                 -(_price(v.get("price")) or 1e9)))
                images = p.get("images") or []
                out.append(Product(
                    store_id=store["id"], store_name=store["name"], title=p.get("title", ""),
                    price=_price(v.get("price")), available=bool(v.get("available")),
                    url=f"{base}/products/{handle}",
                    image=images[0].get("src", "") if images else "",
                ))
            if len(products) < 250:
                break
    return out


# ------------------------------------------------------------------ woocommerce

async def woocommerce_store_api(client, cfg, store) -> list[Product]:
    """Store API pubblica di WooCommerce. prices.price e' in CENTESIMI."""
    base = store["base_url"].rstrip("/")
    terms = store.get("search_terms") or ["pokemon"]
    seen: set = set()
    out: list[Product] = []

    for term in terms:
        data = await _get(client, f"{base}/wp-json/wc/store/v1/products", cfg, store,
                          params={"search": term, "per_page": 100}, expect_json=True)
        if not isinstance(data, list):
            continue
        for p in data:
            pid = p.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            prices = p.get("prices") or {}
            raw = prices.get("price")
            price = None
            if raw not in (None, ""):
                minor = prices.get("currency_minor_unit", 2)
                try:
                    price = int(raw) / (10 ** minor)
                except (TypeError, ValueError):
                    price = _price(raw)
            title = p.get("name") or ""
            # le API Woo restituiscono entita' HTML nei titoli (&#8211; ecc.)
            title = BeautifulSoup(title, "html.parser").get_text()
            images = p.get("images") or []
            image = images[0].get("src", "") if images else ""
            out.append(Product(
                store_id=store["id"], store_name=store["name"], title=title,
                price=price, available=bool(p.get("is_in_stock")),
                url=p.get("permalink") or base, image=image,
            ))
    return out


# ----------------------------------------------------------------------- vtex

async def vtex(client, cfg, store) -> list[Product]:
    base = store["base_url"].rstrip("/")
    out: list[Product] = []
    for term in store.get("search_terms") or ["pokemon"]:
        data = await _get(client, f"{base}/api/catalog_system/pub/products/search", cfg, store,
                          params={"ft": term, "_from": 0, "_to": 49}, expect_json=True)
        if not isinstance(data, list):
            continue
        for p in data:
            for item in p.get("items", []):
                for seller in item.get("sellers", []):
                    offer = seller.get("commertialOffer", {})
                    imgs = item.get("images") or []
                    out.append(Product(
                        store_id=store["id"], store_name=store["name"],
                        title=p.get("productName", ""), price=_price(offer.get("Price")),
                        available=offer.get("AvailableQuantity", 0) > 0,
                        url=urljoin(base, p.get("linkText", "") + "/p"),
                        image=imgs[0].get("imageUrl", "") if imgs else "",
                    ))
                    break
    return out


# ------------------------------------------------------------------------ html

def _availability_from_html(html: str, store: dict) -> bool | None:
    """True/False dal markup, None se indeterminabile."""
    markers = store.get("availability_markers") or {}

    if SCHEMA_OUT.search(html):
        return False
    if SCHEMA_IN.search(html):
        return True

    low = html.lower()
    for kw in markers.get("out_of_stock", NEG_DEFAULT):
        if kw.lower() in low:
            return False
    for kw in markers.get("in_stock", POS_DEFAULT):
        if kw.lower() in low:
            return True
    return None


def _jsonld_products(html: str) -> list[dict]:
    """Estrae i nodi JSON-LD di tipo Product, anche annidati in @graph o liste."""
    soup = BeautifulSoup(html, "html.parser")
    found: list[dict] = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            types = node.get("@type")
            types = [types] if isinstance(types, str) else (types or [])
            if any(str(t).lower() == "product" for t in types):
                found.append(node)
            for key in ("@graph", "itemListElement", "mainEntity"):
                if key in node:
                    walk(node[key])

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            walk(json.loads(tag.string or "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
    return found


def _from_jsonld(node: dict, store: dict, url: str) -> Product | None:
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers = offers or {}
    avail = str(offers.get("availability", ""))
    if SCHEMA_OUT.search(avail):
        available = False
    elif SCHEMA_IN.search(avail):
        available = True
    else:
        return None
    preorder = "preorder" in avail.lower()

    img = node.get("image")
    if isinstance(img, list):
        img = img[0] if img else ""
    if isinstance(img, dict):
        img = img.get("url", "")
    image = str(img or "")
    title = node.get("name")
    if not title:
        return None
    title = html_mod.unescape(str(title))
    return Product(
        store_id=store["id"], store_name=store["name"], title=str(title),
        price=_price(offers.get("price")), available=available,
        url=str(offers.get("url") or node.get("url") or url),
    )


def _candidate_links(html: str, base: str, keywords: list[str]) -> list[str]:
    """Link che valgono la pena di essere visitati: slug che contiene una keyword."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base).netloc
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if urlparse(href).netloc != host or href in seen:
            continue
        slug = urlparse(href).path.lower()
        if any(k in slug for k in keywords):
            seen.add(href)
            out.append(href)
    return out


async def _scrape_pages(client, cfg, store, urls: list[str], encoding: str | None) -> list[Product]:
    limit = cfg.setting("max_product_pages", store, 40)
    sem = asyncio.Semaphore(min(4, cfg.settings.get("concurrency", 8)))
    out: list[Product] = []

    async def one(url: str):
        async with sem:
            try:
                r = await _get(client, url, cfg, store)
            except FetchError:
                return
            html = r.content.decode(encoding, errors="replace") if encoding else r.text
            for node in _jsonld_products(html):
                p = _from_jsonld(node, store, url)
                if p:
                    out.append(p)
                    return
            # nessun JSON-LD utile: ricade sui marcatori testuali dello store
            available = _availability_from_html(html, store)
            if available is None:
                return
            soup = BeautifulSoup(html, "html.parser")
            title = (soup.find("h1").get_text(strip=True) if soup.find("h1")
                     else (soup.title.get_text(strip=True) if soup.title else ""))
            # le pagine legacy (es. Toysin, ISO-8859-1) espongono entita' HTML nei titoli
            title = html_mod.unescape(title)
            if not title:
                return
            og = soup.find("meta", property="og:image")
            image = og.get("content", "") if og else ""
            out.append(Product(store_id=store["id"], store_name=store["name"], title=title,
                               price=_price(_visible_price(soup)), available=available,
                               url=url, image=image))

    await asyncio.gather(*(one(u) for u in urls[:limit]))
    return out


def _visible_price(soup: BeautifulSoup) -> str | None:
    for attr in ("itemprop", "class", "id"):
        for tag in soup.find_all(attrs={attr: re.compile("price", re.I)}):
            text = tag.get("content") or tag.get_text(" ", strip=True)
            if text and PRICE_RE.search(text):
                return text
    return None


# Keyword usate per decidere quali URL visitare sui siti HTML.
# Non sono criteri di match (quelli stanno nei target): servono solo a non
# scaricare migliaia di pagine inutili.
URL_KEYWORDS = ["fuoriclasse", "allenatore", "elite-trainer", "elite_trainer", "etb", "pokemon"]


async def html_generic(client, cfg, store) -> list[Product]:
    base = store["base_url"].rstrip("/")
    encoding = store.get("encoding")
    urls: list[str] = list(store.get("product_urls") or [])

    # Se lo store espone una ricerca lato server, la si interroga: partire dalla
    # homepage trova pochissimi link utili. Nota: i termini vanno scelti con cura,
    # perche' il motore interno di certi siti non indicizza tutte le parole
    # (su giodicart "fuoriclasse" non restituisce nulla, "pokemon" si').
    punti: list[str] = []
    if store.get("search_url"):
        for termine in store.get("search_terms") or ["pokemon"]:
            punti.append(store["search_url"].format(query=quote_plus(termine)))
    punti += store.get("entry_points") or ([] if punti else [base])

    for entry in punti:
        try:
            r = await _get(client, entry, cfg, store)
        except FetchError:
            continue
        html = r.content.decode(encoding, errors="replace") if encoding else r.text
        # alcune category page espongono gia' i Product in JSON-LD: niente fetch extra
        direct = [p for p in (_from_jsonld(n, store, entry) for n in _jsonld_products(html)) if p]
        if direct:
            return direct
        urls.extend(_candidate_links(html, base, URL_KEYWORDS))

    return await _scrape_pages(client, cfg, store, list(dict.fromkeys(urls)), encoding)


html_schema_org = html_generic
html_prestashop = html_generic


async def html_sitemap(client, cfg, store) -> list[Product]:
    """Per i siti senza ricerca utilizzabile: si passa dalla sitemap."""
    encoding = store.get("encoding")
    r = await _get(client, store["sitemap_url"], cfg, store)
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        raise FetchError(f"sitemap non parsabile: {exc}") from exc

    filters = [f.lower() for f in store.get("sitemap_url_filter", ["pokemon"])]
    urls = [
        loc.text for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc.text and any(f in loc.text.lower() for f in filters)
    ]
    # restringe ancora: solo le URL che somigliano a un ETB
    etb = [u for u in urls if any(k in u.lower() for k in ("fuoriclasse", "allenatore", "etb", "elite"))]
    return await _scrape_pages(client, cfg, store, etb or urls, encoding)


ADAPTERS = {
    "shopify": shopify,
    "woocommerce_store_api": woocommerce_store_api,
    "vtex": vtex,
    "html_generic": html_generic,
    "html_schema_org": html_schema_org,
    "html_prestashop": html_prestashop,
    "html_sitemap": html_sitemap,
}


def get(store_type: str):
    try:
        return ADAPTERS[store_type]
    except KeyError:
        raise FetchError(f"nessun adapter per type='{store_type}'") from None
