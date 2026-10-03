"""Monitor disponibilita' ETB Pokemon presso e-commerce italiani.

Tutta la configurazione vive in stores.json: questo pacchetto non contiene
domini, keyword o soglie di prezzo hardcodati.
"""
__all__ = ["config", "matching", "adapters", "state", "notifier", "runner"]
