-- Запись еды из веб-пульта: event_id - пункт coach_events, связь без внешнего ключа (как 0029);
-- NULL - запись из CLI.
ALTER TABLE food_log ADD COLUMN event_id INTEGER;
