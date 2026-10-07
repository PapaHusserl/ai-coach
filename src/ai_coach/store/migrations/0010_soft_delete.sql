-- Удаление записей веса и еды - пометка deleted_at (NULL - живая запись), строки остаются.
ALTER TABLE weight_log ADD COLUMN deleted_at TEXT;
ALTER TABLE food_log ADD COLUMN deleted_at TEXT;
