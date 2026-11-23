-- Индекс Kp из NOAA SWPC (П7, партия 11): время UTC, шаг 3 ч; координат нет.
CREATE TABLE kp_index (
    time TEXT PRIMARY KEY,
    kp REAL NOT NULL,
    kind TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
