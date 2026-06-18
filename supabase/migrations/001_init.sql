-- Solo Leveling App — начальная схема базы данных
-- Применять в проекте Supabase "solo-leveling" (когда разблокируют создание проектов)

-- ============ ИГРОКИ ============
create table if not exists players (
  id           uuid primary key default gen_random_uuid(),
  tg_id        bigint unique,                 -- Telegram user id
  name         text not null,
  dob          date,                          -- дата рождения (для возраста + бонуса на ДР)
  sex          text check (sex in ('female','male')),
  height_cm    numeric,
  weight_kg    numeric,
  goal         text check (goal in ('lose','maintain','gain')),
  activity     text check (activity in ('beginner','medium','high')),
  level        int  not null default 1,
  exp          int  not null default 0,
  rank         text not null default 'E',     -- E,D,C,B,A,S
  streak       int  not null default 0,       -- серия дней подряд
  streak_best  int  not null default 0,
  -- нормы (считаются при онбординге)
  kcal_norm    int,
  water_norm_ml int,
  -- приватность (5 переключателей)
  pub_rating   boolean not null default true, -- участвовать в общем рейтинге
  pub_profile  boolean not null default true, -- показывать профиль
  pub_stats    boolean not null default true, -- показывать прокачку
  pub_body     boolean not null default false,-- показывать вес/состав тела
  pub_feed     boolean not null default true, -- показывать в ленте
  created_at   timestamptz not null default now()
);

-- ============ КАТАЛОГ УПРАЖНЕНИЙ ============
create table if not exists exercises (
  id        uuid primary key default gen_random_uuid(),
  sphere    text not null check (sphere in ('strength','agility','intellect','health')),
  name      text not null,
  default_target text,        -- напр. "5", "10000 шагов", "5 стр."
  xp        int not null default 40,
  is_base   boolean not null default true
);

-- ============ КВЕСТ ИГРОКА (выбранные упражнения) ============
create table if not exists player_quest (
  id           uuid primary key default gen_random_uuid(),
  player_id    uuid not null references players(id) on delete cascade,
  exercise_id  uuid references exercises(id),    -- null если своё упражнение
  sphere       text not null,
  name         text not null,                    -- денормализовано (для своих)
  target       text,
  xp           int not null default 40,
  is_custom    boolean not null default false,
  active       boolean not null default true,
  created_at   timestamptz not null default now()
);

-- ============ ЛОГ ВЫПОЛНЕНИЯ КВЕСТА (по дням) ============
create table if not exists quest_logs (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players(id) on delete cascade,
  quest_id    uuid not null references player_quest(id) on delete cascade,
  log_date    date not null default current_date,
  done        boolean not null default false,
  exp_earned  int not null default 0,
  created_at  timestamptz not null default now(),
  unique (quest_id, log_date)
);

-- ============ ПИТАНИЕ (дневник) ============
create table if not exists meals (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players(id) on delete cascade,
  eaten_at    timestamptz not null default now(),
  name        text not null,
  kcal        int,
  protein_g   numeric,
  fat_g       numeric,
  carb_g      numeric,
  source      text default 'manual' check (source in ('manual','photo')),
  photo_url   text,
  note        text
);

-- ============ ВОДА / НАПИТКИ ============
create table if not exists water_logs (
  id           uuid primary key default gen_random_uuid(),
  player_id    uuid not null references players(id) on delete cascade,
  logged_at    timestamptz not null default now(),
  drink_type   text not null default 'water', -- water,tea,coffee,juice
  volume_ml    int not null,
  effective_ml int not null                   -- с учётом коэффициента усвоения
);

-- ============ СОСТАВ ТЕЛА / ВЗВЕШИВАНИЯ ============
create table if not exists body_metrics (
  id            uuid primary key default gen_random_uuid(),
  player_id     uuid not null references players(id) on delete cascade,
  measured_at   timestamptz not null default now(),
  weight_kg     numeric,
  bmi           numeric,
  fat_pct       numeric,
  fat_mass_kg   numeric,
  skeletal_muscle_pct numeric,
  skeletal_muscle_kg  numeric,
  muscle_kg     numeric,
  water_pct     numeric,
  protein_pct   numeric,
  minerals_kg   numeric,
  visceral_fat  numeric,
  metabolism_kcal int,
  metabolic_age int,
  source        text default 'manual' check (source in ('manual','scale_photo','body_photo'))
);

-- ============ ЗАМЕРЫ САНТИМЕТРОМ ============
create table if not exists measurements (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players(id) on delete cascade,
  measured_at date not null default current_date,
  neck numeric, chest numeric, waist numeric, belly numeric,
  hips numeric, thigh numeric, biceps numeric, biceps_flex numeric,
  forearm numeric, calf numeric, wrist numeric
);

-- ============ ДРУЗЬЯ ============
create table if not exists friendships (
  id         uuid primary key default gen_random_uuid(),
  player_id  uuid not null references players(id) on delete cascade,
  friend_id  uuid not null references players(id) on delete cascade,
  status     text not null default 'pending' check (status in ('pending','accepted','blocked')),
  created_at timestamptz not null default now(),
  unique (player_id, friend_id)
);

-- ============ КЛАНЫ ============
create table if not exists clans (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  owner_id   uuid not null references players(id) on delete cascade,
  created_at timestamptz not null default now()
);
create table if not exists clan_members (
  clan_id    uuid not null references clans(id) on delete cascade,
  player_id  uuid not null references players(id) on delete cascade,
  role       text not null default 'member' check (role in ('owner','member')),
  primary key (clan_id, player_id)
);

-- ============ ПАТИ (бади 1-на-1) ============
create table if not exists parties (
  id         uuid primary key default gen_random_uuid(),
  player_a   uuid not null references players(id) on delete cascade,
  player_b   uuid not null references players(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- ============ ДОСТИЖЕНИЯ ============
create table if not exists achievements (
  id     uuid primary key default gen_random_uuid(),
  code   text unique not null,
  title  text not null,
  icon_url text
);
create table if not exists player_achievements (
  player_id      uuid not null references players(id) on delete cascade,
  achievement_id uuid not null references achievements(id) on delete cascade,
  earned_at      timestamptz not null default now(),
  primary key (player_id, achievement_id)
);

-- индексы под частые запросы
create index if not exists idx_meals_player_date on meals(player_id, eaten_at);
create index if not exists idx_water_player_date on water_logs(player_id, logged_at);
create index if not exists idx_body_player_date  on body_metrics(player_id, measured_at);
create index if not exists idx_questlog_player    on quest_logs(player_id, log_date);
