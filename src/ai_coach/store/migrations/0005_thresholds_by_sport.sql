-- Пороги по видам спорта (lthr пуст, если зоны Garmin дали только максимальный пульс): ключ (sport, calendar_date), источник порога. Старые строки — бег из Garmin.
CREATE TABLE thresholds_new (
    sport TEXT NOT NULL CHECK (sport IN ('run', 'bike', 'swim')),
    calendar_date TEXT NOT NULL,
    lthr INTEGER,
    source TEXT NOT NULL CHECK (source IN ('garmin_lt', 'garmin_zones')),
    max_hr INTEGER,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (sport, calendar_date, source)
);
INSERT INTO thresholds_new (sport, calendar_date, lthr, source, raw_json)
SELECT 'run', calendar_date, lthr, 'garmin_lt', raw_json FROM thresholds;
DROP TABLE thresholds;
ALTER TABLE thresholds_new RENAME TO thresholds;
