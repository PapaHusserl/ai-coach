-- Профиль спортсмена: журнал ключ-значение. Записи только добавляются; текущее значение ключа —
-- последняя запись, ручное главнее Garmin.
CREATE TABLE profile_log (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'garmin')),
    logged_at TEXT NOT NULL,
    raw_json TEXT
);
CREATE INDEX profile_log_key ON profile_log (key, logged_at);
