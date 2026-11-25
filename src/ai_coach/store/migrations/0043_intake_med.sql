-- Журнал приёма: к добавкам (supplement) добавлены курсы (med), приём курса пишет и снимает пульт.
-- SQLite не умеет менять CHECK, поэтому таблица пересоздаётся (как 0023); строки переносятся как есть.
-- item_id - без внешнего ключа, как в 0014.
CREATE TABLE intake_log_new (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('supplement', 'med')),
    item_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    dose REAL CHECK (dose IS NULL OR dose > 0),
    note TEXT,
    deleted_at TEXT
);
INSERT INTO intake_log_new (id, kind, item_id, date, taken_at, dose, note, deleted_at)
    SELECT id, kind, item_id, date, taken_at, dose, note, deleted_at FROM intake_log;
DROP TABLE intake_log;
ALTER TABLE intake_log_new RENAME TO intake_log;
CREATE INDEX intake_log_date ON intake_log (date);
