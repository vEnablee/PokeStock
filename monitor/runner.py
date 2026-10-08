"""Orchestrazione di una scansione completa."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx

from . import adapters, gist, matching
from .config import Config, load
from .models import Product, StoreResult
from .notifier import Telegram
from .state import State, append_history


async def scan_store(client, cfg: Config, store: dict) -> StoreResult:
    started = time.perf_counter()
    try:
        adapter = adapters.get(store["type"])
        products = await adapter(client, cfg, store)
        return StoreResult(store["id"], products, None, time.perf_counter() - started)
    except Exception as exc:  # noqa: BLE001 - un sito rotto non deve fermare il run
        return StoreResult(store["id"], [], f"{type(exc).__name__}: {exc}",
                           time.perf_counter() - started)


async def run(
    cfg: Config | None = None,
    *,
    dry_run: bool = False,
    only_store: str | None = None,
    seed: bool = False,
    verbose: bool = True,
) -> dict:
    cfg = cfg or load()
    settings = cfg.settings
    dry_run = dry_run or settings.get("dry_run", False)


    soglia_q = settings.get("quarantena_dopo_fallimenti", 4)
    giri_q = settings.get("quarantena_giri", 6)

    stores = cfg.stores
    if only_store:
        stores = [s for s in cfg.all_stores if s["id"] == only_store]
        if not stores:
            raise SystemExit(f"store '{only_store}' non trovato in stores.json")

    remoto = gist.da_ambiente()
    if remoto is not None and not remoto.gist_id:
        # Senza GIST_ID ogni esecuzione riparte da zero, quindi si auto-semina e
        # non notifica nulla: un guasto che altrimenti resta invisibile.
        print("::warning::GIST_TOKEN presente ma GIST_ID assente: lo stato non "
              "verra' conservato, questa esecuzione si auto-seminera' e non "
              "invierà alcuna notifica. Imposta il secret GIST_ID.")
    state = State(cfg.path_for("state_file"), remote=remoto)
    if verbose and remoto:
        print(f"** stato caricato da: {state.origine} **")
    telegram = Telegram(cfg, dry_run=dry_run)
    targets = cfg.targets

    # Protezione fondamentale: al primo avvio si registra lo stato SENZA notificare.
    # Altrimenti il primo run spara decine di messaggi per prodotti disponibili da giorni.
    pref = state.preferenze(settings.get("preferenze_predefinite"))
    notifiche_attive = bool(pref.get("notifiche_attive", True))
    target_scelti = pref.get("target_notificati")
    if verbose and not notifiche_attive:
        print("** notifiche disattivate dalla dashboard **")
    if verbose and target_scelti:
        print(f"** notifiche limitate a: {', '.join(target_scelti)} **")

    seeding = seed or state.is_first_run
    if seeding and verbose:
        print("** SEED: primo avvio, registro lo stato iniziale senza inviare notifiche **")

    # Gli store in quarantena non vengono interrogati: dopo N fallimenti di fila
    # insistere peggiora un eventuale ban e spreca tempo. Si riprovano dopo
    # qualche giro.
    in_quarantena = []
    if not only_store:
        attivi = []
        for s in stores:
            if state.in_quarantena(s["id"]):
                rimasti = state.consuma_quarantena(s["id"])
                in_quarantena.append((s["id"], rimasti))
            else:
                attivi.append(s)
        stores = attivi

    sem = asyncio.Semaphore(settings.get("concurrency", 8))

    async def guarded(store):
        async with sem:
            return await scan_store(client, cfg, store)

    started = time.perf_counter()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(guarded(s) for s in stores))

        matched: list[tuple[Product, dict]] = []
        seen_keys: list[str] = []
        scanned = 0

        for res in results:
            store = cfg.store(res.store_id)
            failures = state.mark_store(res.store_id, res.ok, res.error,
                                        soglia_quarantena=soglia_q, giri_quarantena=giri_q)
            if not res.ok:
                if verbose:
                    print(f"  [ERRORE] {store['name']:24s} {res.error}")
                # Un solo avviso, nel momento in cui lo store entra in quarantena:
                # e' li' che smette di essere interrogato e vale la pena saperlo.
                if (soglia_q and failures >= soglia_q
                        and state.avviso_store_dovuto(
                            res.store_id, settings.get("ore_silenzio_avvisi", 12))):
                    await telegram.store_error(client, store["name"], res.error, failures)
                continue

            # Un adapter che risponde 200 ma non estrae nulla e' un guasto
            # silenzioso: senza questo avviso e' indistinguibile da "catalogo vuoto".
            if not res.products and verbose:
                print(f"  [VUOTO ] {store['name']:24s} ha risposto ma non ha restituito prodotti")

            scanned += len(res.products)
            for product in res.products:
                seen_keys.append(product.key)
                # fase 1: il titolo e' un target? (prezzo ignorato)
                target = matching.classify_keywords(product.title, targets, cfg.filters)
                if target:
                    matched.append((product, target))

        # Dedup: stesso prodotto puo' comparire piu' volte nel feed di uno store
        unique: dict[str, tuple[Product, dict]] = {}
        for product, target in matched:
            prev = unique.get(product.key)
            if prev is None or target["priority"] < prev[1]["priority"]:
                unique[product.key] = (product, target)

        notified = 0
        cap = settings.get("max_notifications_per_run", 25)
        renotify = settings.get("renotify_after_hours", 12)
        history_path = cfg.path_for("history_file")
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        above_msrp = 0
        for product, target in sorted(unique.values(), key=lambda pt: (pt[1]["priority"], pt[0].price or 0)):
            # fase 2: il prezzo rientra nella soglia MSRP?
            within = matching.price_in_range(product.price, target, cfg.filters)
            if not within:
                above_msrp += 1

            should, reason = state.should_notify(product, renotify)
            if should and not notifiche_attive:
                should, reason = False, "notifiche disattivate dalla dashboard"
            if should and target_scelti is not None and target["id"] not in target_scelti:
                should, reason = False, f"target '{target['id']}' escluso dalla dashboard"
            if not within:
                should, reason = False, f"fuori soglia MSRP (max {target['max_price_eur']:.2f} EUR)"
            if seeding:
                should, reason = False, "seed iniziale"
            if should and notified >= cap:
                should, reason = False, f"circuit breaker: oltre {cap} notifiche in un run"

            sent = False
            if should:
                sent = await telegram.product_alert(client, product, target)
                notified += int(sent)

            state.record(product, notified=sent, target_id=target["id"], within_msrp=within)
            append_history(history_path, {
                "ts": stamp, "store_id": product.store_id, "store_name": product.store_name,
                "target_id": target["id"], "title": product.title, "price": product.price,
                "available": product.available, "url": product.url,
                "within_msrp": within, "categoria": product.categoria,
                "notified": sent, "reason": reason,
            })

        # Se cade piu' di meta' dei negozi in un colpo solo, non sono i negozi:
        # e' la rete o un blocco che ci riguarda. Meglio saperlo subito.
        quota = settings.get("allarme_fallimenti_percentuale", 50)
        falliti_ora = sum(1 for r in results if not r.ok)
        sopra_soglia = bool(stores) and falliti_ora * 100 / len(stores) >= quota and falliti_ora >= 3
        if state.allarme_globale(sopra_soglia,
                                 settings.get("allarme_giri_consecutivi", 3),
                                 settings.get("ore_silenzio_avvisi", 12)):
            await telegram.send(client, telegram._render(
                "global_alert_template",
                falliti=falliti_ora, totali=len(stores),
                quota=round(falliti_ora * 100 / len(stores)),
                giri=settings.get("allarme_giri_consecutivi", 3)))

    duration = time.perf_counter() - started
    scanned_ok = {r.store_id for r in results if r.ok}
    # In una scansione completa, gli store che non sono piu' in lista (disattivati)
    # non devono restare appesi fra quelli "in errore".
    if not (only_store or settings.get("_run_parziale")):
        state.dimentica_store({s["id"] for s in stores})
    dropped = state.drop_unmatched(scanned_ok, set(unique))
    pruned = state.prune(seen_keys) + dropped
    summary = {
        "ts": stamp,
        "in_quarantena": len(in_quarantena),
        "duration_s": round(duration, 1),
        "stores_total": len(stores),
        "stores_ok": sum(1 for r in results if r.ok),
        "stores_failed": sum(1 for r in results if not r.ok),
        "products_scanned": scanned,
        "matches": len(unique),
        "within_msrp": len(unique) - above_msrp,
        "above_msrp": above_msrp,
        "available_now": sum(1 for p, _ in unique.values() if p.available),
        "available_within_msrp": sum(
            1 for p, t in unique.values()
            if p.available and matching.price_in_range(p.price, t, cfg.filters)
        ),
        "notifications_sent": notified,
        "seeding": seeding,
        "dry_run": dry_run,
        "partial": (bool(only_store) or len(stores) < len(cfg.stores)
                    or bool(settings.get("_run_parziale"))),
        "pruned": pruned,
    }
    state.save(summary)
    if remoto:
        try:
            remoto.scrivi(state.payload(),
                          descrizione=f"{summary['within_msrp']} entro MSRP · "
                                      f"{summary['stores_ok']}/{summary['stores_total']} negozi · "
                                      f"{summary['ts']}")
            if verbose:
                print("** stato salvato sul Gist **")
        except Exception as exc:  # noqa: BLE001 - il run non deve fallire per questo
            print(f"[stato] scrittura sul Gist fallita: {exc}")

    if verbose:
        print(
            f"\n{summary['stores_ok']}/{summary['stores_total']} store OK in {summary['duration_s']}s | "
            f"{scanned} prodotti letti | {summary['matches']} match "
            f"({summary['available_now']} disponibili) | {notified} notifiche inviate"
        )
        for product, target in sorted(unique.values(), key=lambda pt: (not pt[0].available, pt[0].price or 0)):
            if not matching.price_in_range(product.price, target, cfg.filters):
                continue
            flag = "DISPONIBILE" if product.available else "esaurito   "
            price = f"{product.price:6.2f}" if product.price is not None else "   n/d"
            print(f"  [{flag}] {price} EUR  {product.store_name:22s} {target['id']:18s} {product.title[:54]}")

    return summary
