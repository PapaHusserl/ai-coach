-- Варианты блюд к пункту еды (веб-пульт): пишет тренер (MCP create_meal_offers), читает окно еды.
-- event_id - пункт coach_events, связь без внешнего ключа (как 0029); items_json - строки состава
-- [{what, qty, kcal, protein_g, fat_g, carbs_g}], итоги - сумма строк; groups_json - ключи групп
-- продуктов (словарь - CHECK 0020), уходят в запись еды при «Съел вариант».
CREATE TABLE meal_offer (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    items_json TEXT NOT NULL,
    kcal REAL NOT NULL,
    protein_g REAL NOT NULL,
    fat_g REAL NOT NULL,
    carbs_g REAL NOT NULL,
    groups_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);
CREATE INDEX meal_offer_item ON meal_offer (event_id, date);
