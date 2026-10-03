# PokeStock

Monitor di disponibilità a prezzo di listino per Elite Trainer Box.

Monitora la disponibilità degli **Elite Trainer Box / Set Allenatore Fuoriclasse Pokémon**
presso **55 e-commerce italiani** e avvisa su Telegram **solo** quando un prodotto torna
disponibile **entro la soglia MSRP**.

> **Stato attuale: solo locale.** Non c'è nessun deploy configurato — niente GitHub Actions,
> niente Streamlit Cloud, niente cron-job.org. Si aggiungono quando lo decidi tu.

---

## Avvio rapido

```bash
make setup           # virtualenv + dipendenze
make test            # test offline del matching, zero richieste di rete
make smoke           # prova su 3 soli store, con cache
make scan            # scansione completa in dry-run, nessuna notifica inviata
make dashboard       # dashboard su http://localhost:8501
```

La prima scansione reale è un **seed**: registra lo stato di tutti i prodotti **senza
inviare nulla**. È voluto — senza, il primo giro sparerebbe decine di messaggi per
prodotti disponibili da giorni. Dal secondo giro in poi arrivano solo le transizioni
*esaurito → disponibile*.

## Non farsi bannare l'IP

Questo è il punto su cui il progetto è più attento, perché un ban lo rende inutile.

| Protezione | Dove | Valore |
|---|---|---|
| Store interrogati in parallelo | `settings.concurrency` | 4 |
| Pausa minima fra 2 richieste allo **stesso** dominio | `settings.min_seconds_between_requests_per_store` | 1,0 s |
| Ritardo casuale prima di ogni richiesta | `settings.jitter_seconds` | 0,3–1,5 s |
| Tetto di pagine prodotto per store HTML | `settings.max_product_pages` | 15 |
| HTTP 429 | gestito come errore ritentabile con backoff, mai ignorato | |
| Cache su disco | `--cache` | rilanci a costo zero |

**Regola pratica durante lo sviluppo: usa sempre `--cache`.**

```bash
python3 app.py --dry-run --cache     # 1° giro: scarica. 2° giro: 0 richieste di rete
python3 app.py --cache-stats
python3 app.py --clear-cache
```

Misurato: con cache attiva il secondo giro passa da 8,3 s a 0,6 s e **non tocca la rete**.
Per provare una modifica al codice servono zero richieste.

## Comandi

```bash
python3 app.py --dry-run              # scansiona e stampa, non invia niente
python3 app.py --dry-run --cache      # come sopra, senza traffico sui rilanci
python3 app.py --dry-run --limit 3    # solo i primi 3 store
python3 app.py --store cardgameclub   # un solo store, per debug
python3 app.py --seed                 # riallinea lo stato senza notificare
python3 app.py --run                  # scansione vera, invia su Telegram
python3 app.py --list-stores          # elenco store, con i motivi di quelli disattivati
streamlit run app.py                  # dashboard locale
```

## Telegram

Servono due variabili d'ambiente. In locale:

```bash
export TELEGRAM_TOKEN="123456:ABC..."     # da @BotFather
export TELEGRAM_CHAT_ID="-1001234567890"  # da @userinfobot, o l'id del canale
python3 app.py --run
```

Senza, lo scraper gira lo stesso e stampa che salta le notifiche. Con `--dry-run` i
messaggi vengono stampati a video già formattati, così controlli il testo prima.

Per prendere il `chat_id` di un canale: aggiungi il bot come amministratore, manda un
messaggio, poi apri `https://api.telegram.org/bot<TOKEN>/getUpdates`.

## Configurazione: `stores.json`

È l'unica fonte di verità. Nessun dominio, keyword o prezzo è hardcodato nel codice.

**Cambiare cosa monitorare** → sezione `targets`:

