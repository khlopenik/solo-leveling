"""Фоновая проверка неактивности игроков: напоминания и штраф к характеристикам.

Штраф применяется не напрямую (бот не видит локальные данные приложения),
а копится в колонке players.pending_penalty — мини-апп считывает её при
следующем открытии (cloudInit -> applyPendingPenalty в index.html) и сама
вычитает процент из статов, после чего подтверждает через action=ack_penalty.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SCHEMA = "solo_leveling"
ASSETS_DIR = Path(__file__).parent / "assets" / "achievements"

# (порог в часах с последней синхронизации, картинка, штраф в эксп (флэт), текст)
# числа взяты из артов g7_* (там переделан текст "HP" -> "ЭКСП", сами цифры —
# авторские от Любы); штраф режет накопленный эксп при следующем заходе —
# см. applyPendingPenalty() в index.html; бонус за возврат (COMEBACK_BONUS=20)
# всегда меньше минимального штрафа (100), так что уйти специально невыгодно
TIERS = [
    (12, "g7_r0_c0.png", 100,
     "Хехехе… уже 12 часов? Как быстро ты забываешь о своей системе.\n\n"
     "Штраф при следующем заходе: −100 эксп."),
    (24, "g7_r0_c1.png", 250,
     "Целые сутки без тебя. Твой рост остановился, твой эксп утекает.\n\n"
     "Штраф при следующем заходе: −250 эксп."),
    (66, "g7_r0_c2.png", 0,
     "Осталось 6 часов до следующего штрафа. Время идёт, Охотник, "
     "не заставляй ждать слишком долго."),
    (69, "g7_r0_c3.png", 150,
     "Осталось 3 часа. Последнее предупреждение — если не вернёшься, "
     "твоя сила будет отнята.\n\n"
     "Штраф при следующем заходе: −150 эксп."),
    (72, "g7_r1_c0.png", 500,
     "3 дня без тебя. Ты действительно думаешь, что можешь просто исчезнуть?\n\n"
     "Штраф при следующем заходе: −500 эксп."),
    (168, "g7_r1_c1.png", 1000,
     "Неделю ты променял развитие на ничтожество. Жалкое зрелище.\n\n"
     "Штраф при следующем заходе: −1000 эксп."),
    (336, "g7_r1_c2.png", 2000,
     "Две недели. Ты позабыл о своей цели — твоя система считает тебя "
     "недостойным.\n\n"
     "Штраф при следующем заходе: −2000 эксп."),
]


def _headers(write=False):
    h = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    h["Content-Profile" if write else "Accept-Profile"] = SCHEMA
    return h


def _fetch_tg_players():
    if not SUPABASE_SERVICE_KEY:
        logger.warning("SUPABASE_SERVICE_KEY не задан — проверка неактивности пропущена")
        return []
    url = f"{SUPABASE_URL}/rest/v1/players"
    params = {
        "select": "device_id,name,updated_at,last_warned_tier,pending_penalty",
        "device_id": "like.tg*",
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch_player(device_id, last_warned_tier, pending_penalty):
    url = f"{SUPABASE_URL}/rest/v1/players"
    r = requests.patch(
        url,
        headers={**_headers(write=True), "Content-Type": "application/json"},
        params={"device_id": f"eq.{device_id}"},
        json={"last_warned_tier": last_warned_tier, "pending_penalty": pending_penalty},
        timeout=15,
    )
    r.raise_for_status()


async def check_inactivity(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        players = _fetch_tg_players()
    except requests.RequestException:
        logger.exception("Не удалось получить список игроков для проверки неактивности")
        return

    now = datetime.now(timezone.utc)
    for p in players:
        device_id = p.get("device_id") or ""
        if not device_id.startswith("tg"):
            continue
        try:
            tg_id = int(device_id[2:])
        except ValueError:
            continue

        updated_at = p.get("updated_at")
        if not updated_at:
            continue
        last_sync = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        hours_inactive = (now - last_sync).total_seconds() / 3600

        last_tier = p.get("last_warned_tier") or 0
        pending = p.get("pending_penalty") or 0
        new_tier = last_tier
        penalty_add = 0

        for i, (threshold, img, pct, text) in enumerate(TIERS, start=1):
            if i <= last_tier or hours_inactive < threshold:
                continue
            try:
                photo_path = ASSETS_DIR / img
                with open(photo_path, "rb") as f:
                    await context.bot.send_photo(chat_id=tg_id, photo=f, caption=text)
            except Exception:
                logger.exception("Не удалось отправить напоминание о неактивности игроку %s", tg_id)
            new_tier = i
            penalty_add += pct

        if new_tier != last_tier:
            try:
                _patch_player(device_id, new_tier, pending + penalty_add)
            except requests.RequestException:
                logger.exception("Не удалось обновить штраф неактивности для %s", device_id)
