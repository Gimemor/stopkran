-- Демо-данные для локальной ленты. Добавляются только если таблица пуста.
insert into public.requests (owner_id, title, amount, reason, alternative)
select * from (values
  ('dev_1', 'Наушники Sony WH-1000XM5', 29990.00,
   'Старые сломались, а скидка только до вечера', 'Взять б/у за 18 000'),
  ('dev_2', 'Кофемашина De''Longhi', 54000.00,
   'Хочу как в кофейне, пью кофе каждый день', 'Пить растворимый ещё месяц'),
  ('dev_3', 'Курс по Python', 12000.00,
   'Обещают оффер через 3 месяца', 'Дочитать бесплатный туториал')
) as seed(owner_id, title, amount, reason, alternative)
where not exists (select 1 from public.requests);

insert into public.votes (request_id, user_id, side, comment)
select r.id, v.user_id, v.side, v.comment
from public.requests r
join (values
  ('dev_1', 'dev_9', 'against', 'Подожди неделю — скидки будут и в чёрную пятницу'),
  ('dev_1', 'dev_8', 'for',     'Если работаешь в шумном офисе — это инструмент'),
  ('dev_2', 'dev_9', 'against', '54 тысячи за кофе дома — считай зёрна'),
  ('dev_3', 'dev_7', 'for',     'Дешевле любого курса, который я видел')
) as v(owner_id, user_id, side, comment) on r.owner_id = v.owner_id
where not exists (select 1 from public.votes);