```json
{
  "id": "etb_30th",
  "max_price_eur": 64.90,
  "must_contain_all": [],
  "must_contain_any_groups": [
    ["fuoriclasse", "elite trainer box", "etb"],
    ["anniversario", "anniversary", "celebration"],
    ["30", "30esimo", "30°", "trentesimo", "30th"]
  ],
  "must_not_contain": ["megaevoluzione", "bundle", "tin", "..."]
}
```

- `must_contain_all` → tutte presenti (AND)
- `must_contain_any_groups` → almeno una per **ogni** gruppo (gruppi in AND, keyword in OR)
- `must_not_contain` → una sola presenza scarta il prodotto

**Il match è a confine di parola, sempre.** Non è un dettaglio: con il match a
sottostringa `"tin"` matcha dentro `bus**tin**e`, `Mar**tin**elia`, `Vic**tin**i`, e `"30"`
matcha dentro `3039`, `30cm`, `POS2**30**138`. Il primo collaudo produceva avvisi per un
*Topolino n. 3039* e un *set di trucchi Martinelia*. I casi sono congelati in
`tests/test_matching.py`.

Conseguenza da ricordare: `"30"` **non** matcha `30th` né `30esimo` (cifra seguita da
lettera = nessun confine). Per questo le varianti sono elencate separatamente.

**Cataloghi enormi**: se un negozio vende molto altro (una libreria ha migliaia di titoli),
aggiungi `"collections": ["pokemon"]` allo store: l'adapter interrogherà solo quella
collection. Su `giuntialpunto.it` il catalogo generale non contiene nemmeno un prodotto
Pokémon nelle prime 750 voci, mentre `/collections/pokemon` ne restituisce 101 in 0,8 s.

**Aggiungere un negozio** → sezione `stores`. Prima identifica la piattaforma:

```bash
curl -s "https://NEGOZIO.it/products.json?limit=3" | head -c 200                    # Shopify se è JSON
curl -s "https://NEGOZIO.it/wp-json/wc/store/v1/products?search=pokemon" | head -c 200  # WooCommerce se è JSON
```

| `type` | Endpoint | Campo disponibilità |
|---|---|---|
| `shopify` | `/products.json?limit=250&page=N`, oppure `/collections/<handle>/products.json` se lo store dichiara `collections` | `variants[].available` |
| `woocommerce_store_api` | `/wp-json/wc/store/v1/products?search=` | `is_in_stock`, prezzo **in centesimi** |
| `vtex` | `/api/catalog_system/pub/products/search?ft=` | `AvailableQuantity` |
| `html_schema_org` / `html_generic` / `html_prestashop` | `entry_points` → JSON-LD `Product` | `offers.availability` |
| `html_sitemap` | `sitemap_url` filtrata | marcatori testuali |

## Cosa c'è dentro

- **55 store attivi**: 30 Shopify, 15 WooCommerce, 10 da parsing HTML
- **42 store disabilitati** ma documentati con `disabled_reason` — non sono scarti:
  la maggior parte risponde 403 agli IP datacenter e tornerebbe utilizzabile da una
  connessione residenziale (CarteMagic, Gamelife, Il Covo del Nerd, LPP Collecting…)
- **4 rivenditori ufficiali** (fonte: `tcg.pokemon.com`)
- **15 negozi non specializzati**: giocattolerie, cartolerie, un'edicola, un negozio di
  informatica, un distributore e una catena di librerie da oltre 270 punti vendita.
  Sono i meno monitorati, e spesso tengono il prezzo di listino

Ogni store riporta `verified_at` e, dove serve, `verified_evidence`: la prova concreta
raccolta interrogandolo.

## Limiti noti, dichiarati

- Gli 11 store HTML sono i più fragili: dipendono dal markup e si rompono se il negozio
  cambia tema. `dadiemattoncini.it` ha i selettori ancora da rifinire.
- `packmonstore.it` risponde HTML al posto del JSON sotto rate limiting. Il codice valida
  il `Content-Type` prima di parsare, quindi fallisce in modo pulito invece di crashare.
