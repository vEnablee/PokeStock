"""Invio notifiche Telegram via API Bot HTTP."""
from __future__ import annotations

import os
from datetime import datetime

import httpx

API = "https://api.telegram.org/bot{token}/sendMessage"


class Telegram:
    def __init__(self, cfg, *, dry_run: bool = False):
        self.cfg = cfg.telegram
        self.token = os.environ.get("TELEGRAM_TOKEN", "").strip()
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or os.environ.get("CHAT_ID", "").strip()
        self.dry_run = dry_run
        self.sent = 0

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _render(self, template_key: str, **values) -> str:
        template = self.cfg.get(template_key, "")
        try:
            return template.format(**values)
        except KeyError as exc:
            return f"{template_key}: placeholder mancante {exc}"

    async def send(self, client: httpx.AsyncClient, text: str) -> bool:
        if self.dry_run:
            print(f"[DRY-RUN telegram]\n{text}\n{'-' * 60}")
            self.sent += 1
            return True
        if not self.configured:
            print("[telegram] TELEGRAM_TOKEN / TELEGRAM_CHAT_ID non impostati: notifica saltata")
            return False
        try:
            r = await client.post(
                API.format(token=self.token),
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": self.cfg.get("parse_mode", "Markdown"),
                    "disable_web_page_preview": self.cfg.get("disable_web_page_preview", False),
                },
                timeout=20,
            )
            if r.status_code != 200:
                print(f"[telegram] errore {r.status_code}: {r.text[:200]}")
                return False
            self.sent += 1
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[telegram] invio fallito: {exc}")
            return False

    async def product_alert(self, client, product, target) -> bool:
        text = self._render(
            "message_template",
            store_name=product.store_name,
            product_title=product.title,
            price=f"{product.price:.2f}".replace(".", ",") if product.price is not None else "n/d",
            msrp=f"{target.get('msrp_eur', 0):.2f}".replace(".", ","),
            target_name=target.get("name", target.get("id", "")),
            product_url=product.url,
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        return await self.send(client, text)

    async def store_error(self, client, store_id, error, stato) -> bool:
        text = self._render("error_template", store_id=store_id, error=str(error)[:200],
                            stato=stato)
        return await self.send(client, text)
