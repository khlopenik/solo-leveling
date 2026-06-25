"""Разовая проверка новых личных сообщений — пуш получателю в Telegram.
Запускается по расписанию GitHub Actions (.github/workflows/bot-new-messages.yml).
"""

import logging
import os
import sys

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCHEMA = "solo_leveling"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _headers(write=False):
    h = {"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    h["Content-Profile" if write else "Accept-Profile"] = SCHEMA
    return h


def _fetch_unnotified_messages():
    url = f"{SUPABASE_URL}/rest/v1/messages"
    params = {
        "select": "id,sender_uid,recipient_uid,text",
        "notified": "eq.false",
        "read": "eq.false",
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_player_name(device_id):
    url = f"{SUPABASE_URL}/rest/v1/players"
    params = {"select": "name", "device_id": f"eq.{device_id}"}
    r = requests.get(url, headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    rows = r.json()
    return rows[0]["name"] if rows else "Игрок"


def _mark_notified(msg_id):
    url = f"{SUPABASE_URL}/rest/v1/messages"
    r = requests.patch(
        url,
        headers={**_headers(write=True), "Content-Type": "application/json"},
        params={"id": f"eq.{msg_id}"},
        json={"notified": True},
        timeout=15,
    )
    r.raise_for_status()


def _send_message(tg_id, text):
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": tg_id, "text": text}, timeout=15)
    return r.ok


def main():
    try:
        msgs = _fetch_unnotified_messages()
    except requests.RequestException:
        logger.exception("Не удалось получить список новых сообщений")
        sys.exit(1)

    for m in msgs:
        recipient_uid = m.get("recipient_uid") or ""
        sender_uid = m.get("sender_uid") or ""
        if not recipient_uid.startswith("tg"):
            try:
                _mark_notified(m["id"])
            except requests.RequestException:
                logger.exception("Не удалось пометить сообщение как обработанное")
            continue
        try:
            tg_id = int(recipient_uid[2:])
        except ValueError:
            continue
        try:
            sender_name = _fetch_player_name(sender_uid)
        except requests.RequestException:
            sender_name = "Игрок"
        preview = (m.get("text") or "")[:200]
        ok = _send_message(
            tg_id,
            f"💬 {sender_name} написал тебе: «{preview}»\n\nОткрой Систему → Рейтинг → Чаты, чтобы ответить.",
        )
        if not ok:
            logger.error("Не удалось отправить уведомление о сообщении игроку %s", tg_id)
            continue
        try:
            _mark_notified(m["id"])
        except requests.RequestException:
            logger.exception("Не удалось пометить сообщение как обработанное")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