- `e-stayon.com` è disabilitato: è VTEX ma l'endpoint pubblico standard non risponde.
- **Amazon è escluso per scelta**: i prodotti caldi sono venduti "su invito", quindi la
  disponibilità non è osservabile dalla pagina.
- Un prodotto può comparire in più target (`etb_30th` e `etb_qualsiasi`): viene notificato
  **una volta sola**, attribuito al target con `priority` più bassa.

## Dashboard

```bash
make dashboard          # streamlit run app.py  ->  http://localhost:8501
```

Tema dark con glassmorphism, CSS custom iniettato, griglia di card animate.
Tre schede:

**⚡ LIVE DROPS** — 4 KPI (prodotti monitorati, disponibili a MSRP, negozi che
rispondono, risparmio stimato) e una griglia responsive di card con immagine reale
del prodotto presa dal negozio, badge di stato, prezzo colorato (verde entro MSRP,
ambra sopra), scarto rispetto all'MSRP, badge dello store con la piattaforma, e
pulsante "ACQUISTA ORA" che apre la scheda nel negozio.

Animazioni: hover che solleva la card e accende il bordo, zoom dolce sull'immagine,
puntino verde pulsante quando c'è almeno un drop, comparsa in `fadeInUp` scaglionata,
skeleton con effetto shimmer durante la scansione.

**📈 STORICO & ANALYTICS** — dispersione dei prezzi per target (ogni punto è un
negozio, la linea tratteggiata è la soglia MSRP: tutto ciò che sta sopra è ricarico),
disponibilità per negozio, tabella min/mediana/max per target, log scaricabile in CSV.

**⚙️ NEGOZI & SOGLIE** — modifica soglie MSRP, attiva/disattiva target e negozi,
edita le parole chiave e aggiungi nuovi negozi, il tutto scritto su `stores.json`
con backup automatico in `stores.json.bak`.

**Sidebar** — ricerca nel titolo, filtro categoria e negozio, slider prezzo massimo,
disponibilità (tutti / solo disponibili / solo pre-ordini), toggle "solo entro MSRP",
numero di card mostrate, interruttore notifiche Telegram e "FORZA SCANSIONE ORA".

Il toggle Telegram è anche una sicurezza: se è spento la scansione gira in dry-run,
quindi dal browser non puoi far partire messaggi per sbaglio.

### Sul "risparmio stimato"

È la somma, sui prodotti disponibili entro MSRP, della differenza tra il prezzo
pagato e la **mediana dei listini sopra soglia per lo stesso target**. Uso la mediana
e non il massimo di proposito: in questo momento esiste un annuncio a 2.300 €, e
prenderlo come riferimento gonfierebbe il risparmio in modo ridicolo. Il numero
compare solo se ci sono almeno 3 listini sopra soglia da cui ricavarla.

Per calcolarlo lo scraper registra **anche** i prodotti fuori soglia (oggi 353 su 498),
che però non generano mai notifiche.

## Struttura

```
stores.json          configurazione verificata sul campo — unica fonte di verità
PROMPT.md            la specifica da cui è nato il progetto
app.py               CLI + dashboard Streamlit
monitor/
  config.py          caricamento e validazione
  matching.py        match a confine di parola, logica booleana dei target
  adapters.py        un adapter per piattaforma, con cache e rate limiting
  state.py           stato persistente: decide cosa notificare
  notifier.py        Telegram
  runner.py          orchestrazione di una scansione
  cache.py           cache HTTP su disco per sviluppare senza traffico
  models.py          Product, categorie, rilevamento pre-ordine
dashboard/
  styles.py          CSS custom: glassmorphism, keyframes, griglia
  components.py      HTML di KPI, card prodotto, skeleton
  views.py           le tre schede
tests/               test offline, zero richieste di rete
state.json           stato corrente (generato)
history.jsonl        storico append-only (generato)
```

## Esecuzione automatica

