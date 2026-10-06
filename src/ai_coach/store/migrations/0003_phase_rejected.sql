-- Фазы: статус rejected, события updated и rejected. phase_goals и phase_events ссылаются на
-- phases, поэтому на время пересоздания их данные уходят во временные таблицы.
CREATE TABLE phase_goals_old AS SELECT * FROM phase_goals;
CREATE TABLE phase_events_old AS SELECT * FROM phase_events;
DROP TABLE phase_goals;
DROP TABLE phase_events;

CREATE TABLE phases_new (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'accepted', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    accepted_at TEXT
);
INSERT INTO phases_new (id, name, description, start_date, end_date, status, created_at, accepted_at)
SELECT id, name, description, start_date, end_date, status, created_at, accepted_at FROM phases;
DROP TABLE phases;
ALTER TABLE phases_new RENAME TO phases;

CREATE TABLE phase_goals (
    phase_id INTEGER NOT NULL REFERENCES phases (id),
    goal_id INTEGER NOT NULL REFERENCES goals (id),
    PRIMARY KEY (phase_id, goal_id)
);
INSERT INTO phase_goals (phase_id, goal_id) SELECT phase_id, goal_id FROM phase_goals_old;
DROP TABLE phase_goals_old;

CREATE TABLE phase_events (
    id INTEGER PRIMARY KEY,
    phase_id INTEGER NOT NULL REFERENCES phases (id),
    event_type TEXT NOT NULL CHECK (event_type IN ('proposed', 'updated', 'accepted', 'rejected')),
    payload_json TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX phase_events_phase ON phase_events (phase_id, occurred_at);
INSERT INTO phase_events (id, phase_id, event_type, payload_json, occurred_at)
SELECT id, phase_id, event_type, payload_json, occurred_at FROM phase_events_old;
DROP TABLE phase_events_old;
