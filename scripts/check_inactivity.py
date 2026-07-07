"""Разовая проверка пропущенных дней квеста — запускается по расписанию
GitHub Actions (.github/workflows/bot-inactivity.yml), а не постоянным
процессом. Никакого сервера/Render не требуется.

Триггер — НЕ время последнего открытия приложения (можно открыть и не
выполнить квест), а дата последнего ПОЛНОСТЬЮ закрытого дня (state.streakDate).
Если игрок зашёл, но квест не выполнил — день всё равно считается пропущенным.

Расписание чистое, по дням, без рваных часовых порогов: 1, 2, 3, 5, 7, 14, 30
дней пропуска — ровно одно сообщение на каждый порог, без повторов и без
случайного смещения (крон раз в час — сообщение приходит максимум с
опозданием в час после полуночи, когда день засчитался пропущенным).

Шлёт сообщения напрямую через Telegram Bot API (без python-telegram-bot —
он нужен только живому боту, а здесь обычный HTTP-запрос).
"""

import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SCHEMA = "solo_leveling"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "achievements"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# (дней пропущено подряд, картинка, штраф в эксп (флэт))
# Картинки: 102=24ч, 101=12ч (другой стиль), 105=3д, 106_left=7д, 106_right=14д, 107=финал
TIERS = [
    (1,  "ach_102.png",       100),
    (2,  "ach_101.png",       250),
    (3,  "ach_105.png",       500),
    (5,  "ach_105.png",       750),
    (7,  "ach_106_left.png",  1000),
    (14, "ach_106_right.png", 1500),
    (30, "ach_107.png",       2500),
]


def _tier_text(days, pct, new_exp):
    return (
        f"⚠ Ты не выполнял ежедневный квест {days} "
        f"{'день' if days == 1 else 'дня' if days < 5 else 'дней'} подряд. "
        f"Серия сгорела.\n\nШтраф: −{pct} эксп (сейчас: {new_exp})."
    )


def _headers(write=False):
    h = {"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    h["Content-Profile" if write else "Accept-Profile"] = SCHEMA
    return h


def _fetch_tg_players():
    url = f"{SUPABASE_URL}/rest/v1/players"
    params = {
        "select": "device_id,name,exp,updated_at,last_warned_tier,pending_penalty,state",
        "device_id": "like.tg*",
    }
    r = requests.get(url, headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch_player(device_id, last_warned_tier, pending_penalty, exp=None, state=None):
    """Штраф списывается отсюда же, сразу — рейтинг должен быть честным
    независимо от того, заходит ли игрок в приложение. exp/state передаём
    только когда меняем сам exp, чтобы не перетирать state лишний раз."""
    body = {"last_warned_tier": last_warned_tier, "pending_penalty": pending_penalty}
    if exp is not None:
        body["exp"] = exp
    if state is not None:
        body["state"] = state
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


def _last_completed_date(player_row):
    """Дата последнего дня, когда квест был закрыт на 100% (streakDate из state).
    Если такой даты нет (игрок никогда не закрывал день) — берём дату последней
    синхронизации как нейтральный старт отсчёта, чтобы не спамить с первого дня."""
    state = player_row.get("state") or {}
    streak_date = state.get("streakDate")
    if streak_date:
        try:
            return date.fromisoformat(streak_date[:10])
        except ValueError:
            pass
    updated_at = player_row.get("updated_at")
    if updated_at:
        try:
            return datetime.fromisoformat(updated_at.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return None


def main():
    try:
        players = _fetch_tg_players()
    except requests.RequestException:
        logger.exception("Не удалось получить список игроков")
        sys.exit(1)

    today = datetime.now(timezone.utc).date()
    for p in players:
        device_id = p.get("device_id") or ""
        if not device_id.startswith("tg"):
            continue
        try:
            tg_id = int(device_id[2:])
        except ValueError:
            continue

        last_completed = _last_completed_date(p)
        if last_completed is None:
            continue
        days_missed = (today - last_completed).days

        last_tier = p.get("last_warned_tier") or 0
        new_tier = last_tier

        if days_missed == 0 and last_tier:
            # игрок вернулся и снова закрыл день — сбрасываем счётчик предупреждений,
            # иначе при следующем срыве серии тиры 1/2 будут молча пропущены
            try:
                _patch_player(device_id, 0, 0)
            except requests.RequestException:
                logger.exception("Не удалось сбросить тир предупреждений для %s", device_id)
            continue

        cur_exp = p.get("exp") or 0
        state = dict(p.get("state") or {})
        penalty_total = 0

        for i, (threshold_days, img, pct) in enumerate(TIERS, start=1):
            if i <= last_tier or days_missed < threshold_days:
                continue
            new_exp = max(0, cur_exp - pct)
            try:
                _send_photo(tg_id, img, _tier_text(threshold_days, pct, new_exp))
            except Exception:
                logger.exception("Не удалось отправить напоминание игроку %s", tg_id)
            cur_exp = new_exp
            new_tier = i
            penalty_total += pct

        if new_tier != last_tier:
            # штраф списываем тут же, и в колонке exp, и внутри state.exp (иначе
            # при следующем входе игрока его клиент перетрёт exp обратно из state) —
            # рейтинг читает колонку exp, она должна быть честной без захода игрока
            state["exp"] = cur_exp
            try:
                _patch_player(device_id, new_tier, 0, exp=cur_exp, state=state)
            except requests.RequestException:
                logger.exception("Не удалось списать штраф для %s", device_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
