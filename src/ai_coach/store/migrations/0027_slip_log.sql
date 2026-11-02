-- Срыв в момент: свободный текст эмоций как есть (coach slip).
CREATE TABLE slip_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    text TEXT NOT NULL CHECK (length(trim(text)) > 0)
);
CREATE INDEX slip_log_date ON slip_log (date);
