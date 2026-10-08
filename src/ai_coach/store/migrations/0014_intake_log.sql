-- Журнал приёма: пока только добавки (kind 'supplement'); курсы med - позже.
-- Только добавление: несколько приёмов в день разрешены, удаление - пометка deleted_at.
-- item_id - id строки таблицы по kind (без внешнего ключа: таблиц будет две).
-- dose NULL - принято по норме добавки; date - день приёма YYYY-MM-DD, taken_at - когда записано.
CREATE TABLE intake_log (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('supplement')),
    item_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    dose REAL CHECK (dose IS NULL OR dose > 0),
    note TEXT,
    deleted_at TEXT
);
CREATE INDEX intake_log_date ON intake_log (date);
