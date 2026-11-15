-- Формы: определение (поля объектом в fields_json) заводит тренер; снятая форма остаётся в базе.
CREATE TABLE forms (
    name TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT
);
-- Ответы формы у пункта календаря: значения по ключам полей. Повтор добавляет строку. wellbeing_id -
-- запись самочувствия, если у формы есть поле score (оценка и текст лежат там, не здесь).
CREATE TABLE form_log (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    event_id INTEGER NOT NULL REFERENCES coach_events (id),
    form TEXT NOT NULL REFERENCES forms (name),
    values_json TEXT NOT NULL,
    text TEXT,
    wellbeing_id INTEGER REFERENCES wellbeing_log (id)
);
CREATE INDEX form_log_date ON form_log (date);
CREATE INDEX form_log_event ON form_log (event_id, date);
