-- Опросник благополучия WHO-5 раз в 2 недели: пять ответов 0-5 и балл 0-100 (coach who5).
CREATE TABLE who5_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    q1 INTEGER NOT NULL CHECK (q1 BETWEEN 0 AND 5),
    q2 INTEGER NOT NULL CHECK (q2 BETWEEN 0 AND 5),
    q3 INTEGER NOT NULL CHECK (q3 BETWEEN 0 AND 5),
    q4 INTEGER NOT NULL CHECK (q4 BETWEEN 0 AND 5),
    q5 INTEGER NOT NULL CHECK (q5 BETWEEN 0 AND 5),
    score INTEGER NOT NULL CHECK (score = (q1 + q2 + q3 + q4 + q5) * 4),
    text TEXT
);
CREATE INDEX who5_log_date ON who5_log (date);
