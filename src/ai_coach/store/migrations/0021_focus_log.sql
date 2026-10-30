-- Дневная самооценка: фокус, умственная усталость и «трудно заставить себя» 1-5 (coach focus).
CREATE TABLE focus_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    focus INTEGER NOT NULL CHECK (focus BETWEEN 1 AND 5),
    fatigue INTEGER NOT NULL CHECK (fatigue BETWEEN 1 AND 5),
    effort INTEGER NOT NULL CHECK (effort BETWEEN 1 AND 5),
    text TEXT
);
CREATE INDEX focus_log_date ON focus_log (date);
