-- Утренний тест реакции PVT-B (coach pvt): итоги и сырой список времён реакции.
CREATE TABLE pvt_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    duration_s INTEGER NOT NULL,
    trials INTEGER NOT NULL CHECK (trials >= 0),
    false_starts INTEGER NOT NULL CHECK (false_starts >= 0),
    lapses INTEGER NOT NULL CHECK (lapses >= 0),
    mean_rt_ms INTEGER,
    median_rt_ms INTEGER,
    slow10_ms INTEGER,
    speed REAL,
    rts TEXT NOT NULL
);
CREATE INDEX pvt_log_date ON pvt_log (date);
