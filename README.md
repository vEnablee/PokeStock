# PokeStock

Monitor di disponibilità per Elite Trainer Box Pokémon presso e-commerce
italiani. Avvisa su Telegram quando un prodotto torna disponibile entro una
soglia di prezzo definita.

## Come funziona

Un cronjob esterno risveglia un workflow su GitHub Actions, che interroga i
negozi configurati, confronta il risultato con lo stato dell'esecuzione
precedente e notifica solo le novità. Lo stato persiste su un GitHub Gist.

```
cron-job.org ──> GitHub Actions ──> negozi ──> Telegram
                       ↕
                   Gist (stato)
                       ↕
                  dashboard Streamlit
```

Le notifiche partono **solo sulla transizione** da esaurito a disponibile: un
prodotto già in stock non genera avvisi ripetuti.

## Avvio rapido

```bash
make setup       # virtualenv e dipendenze
make test        # test offline, nessuna richiesta di rete
make scan        # scansione completa senza inviare notifiche
make dashboard   # interfaccia su http://localhost:8501
```

La prima esecuzione è una **semina**: registra lo stato corrente senza inviare
nulla. Senza, il primo giro segnalerebbe ogni prodotto già disponibile.

## Comandi

```bash
python app.py --dry-run           # scansiona e stampa, non invia
python app.py --run               # scansione completa con notifiche
python app.py --seed              # riallinea lo stato senza notificare
python app.py --test-telegram     # verifica token e chat id
python app.py --store ID          # un solo negozio, per diagnosi
python app.py --dry-run --cache   # usa la cache locale: nessun traffico
python app.py --list-stores       # elenco dei negozi configurati
```

## Configurazione

Tutto vive in `stores.json`: nessun dominio, parola chiave o soglia di prezzo
è scritta nel codice.

### Prodotti da monitorare

```json
{
  "id": "etb_30th",
  "max_price_eur": 64.90,
  "must_contain_all": [],
  "must_contain_any_groups": [
    ["fuoriclasse", "elite trainer box", "etb"],
    ["anniversario", "celebration"],
    ["30", "30esimo", "30°", "30th"]
  ],
  "must_not_contain": ["bundle", "tin", "blister"]
}
```

- `must_contain_all` — tutte presenti
- `must_contain_any_groups` — almeno una per ogni gruppo (gruppi in AND,
  parole in OR)
- `must_not_contain` — una sola presenza scarta il prodotto

**Il confronto avviene a confine di parola.** Non è un dettaglio: con il match
a sottostringa `tin` ricade dentro `bustine` e `30` dentro `3039`. Di
conseguenza `30` non corrisponde a `30th` né a `30esimo`, che vanno elencati a
parte. I casi limite sono bloccati da `tests/test_matching.py`.

### Negozi

Ogni negozio dichiara un adapter:

| `type` | Sorgente dei dati |
|---|---|
| `shopify` | `/products.json`, oppure una singola collection |
| `woocommerce_store_api` | API Store di WooCommerce |
| `vtex` | API catalogo VTEX |
| `html_schema_org`, `html_generic` | JSON-LD o marcatori nel markup |
| `html_embedded_json` | dati di prodotto incorporati nel sorgente |
| `html_sitemap` | sitemap filtrata |

I negozi disattivati restano nel file con il motivo in `disabled_reason`, così
la diagnosi non va persa.

## Esecuzione automatica

### Secret del repository

| Secret | Origine |
|---|---|
| `TELEGRAM_TOKEN` | @BotFather |
| `TELEGRAM_CHAT_ID` | id della chat o del canale |
| `GIST_TOKEN` | token *classic* con il solo scope `gist` |
| `GIST_ID` | generato al primo avvio |

I token fine-grained non coprono i Gist: per `GIST_TOKEN` serve un token
classic.

### Primo avvio

1. Esegui il workflow con `crea_gist: true` — crea il Gist e ne stampa l'id
2. Salva l'id come secret `GIST_ID`
3. Esegui con `seed: true` per registrare lo stato iniziale
4. Verifica con `test_telegram: true`

Il Gist è necessario perché su GitHub Actions il filesystem è effimero: senza
memoria esterna ogni esecuzione ripartirebbe da zero e rispedirebbe le stesse
notifiche.

### Trigger

Lo `schedule:` di GitHub è impreciso e tenerne due in parallelo rende
imprevedibile l'orario reale. Il workflow è quindi `workflow_dispatch` puro,
svegliato da un cronjob esterno:

```
POST https://api.github.com/repos/<owner>/<repo>/actions/workflows/monitor.yml/dispatches
body    {"ref":"main"}
header  Authorization: Bearer <token con permesso Actions: read and write>
        Accept: application/vnd.github+json
```

Una risposta `204 No Content` indica che il workflow è partito.

## Dashboard

```bash
make dashboard
```

Tre schede: i prodotti disponibili in griglia, l'andamento dei prezzi con il
confronto rispetto alla soglia, e la configurazione di soglie, parole chiave e
negozi.

Da qui si decide anche **se e per quali prodotti ricevere notifiche**: le
preferenze vengono salvate nello stato condiviso, quindi il monitor le applica
dal giro successivo.

Per pubblicarla su Streamlit Community Cloud servono `GIST_TOKEN` e `GIST_ID`
fra i secret dell'app: sul cloud il file di stato locale non esiste, e i dati
arrivano dal Gist.

## Comportamento verso i negozi

Il monitor interroga pochi negozi in parallelo, distanzia le richieste allo
stesso dominio e applica un ritardo casuale. Un HTTP 429 viene trattato come
errore ritentabile.

Dopo alcuni fallimenti consecutivi un negozio entra in **quarantena**: viene
saltato per qualche giro e poi ritentato, con un avviso Telegram. Se in una
singola esecuzione cade oltre metà dei negozi, parte un allarme dedicato: in
quel caso di solito il problema è a monte, non nei negozi.

In sviluppo, `--cache` conserva le risposte su disco e permette di iterare sul
codice senza generare traffico.

## Limiti noti

- Alcuni negozi rispondono agli IP residenziali ma non a quelli dei datacenter:
  su GitHub Actions restano irraggiungibili.
- Gli adapter HTML dipendono dal markup e vanno rivisti se un negozio cambia
  tema.
- I marketplace che vendono su invito non sono osservabili e sono esclusi.
- Streamlit Community Cloud sospende le app inattive: è una dashboard, non uno
  scheduler.

## Struttura

```
stores.json        configurazione: negozi, prodotti, soglie
app.py             CLI e dashboard
monitor/
  config.py        caricamento e validazione
  matching.py      confronto a confine di parola
  adapters.py      un adapter per piattaforma
  state.py         stato persistente e preferenze
  gist.py          persistenza remota
  notifier.py      Telegram
  runner.py        orchestrazione
  cache.py         cache HTTP per lo sviluppo
dashboard/         interfaccia Streamlit
tests/             test offline
```
