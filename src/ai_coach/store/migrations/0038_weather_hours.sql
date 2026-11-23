-- Почасовой ряд погоды (П7, партия 6): прогноз сервиса и последние часы; координаты округлены до 2 знаков.
CREATE TABLE weather_hours (
    time TEXT PRIMARY KEY,
    temperature REAL NOT NULL,
    pressure REAL,
    pressure_surface REAL,
    humidity REAL,
    wind REAL,
    fetched_at TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    place_source TEXT NOT NULL CHECK (place_source IN ('macos', 'config')),
    source TEXT NOT NULL CHECK (source IN ('forecast', 'archive'))
);
