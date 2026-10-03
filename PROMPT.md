# PokeStock — prompt finale

Sei uno sviluppatore Python esperto di scraping asincrono e automazione cloud.
Costruisci un progetto completo, pronto per GitHub, che monitora la disponibilità degli
**Elite Trainer Box / Set Allenatore Fuoriclasse Pokémon** presso e-commerce italiani e
notifica su Telegram **solo** quando un prodotto torna disponibile **entro la soglia MSRP**.

## Vincolo fondativo
`stores.json` esiste già, è stato verificato sul campo contro i siti reali e **non va riscritto**.
È l'unica fonte di verità: 83 store (51 attivi), 3 target, filtri, soglie, template Telegram.
Il codice deve **leggerlo**, non duplicarne i contenuti. Nessun dominio, keyword o prezzo
hardcodato nel codice.

## Requisiti funzionali

1. **Adapter per piattaforma**, selezionati dal campo `type` di ogni store:
   - `shopify` → `GET {base}/products.json?limit=250&page=N`, campo `variants[].available`
   - `woocommerce_store_api` → `GET {base}/wp-json/wc/store/v1/products?search=...`,
     campi `is_in_stock` e `prices.price` (**in centesimi**, dividere per `10**currency_minor_unit`)
   - `vtex` → `GET {base}/api/catalog_system/pub/products/search?ft=...`
   - `html_schema_org` / `html_generic` / `html_prestashop` → scoperta link dalle `entry_points`,
     poi parsing JSON-LD `Product` (`offers.availability`, `offers.price`);
     fallback testuale sui `availability_markers` dello store
   - `html_sitemap` → scarica `sitemap_url`, filtra le URL con `sitemap_url_filter`, visita le candidate
     (rispettando il campo `encoding`, es. Toysin è ISO-8859-1)

2. **Matching da config, con confine di parola obbligatorio.**
   `re.search(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', titolo_normalizzato)`.
   Il match a sottostringa è vietato: produce falsi positivi verificati
   (`tin` dentro `busTINe`, `30` dentro `3039`).
   Logica target: `must_contain_all` (AND) + `must_contain_any_groups` (gruppi in AND, keyword in OR)
   + `must_not_contain` (una sola presenza scarta) + esclusioni globali `filters.exclude_keywords`.
   Normalizzazione NFKD con rimozione dei diacritici su titolo e keyword.

3. **Filtro prezzo**: notifica solo se `min_price_eur <= prezzo <= target.max_price_eur`.

4. **Stato persistente — il requisito più importante.**
   Notifica **solo sulla transizione** non-disponibile → disponibile.
   - Primo avvio senza `state.json`: **seed silenzioso**, zero notifiche (altrimenti al primo run
     arrivano decine di messaggi per prodotti già disponibili da giorni).
   - `renotify_after_hours`: se resta disponibile oltre N ore, un solo promemoria.
   - `dedupe_across_targets`: una notifica per (store, prodotto), attribuita al target a priority minore.
   - `max_notifications_per_run` come circuit breaker contro bug di parsing.

5. **Telegram** via API Bot HTTP, Markdown, usando `telegram.message_template` dal JSON
   (store, titolo, prezzo, MSRP, target, link). Token e chat id **solo** da variabili d'ambiente.
   Avviso di errore per store solo dopo `notify_errors_after_consecutive_failures` fallimenti consecutivi.

6. **Resilienza**: concorrenza limitata da semaforo, retry con backoff, jitter, timeout per-store,
   validazione del `Content-Type` prima di `.json()` (packmonstore risponde HTML sotto rate limiting).
   **Un sito che fallisce non deve mai far fallire il run.**

7. **Due modalità d'esecuzione**:
   - CLI: `python app.py --run` (usata da GitHub Actions), `--dry-run`, `--store ID`, `--seed`
   - Streamlit: dashboard con ultimo run, disponibili ora, storico, salute degli store,
     pulsante di scansione manuale, ed esecuzione via query string `?cron=true`

8. **Persistenza**: `state.json` (stato corrente) e `history.jsonl` (append-only, per i grafici).

## File da produrre
`app.py` · `monitor/` (config, matching, adapters, state, notifier, runner)
`requirements.txt` · `.github/workflows/scraper.yml` (cron, commit dello stato sul repo)
`README.md` (setup Secrets, personalizzazione, limiti noti) · `.gitignore`

## Avvertenze da rispettare
- GitHub Actions gira su IP Azure: i 32 store `enabled: false` restituiscono 403 da lì. È atteso.
- Il cron di Actions ha ritardi di 5–15 minuti: non promettere precisione al minuto.
- Streamlit Community Cloud va in sleep: è la dashboard, **non** lo scheduler.
- Amazon vende "su invito": non è monitorabile ed è escluso by design.
