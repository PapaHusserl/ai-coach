-- Срок годности продуктов: у записи поступления (add/set) дата expires_on (NULL - не портится или
-- срок неизвестен), opened - упаковка открыта (0/1). Новые операции: open (открыли упаковку,
-- новый срок, количество не меняется) и spoil (списание порчей, в остатке как use).
-- SQLite не умеет менять CHECK, поэтому таблица пересоздаётся.
CREATE TABLE pantry_log_new (
    id INTEGER PRIMARY KEY,
    item TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('g', 'ml', 'pcs')),
    op TEXT NOT NULL CHECK (op IN ('add', 'use', 'set', 'open', 'spoil')),
    logged_at TEXT NOT NULL,
    note TEXT,
    expires_on TEXT,
    opened INTEGER CHECK (opened IN (0, 1))
);
INSERT INTO pantry_log_new (id, item, qty, unit, op, logged_at, note)
    SELECT id, item, qty, unit, op, logged_at, note FROM pantry_log;
DROP TABLE pantry_log;
ALTER TABLE pantry_log_new RENAME TO pantry_log;
CREATE INDEX pantry_log_item ON pantry_log (item, logged_at);
