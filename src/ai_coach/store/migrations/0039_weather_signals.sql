-- Сработавшие погодные сигналы (П7, партия 8): первая запись дня и кода остаётся.
CREATE TABLE weather_signals (
    date TEXT NOT NULL,
    kind TEXT NOT NULL,
    value REAL NOT NULL,
    limit_value REAL NOT NULL,
    extreme_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (date, kind)
);
