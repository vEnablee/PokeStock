# Comandi locali. Nessuno di questi fa deploy da nessuna parte.

.PHONY: help setup test scan scan-cached seed dashboard cache-clear cache-stats stores

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup:        ## crea il virtualenv e installa le dipendenze
	python3 -m venv .venv && .venv/bin/pip install -q -U pip && .venv/bin/pip install -q -r requirements.txt
	@echo "fatto. Attiva con: source .venv/bin/activate"

test:         ## test offline del matching (zero richieste di rete)
	python3 -m pytest tests/ -q 2>/dev/null || python3 tests/test_matching.py

scan:         ## scansione completa, dry-run (NON invia notifiche)
	python3 app.py --dry-run

scan-cached:  ## come sopra ma usando la cache: zero traffico sui rilanci
	python3 app.py --dry-run --cache

smoke:        ## test leggero su 3 soli store, con cache
	python3 app.py --dry-run --limit 3 --cache

seed:         ## riallinea lo stato senza notificare
	python3 app.py --seed

notify:       ## scansione VERA con invio su Telegram (richiede le env var)
	python3 app.py --run

dashboard:    ## avvia la dashboard Streamlit in locale
	streamlit run app.py

stores:       ## elenca gli store configurati
	python3 app.py --list-stores

cache-stats:  ## stato della cache
	python3 app.py --cache-stats

cache-clear:  ## svuota la cache
	python3 app.py --clear-cache
