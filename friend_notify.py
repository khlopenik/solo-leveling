"""Пуш-уведомления в Telegram при новой заявке в друзья.

Бот не видит мини-апп напрямую, поэтому раз в пару минут опрашивает
solo_leveling.friend_requests на новые pending-заявки (notified=false),
шлёт получателю сообщение и помечает заявку notified=true, чтобы не
дублировать.
"""

import logging
import os

import requests
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SCHEMA = "solo_leveling"
APP_URL = "https://khlopenik.github.io/solo-leveling/"


def _headers(write=False):
    h = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    h["Content-Profile" if write else "Accept-Profile"] = SCHEMA
    return h


def _fetch_unnotified_requests():
    url = f"{SUPABASE_URL}/rest/v1/friend_requests"
    params = {
        "select": "requester_uid,recipient_uid",
        "status": "eq.pending",
        "notified": "eq.false",
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


def _mark_notified(requester_uid, recipient_uid):
    url = f"{SUPABASE_URL}/rest/v1/friend_requests"
    r = requests.patch(
        url,
        headers={**_headers(write=True), "Content-Type": "application/json"},
        params={
            "requester_uid": f"eq.{requester_uid}",
            "recipient_uid": f"eq.{recipient_uid}",
        },
        json={"notified": True},
        timeout=15,
    )
    r.raise_for_status()


async def check_friend_requests(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE_SERVICE_KEY не задан — проверка заявок в друзья пропущена")
        return
    try:
        requests_ = _fetch_unnotified_requests()
    except requests.RequestException:
        logger.exception("Не удалось получить список заявок в друзья")
        return

    for req in requests_:
        requester_uid = req.get("requester_uid") or ""
        recipient_uid = req.get("recipient_uid") or ""
        if not recipient_uid.startswith("tg"):
            # получателю нечего слать — он не из Telegram (гость в браузере)
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
        try:
            await context.bot.send_message(
                chat_id=tg_id,
                text=(
                    f"🔔 {requester_name} хочет добавить тебя в друзья!\n\n"
                    "Открой Систему → Рейтинг → Друзья, чтобы принять или отклонить заявку."
                ),
            )
        except Exception:
            logger.exception("Не удалось отправить уведомление о заявке игроку %s", tg_id)
            continue
        try:
            _mark_notified(requester_uid, recipient_uid)
        except requests.RequestException:
            logger.exception("Не удалось пометить заявку как обработанную")
