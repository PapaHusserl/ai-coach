-- Продукты дома: журнал. Записи только добавляются; остаток продукта — последний set плюс
-- сумма add минус сумма use после него.
CREATE TABLE pantry_log (
    id INTEGER PRIMARY KEY,
    item TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('g', 'ml', 'pcs')),
    op TEXT NOT NULL CHECK (op IN ('add', 'use', 'set')),
    logged_at TEXT NOT NULL,
    note TEXT
);
CREATE INDEX pantry_log_item ON pantry_log (item, logged_at);

-- Дни, за которые тренер уже предложил рацион на день (по одной записи на дату).
CREATE TABLE meal_plan_log (
    date TEXT PRIMARY KEY,
    logged_at TEXT NOT NULL
);
