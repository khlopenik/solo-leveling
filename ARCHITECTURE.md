# Solo Leveling App — Архитектура

## Из чего состоит приложение
1. **Фронтенд (Telegram мини-апп)** — `index.html` (пока прототип) → станет реальным мини-аппом.
   Открывается внутри Telegram, общается с бэкендом через Supabase JS / API.
2. **База данных (Supabase / Postgres)** — проект `solo-leveling`.
   Схема: `supabase/migrations/001_init.sql` + сиды `002_seed.sql`.
3. **Telegram-бот (Python)** — вход в мини-апп, уведомления (квесты/пинки/ДР), рассылки.
   Стек как у FRAME-бота. Бот: **@solo_leveling_fit_bot** (токен в .env, защищён .gitignore).
   TODO: перевыпустить токен через @BotFather (был вставлен в чат при настройке).
4. **AI-сервисы** — vision для фото→калории и анализа тела (GPT/Claude vision), генерация артов (MuAPI).

## Таблицы БД (кратко)
- `players` — игроки (профиль, уровень, exp, ранг, серия, нормы, 5 флагов приватности)
- `exercises` — каталог упражнений по 4 сферам (strength/agility/intellect/health)
- `player_quest` — выбранный игроком ежедневный квест (+ свои упражнения)
- `quest_logs` — выполнение квеста по дням (exp за день)
- `meals` — дневник питания (ккал/БЖУ, источник manual/photo)
- `water_logs` — вода/напитки (объём + усвоение)
- `body_metrics` — состав тела/взвешивания (вес, жир%, мышцы, вода…)
- `measurements` — замеры сантиметром (11 параметров)
- `friendships` / `clans` / `clan_members` / `parties` — соц-граф
- `achievements` / `player_achievements` — достижения

## База данных — реквизиты
- Проект Supabase: **club-subscriptions** (ref `omiomgwwjuudjqjdggdk`), регион eu-west-1
- Схема: **solo_leveling** (изолирована от таблицы клуба public.subscribers)
- Причина: бесплатный лимит 2 активных проекта (frame-bot + club-subscriptions);
  отдельный проект solo-leveling создадим при апгрейде до Pro, тогда перенесём схему.
- frame-video-studio — УДАЛЕНА (была не нужна). Схему изначально ставили в frame-bot, потом
  перенесли в club-subscriptions (по просьбе) и убрали из frame-bot.

## Статус
- [x] Схема БД написана и ПРИМЕНЕНА (14 таблиц в solo_leveling + сиды: 16 упражнений, 14 достижений)
- [ ] БЕЗОПАСНОСТЬ: включить RLS + политики ДО подключения живых юзеров (сейчас RLS off, но схема не
      открыта в API и таблицы пусты — не опасно)
- [ ] Открыть схему solo_leveling в API (Dashboard → Settings → API → Exposed schemas) ИЛИ работать через бота
- [ ] Подключить фронтенд к Supabase (заменить слой DB localStorage → Supabase)
- [ ] Подключить фронтенд к Supabase (чтение/запись реальных данных)
- [ ] Telegram-бот + мини-апп регистрация
- [ ] AI vision (еда, тело), MuAPI (арт)

## Порядок сборки (план)
1. Поднять БД (миграции) — ФУНДАМЕНТ
2. Фронт читает/пишет: онбординг → players, квест → player_quest/quest_logs
3. Питание/вода/вес → соответствующие таблицы
4. Рейтинг/друзья/кланы/пати
5. Telegram-бот: вход + уведомления
6. AI: фото→калории, анализ тела; арт/аватар
