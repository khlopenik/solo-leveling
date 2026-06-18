-- Стартовые данные: каталог упражнений и достижения

-- ===== Упражнения по 4 сферам =====
insert into exercises (sphere, name, default_target, xp, is_base) values
  ('strength','Приседания','5',50,true),
  ('strength','Отжимания','5',50,true),
  ('strength','Подтягивания','5',80,true),
  ('strength','Планка','60 сек',40,false),
  ('strength','Пресс','20',40,false),
  ('agility','Шаги','10000 шагов',30,true),
  ('agility','Бег','2 км',60,false),
  ('agility','Прыжки','30',30,false),
  ('agility','Скакалка','100',40,false),
  ('agility','Растяжка','10 мин',30,false),
  ('intellect','Чтение','5 стр.',40,true),
  ('intellect','Изучение языка','15 мин',40,false),
  ('intellect','Медитация','10 мин',30,false),
  ('health','Вода по норме','норма',30,true),
  ('health','Сон 8 часов','',40,false),
  ('health','День без сахара','',40,false)
on conflict do nothing;

-- ===== Достижения =====
insert into achievements (code, title) values
  ('awaken','Пробуждение'),
  ('streak_7','Серия 7 дней'),
  ('streak_30','Серия 30 дней'),
  ('streak_100','Серия 100 дней'),
  ('rank_d','Ранг D'),
  ('rank_c','Ранг C'),
  ('rank_b','Ранг B'),
  ('rank_a','Ранг A'),
  ('rank_s','Ранг S'),
  ('iron_will','Железная воля (100 отжиманий)'),
  ('first_kg','Минус первый кг'),
  ('clean_day','Чистый день (БЖУ в норме)'),
  ('early_bird','Ранняя пташка (питание по плану 7 дней)'),
  ('party_leader','Лидер пати')
on conflict do nothing;
