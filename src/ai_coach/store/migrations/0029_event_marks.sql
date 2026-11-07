-- Отметки к пункту плана (веб-пульт): event_id - пункт coach_events, связь без внешнего ключа (как
-- coach_events.workout_id); NULL - запись из CLI.
ALTER TABLE focus_log ADD COLUMN event_id INTEGER;
ALTER TABLE wellbeing_log ADD COLUMN event_id INTEGER;
ALTER TABLE slip_log ADD COLUMN event_id INTEGER;

-- «Сделал / пропустил» у пункта за день: одна на пункт и дату (у повтора - день повтора), done 0/1.
CREATE TABLE done_log (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    done INTEGER NOT NULL CHECK (done IN (0, 1)),
    logged_at TEXT NOT NULL,
    UNIQUE (event_id, date)
);
CREATE INDEX done_log_date ON done_log (date);
