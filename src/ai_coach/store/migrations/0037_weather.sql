-- Погода (П7): наблюдения на момент синка и прогноз по дням; координаты округлены до 2 знаков.
CREATE TABLE weather_now (
    observed_at TEXT PRIMARY KEY,
    temperature REAL NOT NULL,
    apparent REAL NOT NULL,
    code INTEGER NOT NULL,
    wind REAL NOT NULL,
    pressure REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    place_source TEXT NOT NULL CHECK (place_source IN ('macos', 'config')),
    utc_offset_seconds INTEGER NOT NULL
);

CREATE TABLE weather_days (
    date TEXT PRIMARY KEY,
    code INTEGER NOT NULL,
    t_max REAL NOT NULL,
    t_min REAL NOT NULL,
    precip_prob INTEGER,
    fetched_at TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL
);
