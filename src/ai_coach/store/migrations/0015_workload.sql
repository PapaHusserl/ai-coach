-- Нагрузка вне тренировок: события календаря и дневные счётчики (туду, груминг, позже ручные часы).
-- calendar_events: время местное без пояса, date - день начала; повторы делят uid, поэтому ключ
-- (source, uid, start_at). В raw_json нет участников и адресов.
-- day_counters: новый признак = новый kind без миграции, белый список kind - в store/workload.py.
CREATE TABLE calendar_events (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'apple_calendar',
    uid TEXT NOT NULL,
    date TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
    calendar TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('work', 'personal', 'hobby', 'rest', 'unknown')),
    title TEXT,
    status TEXT,
    my_status TEXT,
    synced_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE (source, uid, start_at)
);
CREATE INDEX calendar_events_date ON calendar_events (date);
CREATE TABLE day_counters (
    date TEXT NOT NULL,
    kind TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    raw_json TEXT,
    PRIMARY KEY (date, kind)
);