Lo schema è quello di Screeper: **un cronjob esterno sveglia GitHub Actions, che
scansiona e tiene la memoria su un Gist**.

```
cron-job.org ──POST .../actions/workflows/monitor.yml/dispatches──> GitHub Actions
  ogni 10 min                                                             │
  8:00–23:55 Europe/Rome                                                  ▼
                                                           legge lo stato dal Gist
                                                           scansiona i 59 negozi
                                                           notifica su Telegram
                                                           riscrive il Gist
```

**Perché non lo `schedule:` di GitHub.** Lo scheduler interno è notoriamente
impreciso e tenerne due in parallelo produce esecuzioni a orari imprevedibili
senza sapere chi le ha causate. Il workflow è `workflow_dispatch` puro.

**Perché il Gist.** Su Actions il filesystem è effimero: senza memoria esterna
ogni run ripartirebbe da zero e rispedirebbe notifiche per prodotti già visti.
Lo stato pesa 362 KB in chiaro e 48 KB compresso, dentro il limite di un Gist.

**Perché il repository è pubblico.** Con 96 run al giorno da circa 3,5 minuti si
consumano ~9.700 minuti al mese. Un repository pubblico ha minuti illimitati;
uno privato ne include 2.000, esauriti in poco più di sei giorni.

### Cosa serve configurare

**1. Secret del repository** (Settings → Secrets and variables → Actions):

| Secret | Dove si ottiene |
|---|---|
| `TELEGRAM_TOKEN` | @BotFather, creando un bot nuovo |
| `TELEGRAM_CHAT_ID` | @userinfobot, oppure l'id del canale |
| `GIST_TOKEN` | token fine-grained con il solo permesso **gist** |
| `GIST_ID` | si ottiene al primo run (vedi sotto) |

**2. Primo avvio — la semina.** Senza, il primo run invierebbe decine di
notifiche per prodotti disponibili da giorni:

```
Actions → Monitor ETB Pokémon → Run workflow → seed: true
```

Se `GIST_ID` è vuoto, il passo di salvataggio crea un Gist nuovo e ne stampa
l'id nel log come `::notice::`. Copialo nei secret e i run successivi lo useranno.

**3. Cronjob su cron-job.org:**

- URL: `https://api.github.com/repos/vEnablee/PokeStock/actions/workflows/monitor.yml/dispatches`
- Metodo: `POST`, body `{"ref": "main"}`
- Header: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`
- Il token è fine-grained, limitato a questo repository, permesso **Actions: read and write**
- Cadenza: ogni 10 minuti, 8:00–23:55, fuso Europe/Rome

### Protezioni automatiche

**Quarantena.** Dopo 4 fallimenti consecutivi un negozio viene saltato per i 6
giri successivi, poi ritentato, e parte un solo avviso Telegram nel momento in
cui ci entra. Insistere su un negozio che risponde 403 peggiora un eventuale
blocco e spreca tempo. Un successo azzera tutto.

**Interruttore globale.** Se in un solo giro cade almeno il 50% dei negozi (e
almeno 3), arriva un avviso dedicato: quando cadono tutti insieme di solito non
sono i negozi, è la rete o un blocco che riguarda noi.

**Niente sovrapposizioni.** Il blocco `concurrency` accoda i risvegli invece di
sovrapporli: due run scriverebbero lo stesso Gist.

**Rete di sicurezza.** Uno step `if: always()` ricarica lo stato sul Gist se il
run principale è morto a metà.

## Note sul deploy

GitHub Actions gira da IP Azure. Non è verificato se i negozi che oggi
rispondono bene da IP residenziale italiano si comportino allo stesso modo da
lì: se dopo i primi run compaiono quarantene a catena, il sospetto è quello.

Streamlit Community Cloud va in sleep dopo un periodo di inattività: è una
dashboard, non uno scheduler. Se la pubblichi lì, va fatta leggere **dal Gist**
e non dal file locale, altrimenti mostra dati fermi.
