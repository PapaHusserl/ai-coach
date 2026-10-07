-- Самочувствие: оценка 1-5 и текст. Записи только добавляются; основная за день — последняя.
CREATE TABLE wellbeing_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    text TEXT
);
