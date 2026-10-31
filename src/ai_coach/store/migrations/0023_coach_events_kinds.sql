-- События тренера: к видам добавлены focus (блок фокуса) и meal (еда) - блоки плана дня, без категории,
-- в нагрузку не входят. SQLite не умеет менять CHECK, поэтому таблица пересоздаётся (как 0009);
-- id и calendar_uid переносятся как есть.
CREATE TABLE coach_events_new (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('training', 'practice', 'rest', 'sleep', 'checkin', 'task', 'focus', 'meal')),
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
    note TEXT,
    category TEXT CHECK (category IN ('work', 'personal', 'hobby', 'rest')),
    alarm_min INTEGER CHECK (alarm_min >= 0),
    repeat TEXT CHECK (repeat IS NULL OR (repeat = 'daily' AND kind = 'checkin')),
    workout_id INTEGER,
    practice_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'written', 'cancelled', 'removed')),
    calendar_uid TEXT,
    created_at TEXT NOT NULL,
    written_at TEXT,
    removed_at TEXT,
    removed_by TEXT CHECK (removed_by IN ('cli', 'calendar'))
);
INSERT INTO coach_events_new (
    id, kind, title, date, start_at, end_at, all_day, note, category, alarm_min, repeat,
    workout_id, practice_id, status, calendar_uid, created_at, written_at, removed_at, removed_by
)
    SELECT
        id, kind, title, date, start_at, end_at, all_day, note, category, alarm_min, repeat,
        workout_id, practice_id, status, calendar_uid, created_at, written_at, removed_at, removed_by
    FROM coach_events;
DROP TABLE coach_events;
ALTER TABLE coach_events_new RENAME TO coach_events;
CREATE INDEX coach_events_date ON coach_events (date);
CREATE INDEX coach_events_status ON coach_events (status);
CREATE INDEX coach_events_uid ON coach_events (calendar_uid);
