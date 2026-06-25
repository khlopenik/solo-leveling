"""Разовая проверка новых заявок в друзья — запускается по расписанию
GitHub Actions (.github/workflows/bot-friend-requests.yml). Шлёт пуш
получателю через Telegram Bot API напрямую, без живого процесса бота.
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


def _fetch_unnotified_requests():
    url = f"{SUPABASE_URL}/rest/v1/friend_requests"
    params = {"select": "requester_uid,recipient_uid", "status": "eq.pending", "notified": "eq.false"}
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


def _mark_notified(requester_uid, recipient_uid):
    url = f"{SUPABASE_URL}/rest/v1/friend_requests"
    r = requests.patch(
        url,
        headers={**_headers(write=True), "Content-Type": "application/json"},
        params={"requester_uid": f"eq.{requester_uid}", "recipient_uid": f"eq.{recipient_uid}"},
        json={"notified": True},
        timeout=15,
    )
    r.raise_for_status()


def _send_message(tg_id, text):
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": tg_id, "text": text}, timeout=15)
    return r.ok


def main():
    try:
        reqs = _fetch_unnotified_requests()
    except requests.RequestException:
        logger.exception("Не удалось получить список заявок в друзья")
        sys.exit(1)

    for req in reqs:
        requester_uid = req.get("requester_uid") or ""
        recipient_uid = req.get("recipient_uid") or ""
        if not recipient_uid.startswith("tg"):
            try:
                _mark_notified(requester_uid, recipient_uid)
            except requests.RequestException:
                logger.exception("Не удалось пометить заявку как обработанную")
            continue
        try:
            tg_id = int(recipient_uid[2:])
        except ValueError:
            continue
        try:
            requester_name = _fetch_player_name(requester_uid)
        except requests.RequestException:
            requester_name = "Игрок"
        ok = _send_message(
            tg_id,
            f"🔔 {requester_name} хочет добавить тебя в друзья!\n\n"
            "Открой Систему → Рейтинг → Друзья, чтобы принять или отклонить заявку.",
        )
        if not ok:
            logger.error("Не удалось отправить уведомление игроку %s", tg_id)
            continue
        try:
            _mark_notified(requester_uid, recipient_uid)
        except requests.RequestException:
            logger.exception("Не удалось пометить заявку как обработанную")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
