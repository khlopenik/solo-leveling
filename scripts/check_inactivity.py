"""Разовая проверка пропущенных дней квеста — запускается по расписанию
GitHub Actions (.github/workflows/bot-inactivity.yml), а не постоянным
процессом. Никакого сервера/Render не требуется.

Триггер — реальное время с момента последнего ПОЛНОСТЬЮ закрытого дня
(state.lastFullDayAt, точный timestamp, не дата), а не время последнего
открытия приложения (можно открыть и не выполнить квест).

Лестница по часам с момента последнего закрытого дня:
  6ч/9ч  — предупреждения (без штрафа, картинки 103/104)
  12ч/24ч/3д/7д/14д — реальные тиры со штрафом (картинки 102/101/105/106_left/106_right)

Штраф — НЕ списание XP и НЕ проценты, а временный флэт-дебафф всех 6
характеристик (см. index.html: renderStats() вычитает pending_penalty из
каждого стата). Дебафф заменяется на актуальный при достижении нового тира
(не суммируется) и снимается автоматически, как только игрок снова
закрывает день.

Важно: сброс тира раньше происходил только если крон успевал застать
игрока в узком окне "прошло меньше 6 часов с момента закрытия дня". Если
крон запускался реже (или игрок закрыл день, а следующий прогон случился
уже спустя 20+ часов), это окно проскакивало впустую, и старый тир от
ПРЕДЫДУЩЕГО цикла неактивности навсегда блокировал все следующие
предупреждения/штрафы, кроме самых дальних. Теперь дата последнего
закрытого дня, которую бот уже учёл (last_seen_full_day), хранится
отдельно — и сброс тира происходит при любом обнаружении НОВОГО
закрытого дня, независимо от того, сколько часов прошло с момента
прогона крона.

Шлёт сообщения напрямую через Telegram Bot API (без python-telegram-bot —
он нужен только живому боту, а здесь обычный HTTP-запрос).
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCHEMA = "solo_leveling"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "achievements"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# (тир, часов с последнего закрытого дня, картинка, штраф в очках ко всем характеристикам)
# Штраф не накапливается — при новом тире просто заменяет предыдущий.
# Тиры 1-2 — только предупреждения (штраф 0), реальный штраф начинается с тира 3 (12ч).
TIERS = [
    (1, 6,   "ach_103.png",       0),
    (2, 9,   "ach_104.png",       0),
    (3, 12,  "ach_102.png",       1),
    (4, 24,  "ach_101.png",       2),
    (5, 72,  "ach_105.png",       3),
    (6, 168, "ach_106_left.png",  5),
    (7, 336, "ach_106_right.png", 8),
]

_TIER_TEXT = {
    1: "⏳ Осталось 6 часов, охотник. Не заставляй Систему ждать слишком долго — закрой сегодняшний квест.",
    2: "⚠ Последнее предупреждение — осталось 3 часа. Если не вернёшься, характеристики просядут.",
    3: "😈 Ты не заходил 12 часов. Система начинает скучать, твоя тень слабеет.\n\nШтраф: −{pct} ко всем характеристикам.",
    4: "😈 Целые сутки без тебя... рост остановился, сила утекает.\n\nШтраф: −{pct} ко всем характеристикам.",
    5: "😈 3 дня без тебя. Ты действительно думаешь, что можешь просто исчезнуть?\n\nШтраф: −{pct} ко всем характеристикам.",
    6: "😈 Неделю ты променял развитие на ничтожество.\n\nШтраф: −{pct} ко всем характеристикам.",
    7: "😈 Две недели... Твоя система считает тебя недостойным.\n\nШтраф: −{pct} ко всем характеристикам.",
}


def _tier_text(tier, pct):
    return _TIER_TEXT[tier].format(pct=pct)


def _headers(write=False):
    h = {"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    h["Content-Profile" if write else "Accept-Profile"] = SCHEMA
    return h


def _fetch_tg_players():
    url = f"{SUPABASE_URL}/rest/v1/players"
    params = {
        "select": "device_id,name,updated_at,last_warned_tier,pending_penalty,last_seen_full_day,state",
        "device_id": "like.tg*",
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch_player(device_id, last_warned_tier, pending_penalty, last_seen_full_day):
    body = {
        "last_warned_tier": last_warned_tier,
        "pending_penalty": pending_penalty,
        "last_seen_full_day": last_seen_full_day,
    }
    url = f"{SUPABASE_URL}/rest/v1/players"
    r = requests.patch(
        url,
        headers={**_headers(write=True), "Content-Type": "application/json"},
        params={"device_id": f"eq.{device_id}"},
        json=body,
        timeout=15,
    )
    r.raise_for_status()


def _send_photo(tg_id, img_name, caption):
    photo_path = ASSETS_DIR / img_name
    with open(photo_path, "rb") as f:
        r = requests.post(
            f"{TELEGRAM_API}/sendPhoto",
            data={"chat_id": tg_id, "caption": caption},
            files={"photo": f},
            timeout=20,
        )
    if not r.ok:
        logger.error("sendPhoto failed for %s: %s", tg_id, r.text)


def _last_full_day_at(player_row):
    """Точный момент последнего полностью закрытого дня (state.lastFullDayAt).
    Если его ещё нет (игрок ни разу не закрывал день целиком с момента
    обновления) — не проверяем неактивность вообще, чтобы не спамить
    свежих/старых игроков без этого поля."""
    state = player_row.get("state") or {}
    ts = state.get("lastFullDayAt")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_db_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def main():
    try:
        players = _fetch_tg_players()
    except requests.RequestException:
        logger.exception("Не удалось получить список игроков")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    for p in players:
        device_id = p.get("device_id") or ""
        if not device_id.startswith("tg"):
            continue
        try:
            tg_id = int(device_id[2:])
        except ValueError:
            continue

        last_full = _last_full_day_at(p)
        if last_full is None:
            continue
        hours_missed = (now - last_full).total_seconds() / 3600

        last_tier = p.get("last_warned_tier") or 0
        last_seen_full_day = _parse_db_ts(p.get("last_seen_full_day"))

        # обнаружили новый закрытый день с прошлого прогона — сбрасываем тир
        # немедленно, независимо от того, сколько часов уже прошло с этого
        # момента (раньше сброс происходил только в узком окне < 6ч)
        is_new_full_day = last_seen_full_day is None or last_full > last_seen_full_day
        if is_new_full_day:
            last_tier = 0

        if hours_missed < TIERS[0][1]:
            if last_tier != (p.get("last_warned_tier") or 0) or is_new_full_day:
                try:
                    _patch_player(device_id, 0, 0, last_full.isoformat())
                except requests.RequestException:
                    logger.exception("Не удалось сбросить тир предупреждений для %s", device_id)
            continue

        new_tier = last_tier
        new_penalty = float(p.get("pending_penalty") or 0) if not is_new_full_day else 0.0

        for tier, threshold_hours, img, points in TIERS:
            if tier <= last_tier or hours_missed < threshold_hours:
                continue
            try:
                _send_photo(tg_id, img, _tier_text(tier, points))
            except Exception:
                logger.exception("Не удалось отправить напоминание игроку %s", tg_id)
            new_tier = tier
            new_penalty = points

        if new_tier != (p.get("last_warned_tier") or 0) or is_new_full_day:
            try:
                _patch_player(device_id, new_tier, new_penalty, last_full.isoformat())
            except requests.RequestException:
                logger.exception("Не удалось обновить штраф для %s", device_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
