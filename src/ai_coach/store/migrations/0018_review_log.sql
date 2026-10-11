-- Недельный обзор проведён: week_start - понедельник ISO-недели, done_at - когда, note - заметка (может быть пуста).
-- Повторный обзор той же недели заменяет запись.
CREATE TABLE review_log (
    week_start TEXT PRIMARY KEY,
    done_at TEXT NOT NULL,
    note TEXT
);
