-- CHECK статусов goals и sync_log (пересоздание таблиц), связь фаз с целями, события фаз.
-- На goals ссылается goal_events: на время пересоздания её данные уходят во временную таблицу,
-- иначе DROP goals нарушает внешний ключ (PRAGMA foreign_keys внутри транзакции не меняется).
CREATE TABLE goal_events_old AS SELECT * FROM goal_events;
DROP TABLE goal_events;

CREATE TABLE goals_new (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    target TEXT,
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
INSERT INTO goals_new (id, title, kind, priority, target, target_date, status, created_at, updated_at)
SELECT id, title, kind, priority, target, target_date, status, created_at, updated_at FROM goals;
DROP TABLE goals;
ALTER TABLE goals_new RENAME TO goals;

CREATE TABLE goal_events (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES goals (id),
    event_type TEXT NOT NULL,
    payload_json TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX goal_events_goal ON goal_events (goal_id, occurred_at);
INSERT INTO goal_events (id, goal_id, event_type, payload_json, occurred_at)
SELECT id, goal_id, event_type, payload_json, occurred_at FROM goal_events_old;
DROP TABLE goal_events_old;

CREATE TABLE sync_log_new (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    message TEXT
);
INSERT INTO sync_log_new (id, started_at, finished_at, kind, status, message)
SELECT id, started_at, finished_at, kind, status, message FROM sync_log;
DROP TABLE sync_log;
ALTER TABLE sync_log_new RENAME TO sync_log;

CREATE TABLE phase_goals (
    phase_id INTEGER NOT NULL REFERENCES phases (id),
    goal_id INTEGER NOT NULL REFERENCES goals (id),
    PRIMARY KEY (phase_id, goal_id)
);

CREATE TABLE phase_events (
    id INTEGER PRIMARY KEY,
    phase_id INTEGER NOT NULL REFERENCES phases (id),
    event_type TEXT NOT NULL CHECK (event_type IN ('proposed', 'accepted')),
    payload_json TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX phase_events_phase ON phase_events (phase_id, occurred_at);
