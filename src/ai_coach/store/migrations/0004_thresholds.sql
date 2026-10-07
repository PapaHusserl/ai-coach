-- Пороговый пульс (LTHR) из Garmin: по записи на дату измерения. Нужен для hrTSS.
CREATE TABLE thresholds (
    calendar_date TEXT PRIMARY KEY,
    lthr INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);
